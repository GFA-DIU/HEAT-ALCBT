"""A5.2 — energy used on site during construction.

    A5.2 = SUM( kWh of each carrier x that carrier's kgCO2e/kWh ) / GFA

The carbon factor is the EPD's own B6 figure. That is not a shortcut: BEAT's
energy EPDs declare the carbon of delivering one kWh of that carrier in that
country, and a kWh of grid electricity has the same footprint whether a tower
crane draws it in month four or a lift draws it in year ten. Only the life
cycle stage it is reported under changes.

What this is NOT
----------------
RICS WLCA 2nd ed. splits A5 four ways. BEAT covers one of them:

    A5.1  pre-construction demolition   NOT MODELLED
    A5.2  construction activities       this module
    A5.3  construction waste            pages/scripts/a4a5/compute.py (a5w)
    A5.4  worker transport              NOT MODELLED (optional under RICS)

A building with no site energy entered reports **zero and says so**. There is
no default benchmark, because no sourced kWh/m2 figure exists for these five
countries and inventing one would put an unsourced number inside a total that
looks measured.
"""
from decimal import Decimal

from pages.scripts.a4a5 import fuels


def _factor_per_kwh(epd):
    """kgCO2e per kWh for an energy EPD, from its B6 declaration."""
    try:
        v = epd.get_gwp_impact_sum("b6")
    except Exception:
        return None
    if not v:
        # some carriers declare their operational carbon under A1-A3 instead
        try:
            v = epd.get_gwp_impact_sum("a1a3")
        except Exception:
            return None
    return v or None


def construction_energy(products, floor_area):
    """A5.2 for one building.

    ``products`` is an iterable of ConstructionProduct (or anything with
    ``epd``, ``quantity`` and ``input_unit``). Returns
    ``(a5_2_per_m2, rows, notes)``:

    * ``a5_2_per_m2`` Decimal, kgCO2e/m2
    * ``rows``        one dict per entry, with the conversion spelled out
    * ``notes``       anything the user needs to know to read the number
    """
    fa = Decimal(str(floor_area or 0))
    rows, notes, total = [], [], Decimal("0")

    for p in products:
        epd = p.epd
        kwh, how = fuels.to_kwh(p.quantity, p.input_unit, epd.name)
        factor = _factor_per_kwh(epd)

        row = {
            "id": getattr(p, "id", None),
            "name": epd.name,
            "quantity": float(p.quantity) if p.quantity is not None else None,
            "unit": p.input_unit,
            "kwh": round(kwh, 1) if kwh is not None else None,
            "conversion": how,
            "factor_kgco2e_per_kwh": float(factor) if factor else None,
            "kgco2e": None,
            "a5_2": None,
            "problem": None,
        }

        if kwh is None:
            row["problem"] = how
        elif factor is None:
            row["problem"] = "no B6 carbon factor on this EPD"
        else:
            kg = Decimal(str(kwh)) * Decimal(str(factor))
            row["kgco2e"] = float(round(kg, 2))
            if fa > 0:
                per_m2 = kg / fa
                row["a5_2"] = float(round(per_m2, 4))
                total += per_m2
            else:
                row["problem"] = "no floor area"

        if fuels.describes_assumed_density(epd.name) and (p.input_unit or "").lower() == "l":
            notes.append("%s was converted from litres using an assumed density "
                         "(see pages/scripts/a4a5/fuels.py)." % epd.name)
        rows.append(row)

    if not rows:
        notes.append("No construction site energy entered, so A5.2 is reported "
                     "as zero. The upfront total is understated by whatever the "
                     "site actually used.")

    problems = [r for r in rows if r["problem"]]
    if problems:
        notes.append("%d entr%s could not be counted; see the rows marked below."
                     % (len(problems), "y" if len(problems) == 1 else "ies"))

    return total, rows, notes


def scope_note():
    """One line stating what A5 does and does not include, for the UI."""
    return ("A5 here covers construction waste (A5.3) and site energy (A5.2). "
            "Pre-construction demolition (A5.1) and worker transport (A5.4) are "
            "not included.")
