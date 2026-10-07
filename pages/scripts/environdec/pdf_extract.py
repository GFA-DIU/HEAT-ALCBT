"""Read GWP figures out of an EPD International PDF.

Why this exists
---------------
EPD International's Downstream API, which serves ILCD+EPD datasets, is "subject
to a formal request and approval process". Until that is granted the only
machine-reachable form of these declarations is the published PDF.

Reading numbers out of a PDF is how wrong carbon figures get into a tool, so
this module is built to refuse rather than guess. Every value it returns is
anchored to a module header it actually found; if the header is missing, or the
column count does not line up with the numbers, it reports a reason and returns
nothing. A gap in the import is recoverable. A plausible-looking number in the
wrong column is not.

The shape it keys on, which is consistent across the EN 15804+A2 declarations
in this library:

    Parameter Unit A1-3*** A4 A5 B1-B7 C1 C2 C3 C4 D**
    GWP-total kg CO2 eq. 1.19E+00 4.62E-02 4.00E-01 0.00E+00 ...

    A1-A3 A4 A5 C1 C2 C3 C4 D
    GWP-total [kg CO2 eq.] 4,93E-01 6,26E-02 2,55E-03 ...

Note the second uses comma decimals. Both are handled; the comma is only ever
read as a decimal point inside a number that already looks like one, never as a
thousands separator.
"""
import re

# A GWP row. Declarations in this library write the indicator either way:
#   GWP-total kg CO2 eq. ...
#   Global Warming Potential, total kg CO2 eq. ...
GWP_ROW = re.compile(
    r"^\s*(?:GWP|Global\s+Warming\s+Potential)\s*[-,–]?\s*(.{0,46})", re.I)


def classify_gwp(qualifier):
    """Which GWP indicator a row is - or None for one that must not be used.

    The biogenic and land-use rows sit directly beneath the headline figure and
    carry numbers of the same shape. Treating an unrecognised qualifier as the
    headline would therefore quietly pick, say, 0.232 kg CO2e/tonne of biogenic
    carbon as a cement's footprint, so they are excluded by name rather than
    left to fall through.
    """
    q = qualifier.lower()
    if re.search(r"biogenic|luluc|land\s*use", q):
        return None
    if "total" in q:
        return "total"
    if "ghg" in q:
        return "ghg"
    if "fossil" in q:
        return "fossil"
    return ""

# Scientific notation first, so "4,93E-01" is taken whole rather than as "4,93".
# Three notations appear across this library and all three mean the same thing:
#   4,93E-01   E-notation, comma decimal
#   1.19E+00   E-notation, point decimal
#   6.00*102   "times ten to the", with the exponent run onto the 10
#   4.98*10-1  the same, negative exponent
NUMBER = re.compile(
    r"-?\d+(?:[.,]\d+)?\s*[*x×]\s*10\s*-?\d+"
    r"|-?\d+(?:[.,]\d+)?[Ee][+-]?\d+"
    r"|-?\d+[.,]\d+"
    r"|-?\d+"
)

# The "6.00*102" form, split into mantissa and exponent.
TIMES_TEN = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*[*x×]\s*10\s*(-?\d+)$")

# Module labels as they appear in the header row. The trailing asterisks are
# footnote markers and are stripped.
MODULE = re.compile(
    r"\bA\s?1\s*[-–]\s*A?\s?3\b|\bA[1-5]\b|\bB[1-7]\s*[-–]\s*B[1-7]\b|"
    r"\bB[1-7]\b|\bC[1-4]\s*[-–]\s*C[1-4]\b|\bC[1-4]\b|\bD\b",
    re.I,
)

# "1 kg of product", "1m2 of plasterboard", "declared unit of 1 tonne"
# The declared unit is written either as a sentence ("the declared unit of 1
# tonne of product") or as a table caption ("Impact per 1,000 kg average").
# Thousands separators are common in the caption form, so the amount is
# captured loosely and cleaned by _declared_amount below.
DECLARED = re.compile(
    r"(?:(?:declared|functional)\s+unit|impacts?\s+per|results?\s+per)"
    r"[^.\n]{0,80}?(\d[\d,\s]*(?:\.\d+)?)\s*"
    r"(kg|kilogram|tonne|ton|m2|m²|m3|m³|piece|pcs)\b",
    re.I,
)


def _declared_amount(token):
    """'1,000' / '1 000' -> 1000.0. Separators only, never a decimal comma."""
    return float(re.sub(r"[,\s]", "", token))


# The unit sits between the row label and the first value - "kg CO2 eq." or
# "[kg CO2 eq.]". The 2 in CO2 is a digit, so it has to come out before the
# numbers are counted or every row is off by one against its header.
UNIT_NOISE = re.compile(r"\[[^\]]*\]|kg\s*CO\s*2?\s*(?:eq\.?)?|CO\s*2", re.I)


def strip_unit(line):
    """Remove the unit column so only data values are counted."""
    return UNIT_NOISE.sub(" ", line)


def _to_float(token):
    """Parse a number that may use either a comma or a point as its decimal."""
    t = token.strip()
    times = TIMES_TEN.match(t)
    if times:
        return _to_float(times.group(1)) * (10 ** int(times.group(2)))
    if "," in t and "." in t:
        # Both present: the last one seen is the decimal separator.
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    return float(t)


def normalise_module(token):
    """'A1-3***' / 'A 1 - A3' -> 'A1-A3'; everything else upper-cased."""
    t = re.sub(r"[*\s–]", "", token).upper().replace("—", "-")
    t = re.sub(r"^A1-?A?3$", "A1-A3", t)
    return t


def parse_modules(header_line):
    """Module labels in the order they appear across the header row."""
    return [normalise_module(m.group(0)) for m in MODULE.finditer(header_line)]


def extract_from_text(text):
    """Return {modules: {...}, declared: (amount, unit), note: str} or an error.

    The result always carries `ok`. When False, `reason` says why, and nothing
    should be imported from this document without a human reading it.
    """
    lines = text.splitlines()
    best = None
    candidates = []

    for i, line in enumerate(lines):
        match = GWP_ROW.match(line)
        if not match:
            continue
        indicator = classify_gwp(match.group(1))
        if indicator is None:          # biogenic / land-use row, not the headline
            continue
        numbers = NUMBER.findall(strip_unit(line))
        if not numbers:
            continue

        # Walk back to the nearest line that looks like a table header. Six
        # lines clears a wrapped caption without drifting into prose.
        #
        # Both table shapes in this library are handled by the same rule,
        # because both are anchored on the header having exactly as many
        # module labels as the row has values:
        #
        #   wide      A1-A3 A4 A5 C1 C2 C3 C4 D        8 modules, 8 values
        #   vertical  Indicator Unit A1-A3             1 module,  1 value
        header, modules = None, []
        for j in range(i - 1, max(-1, i - 7), -1):
            text_j = lines[j].strip()
            # A header is a short label row, not a sentence. Without this a
            # paragraph happening to mention "A1-A3" could be mistaken for one.
            if not text_j or len(text_j) > 120 or text_j.endswith("."):
                continue
            found = parse_modules(text_j)
            if found:
                header, modules = text_j, found
                break
        if not header:
            continue

        if len(modules) != len(numbers):
            # A mismatch means the columns cannot be lined up, so the values
            # cannot be placed. Keep looking - declarations often repeat the
            # table once per product variant.
            best = best or {"ok": False, "reason": (
                "column mismatch: header has %d modules, GWP row has %d numbers"
                % (len(modules), len(numbers)))}
            continue

        values = {}
        for mod, num in zip(modules, numbers):
            try:
                values[mod] = _to_float(num)
            except ValueError:
                continue
        if "A1-A3" not in values:
            best = best or {"ok": False,
                            "reason": "no A1-A3 column in header: %s" % header[:80]}
            continue

        candidates.append((indicator, values, header, line))

    if not candidates:
        return best or {"ok": False,
                        "reason": "no GWP row with a readable module header"}

    # EN 15804+A2 makes GWP-total the headline figure; GWP-fossil is usually
    # printed first, so pick by label rather than by position.
    order = {"total": 0, "ghg": 1, "": 2, "fossil": 3}
    label, values, header, row = min(candidates, key=lambda c: order.get(c[0], 4))

    declared = DECLARED.search(text)
    return {
        "ok": True,
        "gwp_row": "GWP-%s" % (label or "total"),
        "modules": values,
        "gwp_a1a3": values["A1-A3"],
        "declared_amount": _declared_amount(declared.group(1)) if declared else None,
        "declared_unit": declared.group(2).lower() if declared else None,
        "header": header[:120],
        "row": row.strip()[:120],
    }


def extract_from_pdf(path):
    """Read `path` and pull the GWP table out of it."""
    import pypdf
    try:
        reader = pypdf.PdfReader(path)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as exc:
        return {"ok": False, "reason": "unreadable PDF: %s" % type(exc).__name__}
    if not text.strip():
        return {"ok": False, "reason": "no extractable text (scanned image?)"}
    return extract_from_text(text)
