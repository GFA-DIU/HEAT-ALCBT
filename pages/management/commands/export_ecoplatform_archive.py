"""Download an OFFLINE archive of ECO Platform EPDs (data only, no PDFs).

Builds a local, future-proof archive under ~/Downloads/Ecoplatform_ALCBT/:
  * global_index.csv  — metadata for EVERY current-valid EPD (all countries):
                        uuid, country, subtype, proxy_type, name, owner, ref_year, uri.
  * json/general/<proxy>/<uuid>.json — full data for GENERAL datasets usable as
                        proxies for data-poor countries (ALCBT): generic subtypes
                        (average/representative/generic/template) + global 'GLO'.
  * json/<ISO2>/<uuid>.json          — full data for specific/country datasets.
  * summary.csv       — one row per downloaded EPD (name, country, unit, GWP A1-A3).
  * manifest.json.

Resumable: files already saved (by uuid, any folder) are skipped, so you can run
--general first, then --all in the background without re-downloading.

    python manage.py export_ecoplatform_archive --general   # generic + global GLO (proxies)
    python manage.py export_ecoplatform_archive --all        # everything (resumes; huge)
    python manage.py export_ecoplatform_archive              # ALCBT countries only
    python manage.py export_ecoplatform_archive --index-only # refresh the global index only

Needs a valid ECO_PLATFORM_TOKEN in .env (expires ~daily). TLS verify disabled
(local Norton interception).
"""
import csv
import glob
import json
import os
from datetime import date, datetime

import requests
import urllib3
from django.core.management.base import BaseCommand

from pages.scripts.ecoplatform.ecoplatform_loader import (
    ECO_PLATFORM_URL, ECO_PLATFORM_TOKEN, country_list)

urllib3.disable_warnings()
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "Downloads", "Ecoplatform_ALCBT")
COUNTRY_NAMES = {"ID": "Indonesia", "IN": "India", "KH": "Cambodia",
                 "TH": "Thailand", "VN": "Vietnam"}
GENERIC_SUBTYPES = {"average dataset", "representative dataset",
                    "generic dataset", "template dataset"}
REGIONAL_GEO = {"RER", "EU", "ROW", "RER W/O DE", "WEU", "EUR", "RNA", "RAS", "RAF"}


def _headers():
    return {"Authorization": f"Bearer {ECO_PLATFORM_TOKEN}"}


def _get(url, timeout=120):
    r = requests.get(url, headers=_headers(), timeout=timeout, verify=False)
    r.raise_for_status()
    return r.json()


def _proxy_type(subtype, geo):
    """Classify how usable a dataset is as a proxy for a data-poor country."""
    st = (subtype or "").strip().lower()
    g = (geo or "").strip().upper()
    if st in GENERIC_SUBTYPES:
        return "generic"
    if g == "GLO":
        return "global"
    if g in REGIONAL_GEO:
        return "regional"
    return ""


def _pluck(e):
    def g(*keys):
        for k in keys:
            v = e.get(k)
            if v:
                return v
        return ""
    geo = (g("geo") or "").strip().upper()
    subtype = (g("subType") or "").strip()
    return {
        "uuid": g("uuid"), "country": geo, "subtype": subtype,
        "proxy_type": _proxy_type(subtype, geo), "name": g("name"),
        "owner": g("owner", "regAuthority"), "ref_year": g("refYear"),
        "valid_until": g("validUntil"), "uri": g("uri"),
    }


class Command(BaseCommand):
    help = "Download an offline ECO Platform EPD archive (general proxies / all / ALCBT)."

    def add_arguments(self, parser):
        parser.add_argument("--out", default=DEFAULT_OUT)
        parser.add_argument("--general", action="store_true",
                            help="Download GENERAL proxies (generic subtypes + global GLO).")
        parser.add_argument("--all", dest="everything", action="store_true",
                            help="Download every valid EPD (resumes; large & slow).")
        parser.add_argument("--countries", default=",".join(country_list))
        parser.add_argument("--index-only", action="store_true")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **o):
        out = o["out"]
        os.makedirs(out, exist_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Archive → {out}"))

        # --- 1) list all current-valid EPDs (metadata) ---
        try:
            total = _get(f"{ECO_PLATFORM_URL}&pageSize=1").get("totalCount") or 0
            self.stdout.write(f"ECO Platform: {total} current-valid EPDs. Fetching list…")
            data = _get(f"{ECO_PLATFORM_URL}&pageSize={total}")
        except requests.HTTPError as e:
            self.stdout.write(self.style.ERROR(
                f"List call failed (HTTP {getattr(e.response,'status_code','?')}). "
                f"The ECO_PLATFORM_TOKEN in .env is likely expired — refresh it and re-run."))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"List call failed: {e}"))
            return

        rows = [_pluck(x) for x in data.get("data", [])]
        rows = [r for r in rows if r["uuid"]]

        # --- 2) rich global index (every country) ---
        with open(os.path.join(out, "global_index.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["uuid", "country", "subtype", "proxy_type",
                                              "name", "owner", "ref_year", "valid_until", "uri"])
            w.writeheader()
            for r in rows:
                w.writerow(r)
        n_generic = sum(1 for r in rows if r["proxy_type"] == "generic")
        n_global = sum(1 for r in rows if r["proxy_type"] == "global")
        self.stdout.write(self.style.SUCCESS(
            f"global_index.csv: {len(rows)} EPDs. generic={n_generic}, global(GLO)={n_global}."))
        if o["index_only"]:
            self._manifest(out, total, len(rows), 0)
            return

        # --- 3) choose targets, GENERAL first ---
        if o["everything"]:
            general = [r for r in rows if r["proxy_type"] in ("generic", "global")]
            rest = [r for r in rows if r["proxy_type"] not in ("generic", "global")]
            targets = general + rest       # general first, then the rest
            label = "ALL (general first)"
        elif o["general"]:
            targets = [r for r in rows if r["proxy_type"] in ("generic", "global")]
            label = "general proxies (generic + global GLO)"
        else:
            codes = {c.strip().upper() for c in o["countries"].split(",")}
            targets = [r for r in rows if r["country"] in codes]
            label = f"countries {sorted(codes)}"
        if o["limit"]:
            targets = targets[: o["limit"]]

        # resume: skip uuids already saved anywhere under json/
        have = {os.path.splitext(os.path.basename(p))[0]
                for p in glob.glob(os.path.join(out, "json", "**", "*.json"), recursive=True)}
        todo = [r for r in targets if r["uuid"] not in have]
        self.stdout.write(
            f"Target: {label} — {len(targets)} EPDs, {len(have)} already on disk, "
            f"{len(todo)} to download.")

        json_dir = os.path.join(out, "json")
        spath = os.path.join(out, "summary.csv")
        new_summary, ok, fail = [], 0, 0
        for n, r in enumerate(todo, 1):
            try:
                full = _get(f"{r['uri']}&lang=en&format=json&view=extended")
                full["source"] = r["uri"]
            except Exception:
                fail += 1
                continue
            if r["proxy_type"] in ("generic", "global"):
                sub = os.path.join(json_dir, "general", r["proxy_type"])
            else:
                sub = os.path.join(json_dir, r["country"] or "XX")
            os.makedirs(sub, exist_ok=True)
            with open(os.path.join(sub, f"{r['uuid']}.json"), "w", encoding="utf-8") as jf:
                json.dump(full, jf, ensure_ascii=False, indent=2)
            new_summary.append(self._summary_row(r, full))
            ok += 1
            if n % 100 == 0:
                self._append_summary(spath, new_summary); new_summary = []
                self.stdout.write(f"  …{n}/{len(todo)} ({ok} saved, {fail} failed)")
        self._append_summary(spath, new_summary)
        self._manifest(out, total, len(rows), ok, fail, label)
        self.stdout.write(self.style.SUCCESS(
            f"Done. {ok} new EPD JSON saved ({fail} failed). Target was: {label}."))

    def _summary_row(self, meta, full):
        unit = gwp = ""
        try:
            from pages.scripts.oekobaudat.oekobaudat_loader import parse_epd
            p = parse_epd(full) or {}
            unit = p.get("declared_unit") or ""
            gwp = p.get("gwp_a1a3") if p.get("gwp_a1a3") is not None else ""
        except BaseException:   # lcax (Rust) can PANIC (BaseException) on bad floats
            pass
        return {"uuid": meta["uuid"], "country": meta["country"],
                "country_name": COUNTRY_NAMES.get(meta["country"], meta["country"]),
                "proxy_type": meta["proxy_type"], "subtype": meta["subtype"],
                "name": meta["name"], "declared_unit": unit, "gwp_a1a3": gwp,
                "valid_until": meta["valid_until"], "uri": meta["uri"]}

    def _append_summary(self, path, rows):
        if not rows:
            return
        fields = ["uuid", "country", "country_name", "proxy_type", "subtype",
                  "name", "declared_unit", "gwp_a1a3", "valid_until", "uri"]
        new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            if new:
                w.writeheader()
            w.writerows(rows)

    def _manifest(self, out, total, indexed, downloaded, failed=0, label=""):
        with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({
                "fetched": datetime.now().isoformat(timespec="seconds"),
                "source": "ECO Platform (portal.eco-platform.org)",
                "valid_year": date.today().year, "total_reported": total,
                "indexed": indexed, "last_download_count": downloaded, "failed": failed,
                "last_target": label, "note": "Data only (no PDFs).",
            }, f, ensure_ascii=False, indent=2)
