"""Converting a fuel quantity as a site records it into kWh.

Construction sites record what they bought: litres of diesel on a delivery
note, kilograms of LPG on a cylinder, kWh on an electricity meter. BEAT's
energy EPDs are all declared **per kWh**, so anything that is not already in
kWh has to be converted before it can meet a carbon factor.

That conversion needs a net calorific value, and for liquids a density as well.
Both are stated here rather than buried in a calculation, because a wrong NCV
moves the answer silently and nobody would see it.

Provenance
----------
**NCVs: IPCC 2006 Guidelines for National Greenhouse Gas Inventories, Volume 2
(Energy), Chapter 1, Table 1.2** — default net calorific values, TJ/Gg, which
is numerically MJ/kg. These are the same defaults TGO and Smart Freight Centre
cite for their own factors, so BEAT is converting on the same basis the source
factors were built on.

**Densities: typical commercial values, NOT from IPCC.** ⚠️ IPCC publishes
NCVs per unit mass; it does not publish densities. The figures below are the
ordinary trade values used to turn litres into kilograms. They are the weakest
link in this module and are the thing to source properly — the SFC study cites
BPCL's conversion table for exactly this purpose, which would be a reasonable
place to take them from.

A fuel whose density is marked as assumed can still be entered in **kg**, which
needs no density at all.
"""

MJ_PER_KWH = 3.6

# carrier -> (net calorific value MJ/kg, density kg/litre or None, note)
# density None = this fuel is not sold by volume, so no density is needed.
FUEL_ENERGY = {
    "diesel":        (43.0, 0.832, "IPCC 2006 gas/diesel oil; density assumed"),
    "gasoline":      (44.3, 0.740, "IPCC 2006 motor gasoline; density assumed"),
    "kerosene":      (43.8, 0.800, "IPCC 2006 other kerosene; density assumed"),
    "fuel_oil":      (40.4, 0.980, "IPCC 2006 residual fuel oil; density assumed"),
    "lpg":           (47.3, None,  "IPCC 2006 LPG; sold by mass"),
    "natural_gas":   (48.0, None,  "IPCC 2006 natural gas; sold by mass or MJ"),
    "coal":          (25.8, None,  "IPCC 2006 other bituminous coal"),
    "lignite":       (11.9, None,  "IPCC 2006 lignite"),
    "anthracite":    (26.7, None,  "IPCC 2006 anthracite"),
    "charcoal":      (29.5, None,  "IPCC 2006 charcoal"),
    "wood":          (15.6, None,  "IPCC 2006 wood/wood waste"),
}

# How an EPD name maps onto one of the carriers above. Matched case-insensitively
# on the EPD name, longest key first so "fuel oil" wins over "oil".
_NAME_TO_CARRIER = [
    ("liquefied petroleum gas", "lpg"),
    ("heavy fuel oil", "fuel_oil"),
    ("light fuel oil", "fuel_oil"),
    ("natural gas", "natural_gas"),
    ("firewood", "wood"),
    ("fuel wood", "wood"),
    ("anthracite", "anthracite"),
    ("charcoal", "charcoal"),
    ("kerosene", "kerosene"),
    ("gasoline", "gasoline"),
    ("lignite", "lignite"),
    ("petrol", "gasoline"),
    ("diesel", "diesel"),
    ("lpg", "lpg"),
    ("coal", "coal"),
    ("wood", "wood"),
]


def carrier_for(epd_name: str):
    """Which fuel an EPD is, or None if it is not a fuel we can convert."""
    name = (epd_name or "").lower()
    for token, carrier in _NAME_TO_CARRIER:
        if token in name:
            return carrier
    return None


def to_kwh(quantity, unit: str, epd_name: str):
    """Convert a recorded fuel quantity to kWh.

    Returns (kwh, note). ``kwh`` is None when the conversion cannot be made
    honestly — an unknown fuel, or litres of something with no density — and
    the note says why, so the caller can show that rather than a wrong number.
    """
    if quantity is None:
        return None, "no quantity"
    q = float(quantity)
    u = (unit or "").lower()

    if u == "kwh":
        return q, "entered in kWh"
    if u == "mj":
        return q / MJ_PER_KWH, "MJ / 3.6"

    carrier = carrier_for(epd_name)
    if carrier is None:
        return None, "not a fuel this module can convert: %r" % (epd_name or "")

    ncv, density, source = FUEL_ENERGY[carrier]

    if u in ("kg", "ton"):
        kg = q * (1000.0 if u == "ton" else 1.0)
        return kg * ncv / MJ_PER_KWH, "%g kg x %g MJ/kg / 3.6  [%s]" % (kg, ncv, source)

    if u == "l":
        if density is None:
            return None, ("%s is not sold by volume here - enter it in kg"
                          % carrier.replace("_", " "))
        kg = q * density
        return (kg * ncv / MJ_PER_KWH,
                "%g l x %g kg/l x %g MJ/kg / 3.6  [%s]" % (q, density, ncv, source))

    return None, "cannot convert %r to kWh" % u


def describes_assumed_density(epd_name: str) -> bool:
    """True when converting this fuel from litres leans on an assumed density."""
    carrier = carrier_for(epd_name)
    if carrier is None:
        return False
    _ncv, density, source = FUEL_ENERGY[carrier]
    return density is not None and "assumed" in source
