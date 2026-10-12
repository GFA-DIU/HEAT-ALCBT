"""The GCCA Low Carbon Rating scale for concrete, as GCCA publishes it.

Eight bands. GCCA's EN 206 report states it plainly: "There are 8 ratings
(AA to G)" - AA near-zero, A to F equally spaced, and "G - Open ended band",
added so every concrete can be allocated a band whatever its GWP.
https://gccassociation.org/wp-content/uploads/2025/11/GCCA_EN206-Report.pdf

Thresholds from Table 1 at https://gccaepd.org/blog/lcr. Note that page says
"seven ratings, from AA to F" - that is the *cement* scale. Concrete has the
extra open-ended band, and this module had G removed on the strength of that
sentence before the EN 206 report was checked.
"""
import pytest

from pages.scripts.Label_mapping.gcca_rating import (
    GCCA_BANDS, GCCA_THRESHOLDS, rate, strength_to_mxx)


def test_the_scale_is_AA_to_G():
    assert GCCA_BANDS == ["AA", "A", "B", "C", "D", "E", "F", "G"]
    # G is open-ended, so it has no threshold row of its own
    assert all(len(v) == len(GCCA_BANDS) - 1 for v in GCCA_THRESHOLDS.values())


@pytest.mark.parametrize("mxx, gwp, expected", [
    # top-of-band values from the published table, M20 column
    (20, 21, "AA"), (20, 68, "A"), (20, 115, "B"), (20, 161, "C"),
    (20, 208, "D"), (20, 255, "E"), (20, 302, "F"),
    # just inside the next band up
    (20, 22, "A"), (20, 69, "B"),
    # the M50 column
    (50, 36, "AA"), (50, 113, "A"), (50, 500, "F"),
])
def test_bands_match_the_published_table(mxx, gwp, expected):
    assert rate(gwp, mxx) == expected


def test_above_the_top_of_F_is_G():
    """G is the open-ended band - every concrete gets a rating."""
    assert rate(303, 20) == "G"
    assert rate(968, 50) == "G"


def test_unrateable_means_the_strength_class_is_off_table_not_high_carbon():
    """None signals an unknown strength, never "too carbon-heavy to rate"."""
    assert rate(501, 45) is None      # M45 is not a published column at all
    assert rate(501, 50) == "G"       # M50 is, so a heavy mix still gets G
    assert rate(500, 50) == "F"       # 500 is exactly the top of F, not G


def test_off_table_strength_classes_are_unrated():
    """GCCA publishes columns for M20/25/30/35/40/50 only."""
    assert strength_to_mxx("Concrete C12/15") is None   # cylinder 12
    assert strength_to_mxx("Concrete C45/55") is None   # cylinder 45
    assert strength_to_mxx("Concrete C20/25") == 20
    assert strength_to_mxx("JSW M30 Ready Mixed Concrete") == 30


def test_a_strength_range_is_too_ambiguous_to_rate():
    assert strength_to_mxx("Ready-mix concrete 200-300 KSC") is None
