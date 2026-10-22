"""Drive the shipped template through the real import endpoints.

Every bug found in this round survived because the checks stopped one layer
short of where the error messages are produced. Parsers were tested, then
forms; the endpoints were only ever exercised with hand-written rows that
matched the parser rather than the template.

This reads static/docs/import-template.xlsx, builds each payload the way
import-dialog.html builds it, and posts it. If a sheet and its endpoint
ever disagree again, this fails instead of the user - and the example we hand
people cannot quietly become one BEAT would reject.
"""
import csv
import json
import warnings

import openpyxl
import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.urls import reverse

from pages.models.building import Building

pytestmark = pytest.mark.django_db

# One file now, filled in as a worked example. A blank template plus a
# separate example was tried and only raised the question of which to open.
TEMPLATE = "static/docs/import-template.xlsx"


# --- reading the template the way the browser does -------------------------

def _sheet_rows(name):
    """XLSX.utils.sheet_to_json(ws, {header: 1, defval: null})."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(TEMPLATE, data_only=True)
    if name not in wb.sheetnames:
        return []
    return [
        [None if v is None else str(v).strip() for v in row]
        for row in wb[name].iter_rows(min_row=1, values_only=True)
    ]


def _cooling(name):
    """slice(1), then drop rows whose only content is a yes/no default."""
    return [
        r for r in _sheet_rows(name)[1:]
        if any(c not in (None, "") and str(c).lower() not in ("none", "no", "yes")
               for c in r)
    ]


def _ventilation(name):
    """slice(1), then require a unit count in column 0."""
    return [
        r for r in _sheet_rows(name)[1:]
        if r and r[0] not in (None, "") and str(r[0]).lower() != "none"
    ]


def _simple(name, index=0):
    return [
        r for r in _sheet_rows(name)[1:]
        if len(r) > index and r[index] not in (None, "")
    ]


def _structural():
    """slice(2) - this sheet has a two-row header - keeping component or EPD."""
    return [
        r for r in _sheet_rows("Structural Components - By Comp")[2:]
        if (len(r) > 1 and r[1] not in (None, ""))
        or (len(r) > 8 and r[8] not in (None, ""))
    ]


# --- fixtures --------------------------------------------------------------

@pytest.fixture
def user(db):
    User = get_user_model()
    u = User.objects.create_user(
        "tplimport", "tplimport@example.com", "testpass123")
    EmailAddress.objects.create(
        user=u, email="tplimport@example.com", verified=True, primary=True)
    return u


@pytest.fixture
def cambodia(db):
    from cities_light.models import Country
    return Country.objects.get_or_create(
        code2="KH",
        defaults={"name": "Cambodia", "continent": "AS", "slug": "cambodia"},
    )[0]


@pytest.fixture
def building(db, user, cambodia):
    return Building.objects.create(
        name="Template Import Test", total_floor_area=1000.0,
        created_by=user, country=cambodia,
    )


@pytest.fixture
def space_types(db):
    """Loaded by a management command, not by migration 0054."""
    from pages.models.building_operation.lighting import LightingSpaceType, RoomType

    with open("pages/data/lighting_space_types.csv", newline="",
              encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            LightingSpaceType.objects.get_or_create(
                code=row["code"].strip(),
                defaults={"name": row["name"].strip(),
                          "sort_order": int(row["sort_order"] or 100)},
            )
    for code, label in RoomType.choices:
        LightingSpaceType.objects.get_or_create(
            code=code, defaults={"name": str(label), "legacy": True})


def _post(client, url_name, payload):
    return client.post(reverse(url_name), data=json.dumps(payload),
                       content_type="application/json")


def _check(resp, what):
    assert resp.status_code == 200, (
        "%s: HTTP %s - %s" % (what, resp.status_code, resp.content[:400]))
    body = resp.json()
    assert not body.get("errors"), "%s: %s" % (what, body["errors"])
    return body


# --- the template's own example rows ---------------------------------------

def test_the_split_ac_example_imports(client, user, building):
    rows = _cooling("Cooling System - Split air cond")
    assert rows, "the example ships filled Split AC rows"
    client.force_login(user)
    body = _check(_post(client, "import_cooling_systems", {
        "building_uuid": str(building.uuid),
        "systems": [{"tab": "split ac", "rows": rows}],
    }), "split ac")
    assert body["saved_count"] == len(rows)


def test_the_cassette_example_imports(client, user, building):
    rows = _ventilation("Ventillation System - CeilingWa")
    assert rows, "the example ships a filled ceiling/wall fan row"
    client.force_login(user)
    _check(_post(client, "import_ventilation_systems", {
        "building_uuid": str(building.uuid),
        "systems": [{"tab": "ceilingwa", "rows": rows}],
    }), "cassette")


def test_the_led_example_imports(client, user, building, space_types):
    rows = _simple("Lightning System - LED")
    assert rows, "the example ships filled LED rows"
    client.force_login(user)
    _check(_post(client, "import_lighting_systems", {
        "building_uuid": str(building.uuid),
        "systems": [{"tab": "led", "rows": rows}],
    }), "led")


def test_the_water_heater_example_imports(client, user, building):
    """Its efficiency column is a percentage. The example used to say 3, which
    divided the energy by 0.03 and reported 33x the truth."""
    rows = _simple("Hot water System - Water Heater")
    assert rows, "the example ships a filled water heater row"
    client.force_login(user)
    _check(_post(client, "import_hot_water_systems", {
        "building_uuid": str(building.uuid),
        "systems": [{"tab": "water-heater", "rows": rows}],
    }), "water heater")

    from pages.models.building_operation import HotWaterSystem
    hws = HotWaterSystem.objects.filter(building=building).first()
    assert hws is not None
    # 6 units x 3.5 kW x 2 h/day x 6 d x 50 wk = 12,600 kWh before efficiency,
    # and 12,600 / 0.95 = 13,263. With an efficiency of 3 it would be
    # 12,600 / 0.03 = 420,000: the same row, 33x over.
    energy = hws.total_energy_consumption_kwh_per_year
    assert energy is not None, (
        "no energy was computed - the guard in _calc_hws_energy refused the "
        "efficiency, which means the example's value is not a percentage")
    assert 13000 < float(energy) < 13500, (
        "expected about 13,263 kWh/yr, got %s - the efficiency column was read "
        "as a level rather than a percentage" % energy)


def test_the_structural_example_imports(client, user, building, cambodia):
    """9 of these 13 rows named a building component that migration 0046
    removed."""
    from pages.models.assembly import AssemblyCategory
    from pages.models.epd import EPD, EPDType, Unit

    for n in ("Foundations", "Beams & Slabs", "Ground Floor", "Roof",
              "Columns", "Finishes"):
        AssemblyCategory.objects.get_or_create(name=n)
    for n in ("Ready-mix concrete C25/30", "Steel reinforcement (steel rebar)",
              "Rectified ceramic tile"):
        EPD.objects.get_or_create(
            name=n, country=cambodia,
            defaults={"names": [{"value": n, "lang": "en"}],
                      "UUID": "tpl-%s" % abs(hash(n)), "declared_unit": Unit.M3,
                      "conversions": [], "type": EPDType.GENERIC,
                      "public": True, "draft": False, "declared_amount": 1},
        )

    rows = _structural()
    assert len(rows) == 13, "expected the 13 example rows, got %s" % len(rows)
    client.force_login(user)
    resp = _post(client, "import_structural_components", {
        "building_uuid": str(building.uuid), "rows": rows,
    })
    assert resp.status_code == 200, resp.content[:500]
    errors = resp.json().get("errors") or {}
    unknown = {k: v for k, v in errors.items()
               if "building_component" in v or "dimension" in v}
    assert not unknown, "template names components the database rejects: %s" % unknown


def test_every_error_label_names_its_sheet(client, user, building):
    """A bare "row 1" from the energy carrier sheet read as a structural fault,
    because both endpoints wrote that same label into one panel."""
    client.force_login(user)
    resp = _post(client, "import_energy_carriers", {
        "building_uuid": str(building.uuid),
        "rows": [["electricity", "nothing metered", "0", "kwh"]],
    })
    assert resp.status_code == 400
    assert all(k.startswith("energy carrier row") for k in resp.json()["errors"]), \
        resp.json()["errors"]
