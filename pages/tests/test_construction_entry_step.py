"""Entering construction-phase energy in the Operational Data Entry step.

The step carries two phases because they share the same carriers and the same
picker: annual running energy (B6) and the one-off total used while the
building was built (A5.2). They are tabs rather than a one-time choice, since
a project may have records for both.

What these tests exist to protect is the separation. The two phases sit on one
page and post to one endpoint, so the obvious failure is site diesel leaking
into the building's annual running energy, or an operational save wiping the
construction entries.
"""
import uuid as uuid_lib

import pytest
from django.urls import reverse

from pages.models.building import Building, ConstructionProduct, OperationalProduct
from pages.models.epd import EPD


pytestmark = pytest.mark.django_db


def _verified_user(django_user_model, username, email):
    """allauth bounces unverified users to /accounts/verify-email/."""
    from allauth.account.models import EmailAddress
    user = django_user_model.objects.create_user(
        username=username, email=email, password="x")
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


@pytest.fixture
def building_with_owner(django_user_model):
    user = _verified_user(django_user_model, "owner", "owner@example.com")
    building = Building.objects.create(
        name="Test building", total_floor_area=500, created_by=user)
    return building, user


def _energy_epd(name, gwp_per_kwh):
    """An energy carrier EPD declared per kWh, with its B6 carbon."""
    from pages.models.epd import EPDImpact, Impact
    epd = EPD.objects.create(
        UUID=uuid_lib.uuid4(), name=name, names={"en": name},
        type="generic", declared_amount=1, declared_unit="kwh")
    impact, _ = Impact.objects.get_or_create(
        impact_category="gwp", life_cycle_stage="b6")
    EPDImpact.objects.create(epd=epd, impact=impact, value=gwp_per_kwh)
    return epd


@pytest.fixture
def energy_epds():
    return _energy_epd("Electricity", 0.59), _energy_epd("Diesel", 0.30)


def _post(client, building, pairs):
    """pairs: [(epd, quantity, unit, description, stamp)]"""
    data = {"action": "save_constr_products", "building_uuid": str(building.uuid)}
    for epd, qty, unit, desc, stamp in pairs:
        data["constr_%s_quantity_%s" % (epd.id, stamp)] = str(qty)
        data["constr_%s_unit_%s" % (epd.id, stamp)] = unit
        data["constr_%s_description_%s" % (epd.id, stamp)] = desc
    return client.post(reverse("building_step_operational"), data)


def test_saving_site_energy_creates_construction_products(
        client, building_with_owner, energy_epds):
    building, user = building_with_owner
    elec, diesel = energy_epds
    client.force_login(user)

    r = _post(client, building, [
        (elec, 18000, "kwh", "site power", "111"),
        (diesel, 4200, "l", "crane", "222"),
    ])
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["saved"] == 2
    assert ConstructionProduct.objects.filter(building=building).count() == 2


def test_site_energy_never_lands_in_operational_products(
        client, building_with_owner, energy_epds):
    """The whole point of a separate model: site diesel is not running energy."""
    building, user = building_with_owner
    elec, diesel = energy_epds
    client.force_login(user)

    before = OperationalProduct.objects.filter(building=building).count()
    _post(client, building, [(diesel, 4200, "l", "generator", "333")])
    assert OperationalProduct.objects.filter(building=building).count() == before


def test_the_response_carries_the_a5_2_figure_so_the_banner_can_update(
        client, building_with_owner, energy_epds):
    building, user = building_with_owner
    elec, _diesel = energy_epds
    client.force_login(user)

    body = _post(client, building, [(elec, 1000, "kwh", "", "444")]).json()
    assert "a5_2_per_m2" in body
    assert body["a5_2_per_m2"] > 0
    assert body["rows"][0]["kwh"] == 1000.0


def test_saving_again_replaces_rather_than_duplicates(
        client, building_with_owner, energy_epds):
    building, user = building_with_owner
    elec, _ = energy_epds
    client.force_login(user)

    _post(client, building, [(elec, 1000, "kwh", "", "555")])
    _post(client, building, [(elec, 2000, "kwh", "", "666")])
    rows = ConstructionProduct.objects.filter(building=building)
    assert rows.count() == 1
    assert float(rows.first().quantity) == 2000.0


def test_a_zero_or_missing_quantity_is_skipped_not_saved(
        client, building_with_owner, energy_epds):
    building, user = building_with_owner
    elec, _ = energy_epds
    client.force_login(user)

    body = _post(client, building, [(elec, 0, "kwh", "", "777")]).json()
    assert body["saved"] == 0
    assert ConstructionProduct.objects.filter(building=building).count() == 0


def test_another_users_building_cannot_be_written_to(
        client, building_with_owner, energy_epds, django_user_model):
    building, _owner = building_with_owner
    elec, _ = energy_epds
    intruder = _verified_user(
        django_user_model, "intruder", "intruder@example.com")
    client.force_login(intruder)

    r = _post(client, building, [(elec, 999, "kwh", "", "888")])
    assert r.status_code == 400
    assert ConstructionProduct.objects.filter(building=building).count() == 0


def test_an_unknown_building_is_rejected(client, building_with_owner, energy_epds):
    _building, user = building_with_owner
    elec, _ = energy_epds
    client.force_login(user)
    r = client.post(reverse("building_step_operational"), {
        "action": "save_constr_products",
        "building_uuid": str(uuid_lib.uuid4()),
        "constr_%s_quantity_1" % elec.id: "10",
        "constr_%s_unit_1" % elec.id: "kwh",
    })
    assert r.status_code == 400
