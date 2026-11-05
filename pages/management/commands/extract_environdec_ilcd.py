"""Read EPD figures from the ILCD datasets rather than out of the PDFs.

Why this exists alongside `extract_environdec_epds`: on the 2026 batch of
Indian EPDs the PDF parser refuses 22 of every 25, because the declaration
layouts have drifted and a GWP row can no longer be matched to its module
header. It refuses honestly, so nothing wrong is imported, but almost nothing
is imported either.

Most of those same EPDs are also published as ILCD datasets on
data.environdec.com, keyed on the UUID the library listing already gives us.
There the module figures are tagged, so A1-A3 is read rather than inferred
from a column position.

It writes the SAME csv shape as the PDF extractor, so the existing
`import_environdec_epds` gates still apply: the declared unit must be
present, the implied kgCO2e per kg must sit in a sane band for the material,
and the name must map to a real leaf category.

Refusals, never guesses:
  * no dataset for that UUID (the older EPDs are PDF-only)
  * no GWP-total result, or no A1-A3 module on it
  * a declared unit that cannot be read confidently from the stated
    functional unit

    python manage.py extract_environdec_ilcd --in shortlist.csv --out parsed.csv
"""
import csv
import io
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter

import requests
from django.core.management.base import BaseCommand

# TLS verification stays ON. On a machine whose antivirus intercepts HTTPS,
# point REQUESTS_CA_BUNDLE at certifi plus the local roots; requests reads it.
HEADERS = {"User-Agent": "Mozilla/5.0 (BEAT EPD import)"}
RESOURCE = "https://data.environdec.com/resource/processes/%s?format=xml"
FLOW = "https://data.environdec.com/resource/flows/%s?format=xml"

# ILCD flow property -> the unit BEAT stores. 60 of the 98 Indian datasets
# leave functionalUnitOrOther empty and put the declared unit only in the
# reference flow, where it is a property name rather than a unit string.
FLOW_PROPERTY_UNITS = {
    "mass": "kg",
    "area": "m2",
    "volume": "m3",
    "length": "m",
    "number of pieces": "pcs",
    "items": "pcs",
    "pieces": "pcs",
    # The same properties as the publisher writes them in German. These
    # datasets return the reference flow property's own name in whatever
    # language it was registered in, and several Indian EPDs resolve to the
    # German originals.
    "masse": "kg",
    "fläche": "m2",
    "flaeche": "m2",
    "volumen": "m3",
    "länge": "m",
    "laenge": "m",
    "anzahl": "pcs",
    "stück": "pcs",
}

# Flow property UUID -> unit, tried BEFORE the name above.
#
# 15 Indian EPDs were refused because their reference flow property's
# shortDescription had been replaced with the PRODUCT name: "Steel Plate",
# "Manhole Cover", "VDS(r) Fixed Partition". Keyed on that name nothing
# matched and a declaration with a perfectly good figure was dropped. The
# UUID beneath it is a reference to a standard ILCD flow property, and in
# every dataset inspected it was correct even where the name was not, so it
# is the better key.
#
# The first three were confirmed by fetching the flow property dataset from
# the registry. Area and Volume return HTTP 403 and could not be confirmed
# that way; they are included on the weaker basis that two datasets carry
# them with their own name reading "Area" and "Volume" and the figures then
# make sense. That is stated rather than hidden, and it costs little: when
# the name is right the name route already handles it.
#
# These UUIDs differ only in the middle. Truncating them to 12 characters
# while investigating made Mass, Area and Volume look like the same
# identifier and nearly produced a map that labelled carpet tile per m2 as
# per kg. Compare them whole.
FLOW_PROPERTY_UUID_UNITS = {
    # confirmed against the registry
    "93a60a56-a3c8-11da-a746-0800200b9a66": "kg",   # Mass / Masse
    "838aaa23-0117-11db-92e3-0800200c9a66": "m",    # Length / Länge
    "01846770-4cfe-4a25-8ad9-919d8d378345": "pcs",  # Number of items
    # observed in datasets whose own name agreed; not registry-confirmed
    "93a60a56-a3c8-19da-a746-0800200c9a66": "m2",   # Area
    "93a60a56-a3c8-22da-a746-0800200c9a66": "m3",   # Volume
}

NS = {
    "p": "http://lca.jrc.it/ILCD/Process",
    "c": "http://lca.jrc.it/ILCD/Common",
    "epd": "http://www.iai.kit.edu/EPD/2013",
    "epd2": "http://www.indata.network/EPD/2019",
}

OUT_FIELDS = [
    "status", "country", "material_group", "product", "manufacturer",
    "registration_number", "gwp_a1a3", "declared_amount", "declared_unit",
    "gwp_a4", "gwp_a5", "gwp_c", "gwp_d", "url", "reason", "header_row",
]

# "1 m2 of installed plasterboard ...", "1 tonne of cement", "1 kg of paint".
UNIT_WORDS = {
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "tonne": "ton", "tonnes": "ton", "ton": "ton", "tons": "ton", "t": "ton",
    "m2": "m2", "m²": "m2", "sqm": "m2",
    "m3": "m3", "m³": "m3", "cbm": "m3",
    "m": "m", "metre": "m", "meter": "m", "metres": "m", "meters": "m",
    "piece": "pcs", "pieces": "pcs", "pcs": "pcs", "unit": "pcs",
}
# The trailing digit is part of the unit: without it "1 m2 of plasterboard"
# reads as one METRE of plasterboard, which the plausibility bands cannot
# catch because a per-metre figure is not absurd on its face.
FUNCTIONAL = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*([A-Za-z]+[23²³]?)\b", re.U)


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def parse_unit(functional_unit):
    """Return (amount, unit) or (None, reason)."""
    m = FUNCTIONAL.match(functional_unit or "")
    if not m:
        return None, "functional unit does not start with a number and a unit"
    raw_amount, raw_unit = m.group(1).replace(",", "."), m.group(2).lower()
    unit = UNIT_WORDS.get(raw_unit)
    if not unit:
        return None, "unrecognised declared unit %r" % raw_unit[:20]
    try:
        amount = float(raw_amount)
    except ValueError:
        return None, "declared amount %r is not a number" % raw_amount[:20]
    if amount <= 0:
        return None, "declared amount is %s" % amount
    return (amount, unit), None


def unit_for_flow_property(uuid, name):
    """The declared unit a reference flow property implies, or None.

    UUID first, name second. A publisher can rewrite the property's
    shortDescription and several Indian ones have, replacing it with the
    product name, which is why 15 declarations with perfectly good figures
    were refused. The UUID is a reference to a standard ILCD flow property
    and was correct in every dataset inspected, so it is the better key.

    Returning None is a refusal and the caller must treat it as one. Guessing
    a unit here would divide a carbon figure by the wrong dimension, which
    produces a number that looks entirely reasonable and is not.
    """
    return (FLOW_PROPERTY_UUID_UNITS.get((uuid or "").strip().lower())
            or FLOW_PROPERTY_UNITS.get((name or "").strip().lower()))


def reference_flow_unit(session, root, delay):
    """Declared unit and amount from the reference flow's own dataset.

    Returns ((amount, unit), None) or (None, reason). The flow states a
    property - Mass, Area, Volume - rather than a unit string, so the mapping
    above is applied and anything unmapped is refused.
    """
    ref_id = None
    for el in root.iter():
        if el.tag.endswith("referenceToReferenceFlow"):
            ref_id = _text(el)
            break
    if ref_id is None:
        return None, "no reference flow on the process"

    flow_uuid, amount = None, None
    for ex in root.iter():
        if not ex.tag.endswith("exchange"):
            continue
        if ex.attrib.get("dataSetInternalID") != ref_id:
            continue
        for el in ex.iter():
            if el.tag.endswith("referenceToFlowDataSet"):
                flow_uuid = el.attrib.get("refObjectId")
            elif el.tag.endswith("meanAmount"):
                try:
                    amount = float(_text(el))
                except ValueError:
                    pass
        break
    if not flow_uuid:
        return None, "reference flow %s has no flow dataset" % ref_id
    if not amount or amount <= 0:
        return None, "reference flow amount is %r" % amount

    try:
        resp = session.get(FLOW % flow_uuid, timeout=60)
    except Exception as exc:
        return None, "flow fetch failed: %s" % type(exc).__name__
    time.sleep(delay)
    if resp.status_code != 200:
        return None, "flow dataset HTTP %s" % resp.status_code
    try:
        flow = ET.fromstring(resp.content)
    except ET.ParseError:
        return None, "flow dataset is not XML"

    prop_id = None
    for el in flow.iter():
        if el.tag.endswith("referenceToReferenceFlowProperty"):
            prop_id = _text(el)
            break
    name, per_unit, prop_uuid = "", None, ""
    for fp in flow.iter():
        if not fp.tag.endswith("flowProperty"):
            continue
        if prop_id is not None and fp.attrib.get("dataSetInternalID") != prop_id:
            continue
        for el in fp.iter():
            if el.tag.endswith("referenceToFlowPropertyDataSet"):
                prop_uuid = el.attrib.get("refObjectId", "") or prop_uuid
                for sub in el.iter():
                    if sub.tag.endswith("shortDescription") and not name:
                        name = _text(sub)
            elif el.tag.endswith("meanValue"):
                try:
                    per_unit = float(_text(el))
                except ValueError:
                    pass
        break
    unit = unit_for_flow_property(prop_uuid, name)
    if not unit:
        return None, ("flow property %r (%s) has no unit mapping"
                      % (name[:30], prop_uuid[:36] or "no uuid"))
    if per_unit is None or per_unit <= 0:
        return None, "reference flow property has no usable meanValue"

    # The declared amount is the exchange amount TIMES the flow property's own
    # meanValue. Steel declares 1 reference flow of 1000 kg; reading only the
    # exchange gave 1 kg and so a figure a thousand times too large per kg.
    # The importer's plausibility band is what caught that, which is why the
    # band is worth more than this comment.
    return (amount * per_unit, unit), None


def gwp_modules(root):
    """Module -> value for the GWP-total result, or {} if there is none."""
    for result in root.iter():
        if not result.tag.endswith("LCIAResult"):
            continue
        name = ""
        for el in result.iter():
            if el.tag.endswith("shortDescription"):
                name = _text(el)
                break
        if "gwp-total" not in name.lower().replace(" ", ""):
            continue
        out = {}
        for el in result.iter():
            if not el.tag.endswith("amount"):
                continue
            module = None
            for key, value in el.attrib.items():
                if key.endswith("module"):
                    module = value
            if module is None:
                continue
            try:
                out[module] = float(_text(el))
            except ValueError:
                continue
        return out
    return {}


class Command(BaseCommand):
    help = "Extract EPD GWP from environdec ILCD datasets into a review CSV."

    def add_arguments(self, parser):
        parser.add_argument("--in", dest="infile", required=True)
        parser.add_argument("--out", dest="outfile", required=True)
        parser.add_argument("--uuid-from", dest="uuidfile",
                            help="CSV carrying library_id,uuid when the "
                                 "shortlist itself has no uuid column.")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--delay", type=float, default=0.3)

    def handle(self, *args, **options):
        rows = list(csv.DictReader(
            io.open(options["infile"], encoding="utf-8-sig")))
        if options["limit"]:
            rows = rows[:options["limit"]]

        uuids = {}
        if options["uuidfile"]:
            for r in csv.DictReader(
                    io.open(options["uuidfile"], encoding="utf-8-sig")):
                if r.get("uuid"):
                    uuids[r.get("library_id", "")] = r["uuid"]
                    if r.get("url"):
                        uuids[r["url"]] = r["uuid"]

        session = requests.Session()
        session.headers.update(HEADERS)
        out_rows = []

        for i, row in enumerate(rows, start=1):
            base = {k: row.get(k, "") for k in
                    ("country", "material_group", "product", "manufacturer",
                     "registration_number", "url")}
            out = dict.fromkeys(OUT_FIELDS, "")
            out.update(base)

            uuid = row.get("uuid") or uuids.get(row.get("url", "")) or ""
            if not uuid:
                lib = re.search(r"/library/epd(\d+)", row.get("url", "") or "")
                uuid = uuids.get("epd%s" % lib.group(1), "") if lib else ""
            if not uuid:
                out.update(status="REFUSED", reason="no dataset uuid known")
                out_rows.append(out)
                continue

            try:
                resp = session.get(RESOURCE % uuid, timeout=60)
            except Exception as exc:
                out.update(status="REFUSED",
                           reason="fetch failed: %s" % type(exc).__name__)
                out_rows.append(out)
                continue
            time.sleep(options["delay"])

            if resp.status_code == 404:
                out.update(status="REFUSED",
                           reason="no ILCD dataset (PDF-only EPD)")
                out_rows.append(out)
                continue
            if resp.status_code != 200:
                out.update(status="REFUSED", reason="HTTP %s" % resp.status_code)
                out_rows.append(out)
                continue

            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError as exc:
                out.update(status="REFUSED", reason="not XML: %s" % exc)
                out_rows.append(out)
                continue

            mods = gwp_modules(root)
            if not mods:
                out.update(status="REFUSED", reason="no GWP-total result")
                out_rows.append(out)
                continue
            a1a3 = mods.get("A1-A3")
            if a1a3 is None:
                a1a3 = sum(mods[m] for m in ("A1", "A2", "A3") if m in mods) or None
            if a1a3 is None:
                out.update(status="REFUSED",
                           reason="GWP-total has no A1-A3 module")
                out_rows.append(out)
                continue

            functional = ""
            for el in root.iter():
                if el.tag.endswith("functionalUnitOrOther"):
                    functional = _text(el)
                    break
            parsed, why = parse_unit(functional)
            if not parsed:
                # Most datasets leave the functional unit blank and state the
                # declared unit only on the reference flow.
                parsed, why2 = reference_flow_unit(session, root,
                                                   options["delay"])
                if not parsed:
                    out.update(status="REFUSED",
                               reason="%s; %s" % (why, why2),
                               header_row=functional[:120])
                    out_rows.append(out)
                    continue
            amount, unit = parsed

            name = ""
            for el in root.iter():
                if el.tag.endswith("baseName"):
                    name = _text(el)
                    break

            out.update(
                status="OK",
                gwp_a1a3=a1a3,
                declared_amount=amount,
                declared_unit=unit,
                gwp_a4=mods.get("A4", ""),
                gwp_a5=mods.get("A5", ""),
                gwp_c=sum(v for k, v in mods.items() if k.startswith("C")) or "",
                gwp_d=mods.get("D", ""),
                product=base["product"] or name,
                header_row=functional[:120],
            )
            out_rows.append(out)

            if i % 10 == 0 or i == len(rows):
                ok = sum(1 for r in out_rows if r["status"] == "OK")
                self.stdout.write("   %d/%d   parsed %d   refused %d"
                                  % (i, len(rows), ok, len(out_rows) - ok))

        with io.open(options["outfile"], "w", newline="",
                     encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
            w.writeheader()
            w.writerows(out_rows)

        ok = sum(1 for r in out_rows if r["status"] == "OK")
        self.stdout.write("\nparsed %d, refused %d  ->  %s"
                          % (ok, len(out_rows) - ok, options["outfile"]))
        refusals = Counter(r["reason"] for r in out_rows
                           if r["status"] != "OK")
        if refusals:
            self.stdout.write("refusal reasons:")
            for reason, n in refusals.most_common(10):
                self.stdout.write("   %4d  %s" % (n, reason))
