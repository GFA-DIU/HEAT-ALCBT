"""Rounding may never turn a real impact into zero.

Both impact accessors round to two decimals BEFORE dividing by the declared
amount. For an EPD declared per kilogram the stored figure is small, so two
decimals can erase it: 0.00106 becomes 0.00 and the material contributes no
carbon at all. 41 records in production were in that state.

An absent figure reads as "this material is free", which nobody questions,
rather than as an error. The floor stops that.

What these tests do NOT assert is that the rounding is gone. It is not: 628
other records still shift by 0.5 to 25 per cent, sand and aggregate among
them. That correction moves figures in 645 buildings and is a separate,
deliberate decision.
"""
from decimal import Decimal

import pytest

from pages.models.epd import EPD, _round_without_zeroing

pytestmark = pytest.mark.django_db


def make_epd(raw_amount=1):
    return EPD.objects.create(
        name="Test material", declared_unit="kg", declared_amount=raw_amount,
        type="official", names={})


# --- the floor itself ------------------------------------------------------

def test_a_value_that_would_round_to_zero_is_kept_whole():
    assert _round_without_zeroing(0.00105637) == 0.00105637


def test_a_tiny_negative_value_is_kept_too():
    """A negative A1-A3 happens where sequestration is declared. Erasing it
    would silently credit nothing instead of a small credit."""
    assert _round_without_zeroing(-0.0009) == -0.0009


def test_a_real_zero_stays_zero():
    """Fly ash and slag are legitimately zero at A1-A3. The floor must not
    invent a value for them."""
    assert _round_without_zeroing(0) == 0
    assert _round_without_zeroing(0.0) == 0


def test_ordinary_values_are_still_rounded():
    """The floor is narrow. Everything that does not vanish is unchanged, so
    no figure moves except the ones that were being erased."""
    assert _round_without_zeroing(0.009) == 0.01
    assert _round_without_zeroing(996.0) == 996.0
    assert _round_without_zeroing(2.3456) == 2.35


def test_a_value_just_above_the_threshold_still_rounds():
    assert _round_without_zeroing(0.005) == 0.01


# --- through the accessors -------------------------------------------------

def _give(epd, category, stage, value):
    from pages.models.epd import EPDImpact, Impact
    impact, _ = Impact.objects.get_or_create(
        impact_category=category, life_cycle_stage=stage)
    EPDImpact.objects.create(epd=epd, impact=impact, value=value)


def test_carbon_accessor_no_longer_reports_zero_for_a_real_value():
    epd = make_epd()
    _give(epd, "gwp", "a1a3", 0.00105637)
    assert epd.get_gwp_impact_sum("a1a3") != 0


def test_energy_accessor_no_longer_reports_zero_for_a_real_value():
    """penrt had the identical defect. Fixing one and not the other would
    leave the same bug in place under a different name."""
    epd = make_epd()
    _give(epd, "penrt", "a1a3", 0.00131847)
    assert epd.get_penrt_impact_sum("a1a3") != 0


def test_a_normal_carbon_figure_is_unchanged():
    epd = make_epd(raw_amount=1000)
    _give(epd, "gwp", "a1a3", 996.0)
    assert epd.get_gwp_impact_sum("a1a3") == Decimal("996") / Decimal(1000)
