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
    assert "plug load" in message.lower()
    assert "%" in message


def test_the_tolerance_matches_the_building_page():
    """views/building/building.py already uses 5% for its carriers-against-bill
    check. Two different ideas of a mismatch would be worse than either."""
    assert ENERGY_CARRIER_TOLERANCE == Decimal("0.05")
