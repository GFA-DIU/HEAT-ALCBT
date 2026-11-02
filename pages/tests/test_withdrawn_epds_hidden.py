"""A withdrawn EPD must not be offered in the material picker.

`draft` existed on every EPD but nothing acted on it, so marking a record
withdrawn changed nothing: it stayed selectable. That is how a fire door
published at 0.24 kgCO2e/m2, against 12 to 936 for comparable steel doors,
remained on offer after being identified as not credible.

What matters here is the pair: the record disappears from the LIST, and it
keeps existing. Deleting it would break any building already using it and
destroy the evidence if the retraction was wrong.
"""
import pytest

from pages.models.epd import EPD
from pages.views.assembly.epd_filtering import get_filtered_epd_list

pytestmark = pytest.mark.django_db


class FakeRequest:
    """get_filtered_epd_list only reads the method and the query dict."""

    method = "GET"
    GET = {}
    POST = {}


def make_epd(name, draft=False, unit="kg"):
    return EPD.objects.create(
        name=name, declared_unit=unit, declared_amount=1,
        type="official", names={}, draft=draft)


def listed():
    epds, _ = get_filtered_epd_list(FakeRequest())
    return {e.name for e in epds}


def test_a_normal_epd_is_offered():
    make_epd("Ordinary Portland Cement")
    assert "Ordinary Portland Cement" in listed()


def test_a_withdrawn_epd_is_not_offered():
    make_epd("Doors - Peneder - electronic fire resistance door (FN30)",
             draft=True)
    assert "Doors - Peneder - electronic fire resistance door (FN30)" \
        not in listed()


def test_withdrawing_one_does_not_hide_the_others():
    make_epd("Good cement")
    make_epd("Retracted cement", draft=True)
    names = listed()
    assert "Good cement" in names
    assert "Retracted cement" not in names


def test_a_withdrawn_epd_still_exists():
    """Excluded from the list, not deleted: a building already using it must
    keep working, and the record must be restorable."""
    epd = make_epd("Retracted door", draft=True)
    assert EPD.objects.filter(pk=epd.pk).exists()
    assert EPD.objects.get(pk=epd.pk).draft is True


def test_restoring_it_puts_it_back_on_offer():
    epd = make_epd("Temporarily retracted", draft=True)
    assert "Temporarily retracted" not in listed()
    epd.draft = False
    epd.save(update_fields=["draft"])
    assert "Temporarily retracted" in listed()
