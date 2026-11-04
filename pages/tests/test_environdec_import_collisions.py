"""Two ways the environdec importer could put a wrong carbon figure in BEAT.

1. NAME COLLISION. The importer keys records on (name, country). "TMT Bars"
   is the title of at least three different Indian declarations from three
   different steelmakers, and "Portland Pozzolana Cement (PPC)" is the title
   of both ACC's and Ambuja's. Without a guard, importing one overwrites
   another maker's record in place: the name stays, the manufacturer stays,
   and the carbon figure silently becomes somebody else's. Every building
   using that material changes, and nothing anywhere says so.

2. CATEGORY ORDER. "Portland Pozzolana Cement" contains the word "pozzolan",
   which is a power-station byproduct with a plausibility band of
   0.001-0.3 kgCO2e/kg. Both Indian PPC declarations sit at about 0.74, an
   ordinary cement figure, so filed as a byproduct they were refused as
   implausible. The opposite error is the dangerous one: a genuine pozzolan
   filed as cement would pass a band ten times too generous.
"""
import pytest

from pages.management.commands.import_environdec_epds import classify


# --- category order --------------------------------------------------------

def test_portland_pozzolana_cement_is_a_cement_not_a_byproduct():
    cat, material = classify("Portland Pozzolana Cement (PPC)")
    assert cat == "1.1.01", (
        "PPC resolved to %s; filed as a byproduct its band is 0.001-0.3 "
        "kgCO2e/kg and a real cement figure of 0.74 is refused" % cat)
    assert "cement" in material.lower()


def test_plain_pozzolan_is_still_a_byproduct():
    """The guard must not swallow the thing it is guarding against."""
    cat, _ = classify("Pozzolana powder")
    assert cat == "1.2.08"


def test_fly_ash_is_unaffected():
    assert classify("Fly ash")[0] == "1.2.08"


def test_slag_cement_is_still_a_cement():
    assert classify("Portland Slag Cement")[0] == "1.1.01"


def test_vnext_is_a_fibre_cement_board():
    """Visaka's declaration says fibre cement; the product title never does."""
    assert classify("Vnext Panel 50mm")[0] == "1.3.12"


# --- name collisions -------------------------------------------------------

@pytest.mark.django_db
def test_a_different_maker_does_not_overwrite_an_existing_record():
    from cities_light.models import Country

    from pages.models.epd import EPD, EPDType, MaterialCategory
    from pages.scripts.csv_import.utils import get_superuser
    from pages.management.commands.import_environdec_epds import Command

    india, _ = Country.objects.get_or_create(name="India",
                                             defaults={"code2": "IN"})
    cat = MaterialCategory.objects.filter(category_id="4.1.01").first()
    assert cat is not None, "4.1.01 ships with the database"

    before = EPD.objects.create(
        name="TMT Bars", country=india, type=EPDType.OFFICIAL,
        declared_unit="kg", declared_amount=1000, manufacturer="Peekay Steels",
        category=cat, names={}, created_by=get_superuser(),
        UUID="EPD-IES-0000001",
    )

    rows = [{
        "status": "OK", "country": "India", "material_group": "",
        "product": "TMT Bars", "manufacturer": "Prakash Ferrous Industries",
        "registration_number": "EPD-IES-0024699:001", "gwp_a1a3": "992",
        "declared_amount": "1000", "declared_unit": "kg",
        "url": "https://www.environdec.com/library/epd24699",
    }]
    created, updated, rejects = Command()._run(rows)

    assert not rejects, rejects
    assert (created, updated) == (1, 0), (
        "the second maker's declaration must create its own record, not "
        "update Peekay's")

    before.refresh_from_db()
    assert before.manufacturer == "Peekay Steels"
    assert not before.epdimpact_set.exists(), (
        "Peekay's record gained Prakash's carbon figure")
    assert EPD.objects.filter(country=india,
                              name__startswith="TMT Bars").count() == 2


@pytest.mark.django_db
def test_the_same_maker_still_updates_in_place():
    """The guard keys on the maker, so re-running an import is still
    idempotent and does not pile up duplicates."""
    from cities_light.models import Country

    from pages.models.epd import EPD
    from pages.management.commands.import_environdec_epds import Command

    Country.objects.get_or_create(name="India", defaults={"code2": "IN"})
    rows = [{
        "status": "OK", "country": "India", "material_group": "",
        "product": "TMT Bars", "manufacturer": "Prakash Ferrous Industries",
        "registration_number": "EPD-IES-0024699:001", "gwp_a1a3": "992",
        "declared_amount": "1000", "declared_unit": "kg",
        "url": "https://www.environdec.com/library/epd24699",
    }]
    first = Command()._run(rows)
    second = Command()._run(rows)
    assert first[0] == 1 and first[1] == 0
    assert second[0] == 0 and second[1] == 1, (
        "a re-run created a second copy instead of updating")
    assert EPD.objects.filter(name__startswith="TMT Bars").count() == 1
