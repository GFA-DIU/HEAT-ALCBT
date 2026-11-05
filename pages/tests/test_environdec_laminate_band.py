"""The high pressure laminate band, and what it does and does not prove.

BEAT's laminate leaf held no records at all, so unlike every other band in
the importer this one could not be derived from the catalogue. It rests
instead on three declarations from three unrelated makers - Luxotica at 1.04,
Century at 1.49 and Samrat at 1.70 kgCO2e/kg.

That is a weaker basis than a published reference and the code says so. It is
NOT the same as the circular case, which is deriving a band from one record
and then checking that same record against it: three competitors arriving
independently at the same range is evidence about the product, not about one
company's spreadsheet. What it cannot do is catch an error all three share.

The area band is looser again, because per square metre a laminate scales
with thickness and the market sells 0.7 mm to 6 mm.
"""
from pages.management.commands.import_environdec_epds import (
    AREA_BANDS, CATEGORY_RULES, MASS_BANDS, classify)

HPL = "6.5.01"


# --- the products that were blocked now classify ---------------------------

def test_the_six_indian_laminates_all_resolve_to_the_laminate_leaf():
    for product in ("High Pressure Laminates",                  # Luxotica
                    "Average High Pressure Laminate (HPL) -Compact panels",
                    "Samrat HPL",                               # Samrat
                    "HIGH PRESSURE LAMINATE",                   # Merino
                    "Thin Laminate",                            # Rushil
                    "Compact Laminate"):                        # Rushil
        assert classify(product)[0] == HPL, product


def test_compact_laminate_was_the_one_the_old_rule_missed():
    """The rule said "compact panel", which Rushil's "Compact Laminate" does
    not contain."""
    assert classify("Compact Laminate")[0] == HPL


# --- the bands admit the real figures and refuse nonsense ------------------

def test_the_mass_band_admits_all_three_makers():
    lo, hi = MASS_BANDS[HPL]
    for maker, value in (("Luxotica", 1.04), ("Century", 1.49),
                         ("Samrat", 1.6998)):
        assert lo <= value <= hi, maker


def test_the_mass_band_still_refuses_an_order_of_magnitude_error():
    lo, hi = MASS_BANDS[HPL]
    assert not (lo <= 0.015 <= hi), "a tonne read as a kilogram must refuse"
    assert not (lo <= 104.0 <= hi), "a misplaced decimal must refuse"


def test_the_area_band_spans_the_thicknesses_the_market_sells():
    lo, hi = AREA_BANDS[HPL]
    # 1mm Merino through 6mm Crown, the evidence named in the code comment.
    for thickness, value in ((1.0, 0.518), (0.8, 1.19), (0.7, 1.46),
                             (2.0, 3.12), (3.0, 4.76), (6.0, 10.1),
                             (6.0, 21.0)):
        assert lo <= value <= hi, "%smm at %s" % (thickness, value)


def test_the_area_band_is_not_unbounded():
    lo, hi = AREA_BANDS[HPL]
    assert not (lo <= 0.004 <= hi)
    assert not (lo <= 420.0 <= hi)


# --- the band must not be silently absent ----------------------------------

def test_both_bands_exist_so_the_leaf_is_checkable():
    """A category with no band is refused outright by the importer. These two
    entries are the whole reason the laminates can be imported, so their
    absence should fail loudly here rather than quietly in a later batch."""
    assert HPL in MASS_BANDS
    assert HPL in AREA_BANDS


def test_the_laminate_rule_sits_above_the_plain_board_rules():
    """"Compact panel" must not be caught by a later, broader board rule."""
    order = [i for i, (pattern, cat, _) in enumerate(CATEGORY_RULES)
             if cat == HPL]
    board = [i for i, (pattern, cat, _) in enumerate(CATEGORY_RULES)
             if cat in ("1.3.12", "1.3.13")]
    assert order and board
    assert min(order) < min(board)
