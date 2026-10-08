"""The GCCA Low Carbon Rating scale, as GCCA publishes it.

Thresholds transcribed from Table 1 at https://gccaepd.org/blog/lcr. The scale
has seven bands, AA to F, and stops at F - there is no G. An earlier version of
this module omitted AA and invented a G, so a near-zero product would have been
reported as A and two EPDs carried a letter the scheme does not define.
"""
import pytest

from pages.scripts.Label_mapping.gcca_rating import (
    GCCA_BANDS, GCCA_THRESHOLDS, rate, strength_to_mxx)


def test_the_scale_is_AA_to_F_with_no_G():
    assert GCCA_BANDS == ["AA", "A", "B", "C", "D", "E", "F"]
    assert "G" not in GCCA_BANDS
    assert all(len(v) == len(GCCA_BANDS) for v in GCCA_THRESHOLDS.values())


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


def test_above_the_top_of_F_is_unrated_not_G():
    """968 kgCO2e/m3 is off the scale; GCCA defines no band for it."""
    assert rate(303, 20) is None
    assert rate(968, 50) is None


def test_off_table_strength_classes_are_unrated():
    """GCCA publishes columns for M20/25/30/35/40/50 only."""
    assert strength_to_mxx("Concrete C12/15") is None   # cylinder 12
    assert strength_to_mxx("Concrete C45/55") is None   # cylinder 45
    assert strength_to_mxx("Concrete C20/25") == 20
    assert strength_to_mxx("JSW M30 Ready Mixed Concrete") == 30


def test_a_strength_range_is_too_ambiguous_to_rate():
    assert strength_to_mxx("Ready-mix concrete 200-300 KSC") is None
