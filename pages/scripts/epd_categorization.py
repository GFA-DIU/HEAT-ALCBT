"""Shared EPD -> MaterialCategory resolver used by every EPD loader.

Categorization is DISPLAY / DASHBOARD grouping only — it does NOT affect any
building's carbon calculation. Centralising it here keeps the behaviour identical
across loaders (oekobaudat, TGO, ECO-Platform, generic CSVs) and removes the
per-loader ad-hoc fallbacks (notably the old bogus "Primer for paints and
plasters" default that mislabelled most non-oekobaudat imports).

Resolution order (first hit wins):
  1. exact classification id      -> MaterialCategory.category_id  (authoritative)
  2. rebar detected by name       -> "Steel reinforing bar"        (beats subcategory)
  3. source subcategory label     -> mapped category               (e.g. TGO column)
  4. product-name keyword rules   -> mapped category
  5. "Unknown"                    (never guesses a specific category)

Nothing here CREATES categories — it only returns existing MaterialCategory rows,
so loaders can no longer spawn nameless category rows by accident.
"""
import re

from pages.models.epd import MaterialCategory

# --- rebar (name-based, high confidence, checked before subcategory) --------
_REBAR_RE = re.compile(
    r"(deformed bar|round(ed)? bar|reinforc\w* bar|\brebar\b|reinforc\w* mesh|deformed .*wire mesh|wire mesh)",
    re.IGNORECASE,
)

# --- source subcategory label -> MaterialCategory name_en -------------------
# Keys are the exact labels used by source datasets (currently TGO's "Subcategory"
# column). Steel/Pipe are handled specially in _resolve_subcategory().
SUBCATEGORY_TO_CATEGORY = {
    "Insulation": "Insulation materials",
    "Concrete": "Mineral building products",
    "Cement": "Mineral building products",
    "Mortar": "Mineral building products",
    "Masonry": "Mineral building products",
    "Paint and Coating": "Coverings",
    "Flooring": "Coverings",
    "Ceiling": "Coverings",
    "Roofing": "Coverings",
    "Wall Finishing / Panel": "Coverings",
    "Door / Window / Opening": "Components for windows and curtain walls",
    "Chemical / Bonding / Adhesive": "Coverings",
}

# --- product-name keyword rules (first match wins; ORDER MATTERS) -----------
# Superset of the TGO and ECO-Platform rule sets. More specific rules first.
_NAME_RULES = [
    # Paint/coating/primer first: a coating IS a covering regardless of the
    # substrate named in the product (e.g. "aluminium wood primer" -> Coverings).
    (r"paint|primer|coating|enamel|varnish|lacquer|jotafloor|jotun|penguard|jotamastic|jotashield|hardtop|majestic|\bcool\b|semigloss|\bsheen\b|\bmatt\b|shield-1", "Coverings"),
    (r"structural steel|steel (sheet|coil|plate|pipe|product|bar|section|rod)|steel plate|steel sheet|steel coil|hot[- ]?rolled|cold[- ]?rolled|lip channel|\bpurlin\b|galvalume|alu[- ]?zinc|galvani[sz]ed steel|\bsteel\b", "Steel"),
    (r"precast|pre-cast", "Precast concrete elements and goods"),
    (r"alumin(i)?um|copper|\bbrass\b|\bzinc\b|\blead\b|\bmetal\b", "Metals"),
    (r"glass ?wool|rock ?wool|mineral wool|aeroflex|aero roof|\beps\b|\bxps\b|acoustic|cellulose fib|insulation", "Insulation materials"),
    (r"waterproof|membrane|bitumen|sealant|adhesive|bonding|\bgrout\b|chemical", "Coverings"),
    (r"tile|floor|ceiling|gyp(sum|board|roc)|plaster ?board|\bpanel\b|\bboard\b|fascia|fa[cç]ade|laminate|wallpaper|vinyl", "Coverings"),
    (r"concrete|cement|\bmortar\b|screed|\blean\b|aggregate|clinker", "Mineral building products"),
    (r"brick|\bblock\b|masonry|\baac\b|ceramic|clay", "Mineral building products"),
    (r"\bwood\b|timber|plywood|\bmdf\b|particle ?board|\bosb\b|bamboo", "Wood"),
    (r"\bu?pvc\b|\bcpvc\b|\bppr\b|hdpe|plastic|polymer|polyethylene|polypropylene|polybutylene", "Plastics"),
    (r"\bpipe\b|\bvalve\b|\bduct\b|fitting|hvac|plumb", "Building service engineering"),
    (r"window|\bdoor\b|glazing|glass|curtain wall", "Components for windows and curtain walls"),
]
_NAME_RULES = [(re.compile(p, re.IGNORECASE), name) for p, name in _NAME_RULES]

_cache = {}


def category_by_name(name_en):
    """Return the existing MaterialCategory for a name (shallowest level), cached."""
    if not name_en:
        return None
    if name_en not in _cache:
        _cache[name_en] = (
            MaterialCategory.objects.filter(name_en=name_en).order_by("level").first()
        )
    return _cache.get(name_en)


def _resolve_subcategory(subcategory, name):
    sc = str(subcategory).strip() if subcategory else ""
    if sc in ("Steel / Metal", "Wire / Welding Rod"):
        return category_by_name("Steel")
    if sc in ("Pipe", "Pipe-accessory"):
        if re.search(r"steel|cast iron", name, re.I):
            return category_by_name("Steel")
        if re.search(r"\bu?pvc\b|cpvc|\bppr\b|hdpe|plastic|polyethylene|polypropylene|polybutylene", name, re.I):
            return category_by_name("Plastics")
        return category_by_name("Building service engineering")
    return category_by_name(SUBCATEGORY_TO_CATEGORY.get(sc))


def resolve_by_name(name):
    """Product-name keyword match only. Returns a MaterialCategory or None."""
    nm = name or ""
    if _REBAR_RE.search(nm):
        return category_by_name("Steel reinforing bar")
    for rx, cname in _NAME_RULES:
        if rx.search(nm):
            return category_by_name(cname)
    return None


def resolve_category(classification_id=None, name="", subcategory=None):
    """Resolve an EPD to a MaterialCategory (see module docstring for order)."""
    if classification_id:
        cat = MaterialCategory.objects.filter(category_id=classification_id).first()
        if cat:
            return cat
    nm = name or ""
    if _REBAR_RE.search(nm):
        return category_by_name("Steel reinforing bar")
    if subcategory:
        cat = _resolve_subcategory(subcategory, nm)
        if cat:
            return cat
    for rx, cname in _NAME_RULES:
        if rx.search(nm):
            return category_by_name(cname)
    return category_by_name("Unknown")
