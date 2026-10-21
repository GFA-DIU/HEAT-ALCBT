"""The import refuses carriers that do not account for the file's own systems.

A building reported two operational carbon figures at once: the page headline
read 588.0 kgCO2eq/m2 over 50 years, computed from 48,000 kWh of energy
carriers, while the Systems tab read 1,494.30 kgCO2eq/m2/yr, computed from
4,603,164 kWh of modelled systems. Both were correct arithmetic on different
inputs and nothing said so.
"""
import json
from decimal import Decimal

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.urls import reverse

from pages.models.building import Building, OperationalProduct
from pages.views.building.import_building import ENERGY_CARRIER_TOLERANCE

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    User = get_user_model()
    u = User.objects.create_user("carriers", "carriers@example.com", "pw123456")
    EmailAddress.objects.create(
        user=u, email="carriers@example.com", verified=True, primary=True)
    return u


@pytest.fixture
def cambodia(db):
    from cities_light.models import Country
    return Country.objects.get_or_create(
        code2="KH",
        defaults={"name": "Cambodia", "continent": "AS", "slug": "cambodia"},
    )[0]


@pytest.fixture
def electricity(db, cambodia):
    """An energy-carrier EPD. The lookup filters on category 9.2, so the
    category hierarchy is part of what makes it findable."""
    from pages.models.epd import EPD, EPDType, MaterialCategory, Unit

    root, _ = MaterialCategory.objects.get_or_create(
        category_id="9", defaults={"name_en": "Others", "name_de": "Others",
                                   "level": 1})
    parent, _ = MaterialCategory.objects.get_or_create(
        category_id="9.2", defaults={"name_en": "Energy carrier",
                                     "name_de": "Energietraeger", "level": 2,
                                     "parent": root})
    child, _ = MaterialCategory.objects.get_or_create(
        category_id="9.2.elec", defaults={"name_en": "Electricity",
                                          "name_de": "Strom", "level": 3,
                                          "parent": parent})
    return EPD.objects.create(
        name="Electricity", names=[{"value": "Electricity", "lang": "en"}],
        UUID="test-electricity-kh", declared_unit=Unit.KWH, conversions=[],
        type=EPDType.GENERIC, category=child, country=cambodia,
        public=True, draft=False, declared_amount=1,
    )


@pytest.fixture
def building(db, user, cambodia, electricity):
    """A building whose four modelled systems use 100,000 kWh/yr."""
    from pages.models.building_operation.energy_summary import EnergySummary

    b = Building.objects.create(
        name="Carrier Check", total_floor_area=1000.0,
        created_by=user, country=cambodia,
    )
    EnergySummary.objects.create(
        building=b,
        cooling_kwh=Decimal("60000"), ventilation_kwh=Decimal("20000"),
        lighting_kwh=Decimal("15000"), hot_water_kwh=Decimal("5000"),
    )
    return b


def _post(client, building, rows):
    return client.post(
        reverse("import_energy_carriers"),
        data=json.dumps({"building_uuid": str(building.uuid), "rows": rows}),
        content_type="application/json",
    )


def _row(kwh):
    return ["electricity", "grid", str(kwh), "kwh"]


def test_the_reference_is_the_entered_systems(building):
    """Not the building total: the plug-load default and an estimated lift are
    derived after the file is read, so nobody filling a sheet can know them."""
    assert building.energy_summary.entered_systems_kwh == Decimal("100000")


def test_carriers_that_account_for_the_systems_import(client, user, building):
    client.force_login(user)
    resp = _post(client, building, [_row(100000)])
    assert resp.status_code == 200, resp.content[:400]
    assert OperationalProduct.objects.filter(building=building).count() == 1


def test_the_real_case_is_refused(client, user, building):
    """48,000 against 4,603,164 was 99% short."""
    client.force_login(user)
    resp = _post(client, building, [_row(1000)])
    assert resp.status_code == 400
    body = resp.json()["errors"]
    assert "energy carriers" in body
    message = body["energy carriers"]["quantity"][0]
    assert "100,000" in message and "1,000" in message
    assert OperationalProduct.objects.filter(building=building).count() == 0, \
        "nothing may be saved when the import is refused"


@pytest.mark.parametrize("kwh,accepted", [
    (100000, True),      # exact
    (104000, True),      # +4%
    (96000, True),       # -4%
    (106000, False),     # +6%
    (94000, False),      # -6%
])
def test_the_five_percent_tolerance(client, user, building, kwh, accepted):
    client.force_login(user)
    resp = _post(client, building, [_row(kwh)])
    assert (resp.status_code == 200) is accepted, (kwh, resp.status_code)


def test_several_carriers_are_summed(client, user, building):
    client.force_login(user)
    resp = _post(client, building, [_row(60000), _row(40000)])
    assert resp.status_code == 200, resp.content[:400]


def test_a_file_with_no_carriers_is_allowed(client, user, building):
    """A purely modelled building has no bills. Blocking it would stop a
    normal case; carbon then comes from the systems."""
    client.force_login(user)
    resp = _post(client, building, [])
    assert resp.status_code == 200, resp.content[:400]


def test_a_building_with_no_systems_is_not_blocked(client, user, cambodia, electricity):
    """Nothing to compare against, so the check cannot say anything."""
    b = Building.objects.create(
        name="No systems", total_floor_area=500.0,
        created_by=user, country=cambodia,
    )
    client.force_login(user)
    resp = _post(client, b, [_row(12345)])
    assert resp.status_code == 200, resp.content[:400]


def test_the_message_says_what_is_excluded(client, user, building):
    """The user must not go looking for the plug load in their own figures."""
    client.force_login(user)
    message = _post(client, building, [_row(1)]).json()[
        "errors"]["energy carriers"]["quantity"][0]
    low = message.lower().replace("plug-load", "plug load")
    assert "plug load" in low
    assert "not counted" in low, "it must say the estimates are excluded"
    assert "%" in message


def test_the_tolerance_matches_the_building_page():
    """views/building/building.py already uses 5% for its carriers-against-bill
    check. Two different ideas of a mismatch would be worse than either."""
    assert ENERGY_CARRIER_TOLERANCE == Decimal("0.05")


# --- the two checks must ask for the same number ---------------------------
#
# They did not. The data-entry page compared carriers against total_kwh and
# the import against the entered systems, and on a test building those were
# 432,432 and 326,364 - a gap of 106,068 kWh that was entirely a 7.5% lift
# estimate and a 25% plug-load default. The carriers could not satisfy both.

def test_the_page_target_is_the_entered_systems(building):
    """Not total_kwh. The target must hold only what the user supplied."""
    import inspect

    from pages.views.building import add_building_steps

    src = inspect.getsource(add_building_steps)
    assert "total_annual_energy_consumption = energy_summary.entered_systems_kwh" in src
    assert "total_annual_energy_consumption = energy_summary.total_kwh" not in src


def test_the_estimates_are_excluded_from_the_target(building):
    """The building's own total still includes them - only the target does
    not, so operational carbon is unchanged."""
    es = building.energy_summary
    assert es.entered_systems_kwh == Decimal("100000")
    assert es.total_kwh > es.entered_systems_kwh
    assert es.plug_load_basis == "estimated"


def test_a_metered_plug_load_joins_the_target(building):
    """"User while re-entering can enter them manually if they have the
    value" - a real figure must count, a percentage must not."""
    es = building.energy_summary
    es.plug_load_kwh = Decimal("20000")
    es.save()
    es.refresh_from_db()
    assert es.plug_load_basis == "metered"
    assert es.entered_systems_kwh == Decimal("120000")


def test_a_percentage_plug_load_does_not(building):
    """Scaled off the systems rather than measured, so requiring a bill to
    match it would make the assumption the thing being tested."""
    es = building.energy_summary
    es.plug_load_percent = Decimal("25")
    es.save()
    es.refresh_from_db()
    assert es.plug_load_basis == "percent"
    assert es.entered_systems_kwh == Decimal("100000")


def test_the_plug_base_never_contains_the_plug_load(building):
    """plug_load_base is the base a percentage is taken OF. Folding the plug
    figure into it would take a percentage of itself."""
    es = building.energy_summary
    es.plug_load_kwh = Decimal("20000")
    es.save()
    es.refresh_from_db()
    assert es.plug_load_base == Decimal("100000")
    assert es.entered_systems_kwh == Decimal("120000")


def test_a_metered_plug_load_changes_what_imports(client, user, building):
    """With 20,000 kWh of metered plug load the target becomes 120,000, so
    the carriers that passed before are now 17% short."""
    es = building.energy_summary
    es.plug_load_kwh = Decimal("20000")
    es.save()
    client.force_login(user)
    assert _post(client, building, [_row(100000)]).status_code == 400
    assert _post(client, building, [_row(120000)]).status_code == 200


def test_the_message_breaks_the_total_down(client, user, building):
    """A bare total leaves the user to work out which sheet is responsible."""
    client.force_login(user)
    message = _post(client, building, [_row(1)]).json()[
        "errors"]["energy carriers"]["quantity"][0]
    for name, value in (("Cooling", "60,000"), ("Ventilation", "20,000"),
                        ("Lighting", "15,000"), ("Hot water", "5,000")):
        assert name in message, message
        assert value in message, message


def test_the_message_does_not_list_an_estimated_lift(client, user, building):
    """It is not in the target, so naming it would send the user looking for
    a number that does not count."""
    client.force_login(user)
    message = _post(client, building, [_row(1)]).json()[
        "errors"]["energy carriers"]["quantity"][0]
    assert "Lift" not in message
