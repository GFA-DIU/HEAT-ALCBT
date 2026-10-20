"""Room types the import could not express.

LightingSystem.room_type holds a LightingSpaceType code. The table has 68 of
them, 6 legacy and 62 added with the national room types, but the importer's
hard-coded map only ever knew the 6 - so importing a room named "Work room /
Open plan" failed with "room_type: This field is required".
"""
import pytest

from pages.views.building.import_building import (
    PACKAGED_SUBTYPE_MAP, _parse_lighting_rows, _resolve_room_type,
)


# The 68 rows are not created by a migration - 0054 makes the table and the
# rows are loaded from pages/data/lighting_space_types.csv by a management
# command, which is why production had to have them loaded by hand. Seeding
# the tests from that same CSV keeps them from skipping, and from drifting
# away from the file the application is actually loaded from.

@pytest.fixture(autouse=True)
def space_types(db):
    import csv

    from pages.models.building_operation.lighting import LightingSpaceType, RoomType

    with open("pages/data/lighting_space_types.csv", newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            LightingSpaceType.objects.get_or_create(
                code=row["code"].strip(),
                defaults={
                    "name": row["name"].strip(),
                    "is_common": row["is_common"].strip().upper() == "TRUE",
                    "sort_order": int(row["sort_order"] or 100),
                },
            )
    # The six originals are kept so existing records still display.
    for code, label in RoomType.choices:
        LightingSpaceType.objects.get_or_create(
            code=code, defaults={"name": str(label), "legacy": True},
        )
    return LightingSpaceType.objects.count()


@pytest.mark.django_db
def test_every_room_type_in_the_table_resolves_to_itself():
    from pages.models.building_operation.lighting import LightingSpaceType

    missed = []
    for space in LightingSpaceType.objects.all():
        if _resolve_room_type(space.name.lower()) != space.code:
            missed.append(space.name)
    assert not missed, f"these room types cannot be imported: {missed}"


@pytest.mark.django_db
@pytest.mark.parametrize("name", [
    "Work room / Open plan", "Meeting room", "Corridor / Lobby",
])
def test_the_room_types_from_a_real_office_file(name):
    from pages.models.building_operation.lighting import LightingSpaceType

    space = LightingSpaceType.objects.filter(name__iexact=name).first()
    assert space is not None, f"{name!r} is missing from the CSV"
    assert _resolve_room_type(name.lower()) == space.code


@pytest.mark.django_db
def test_an_exact_name_beats_a_substring():
    """The substring pass matched "Staff office" on the key "office" and filed
    it as OFFICE_CONFERENCE - a conference room, which carries a different
    lighting power density. It produced a record, so nothing reported it."""
    from pages.models.building_operation.lighting import LightingSpaceType

    space = LightingSpaceType.objects.filter(name__iexact="Staff office").first()
    assert space is not None, f"{name!r} is missing from the CSV"
    got = _resolve_room_type("staff office")
    assert got == space.code
    assert got != "OFFICE_CONFERENCE"


@pytest.mark.django_db
def test_wording_from_the_old_template_still_resolves():
    """Files written against the old template use labels that are not in the
    table at all, so the substring pass is kept behind the exact match."""
    assert _resolve_room_type(
        "residential: kitchen, dining, bedroom, bathroom"
    ) == "RESIDENTIAL_KITCHEN"
    assert _resolve_room_type("hospital: patient room") == "HOSPITAL_PATIENT"


@pytest.mark.django_db
def test_an_unknown_room_refuses_rather_than_guessing():
    assert _resolve_room_type("flibbertigibbet") is None
    assert _resolve_room_type("") is None


@pytest.mark.django_db
def test_a_led_row_carries_its_room_type_through():
    from pages.models.building_operation.lighting import LightingSpaceType

    row = ["Meeting room", 260, "LED (Light emitting diode)", 40, 20, 6, 6, 50, "Yes"]
    parsed = _parse_lighting_rows("led", [row])[0]
    assert parsed["room_type"] == "COMMON_MEETING"


def test_cassette_is_not_offered_as_a_packaged_subtype():
    """Cassettes became their own ventilation type. The map listed 'cassette'
    pointing at itself, which is not one of the three valid subtypes."""
    from pages.models.building_operation.air_conditioning import PackagedACSubType

    valid = {c for c, _ in PackagedACSubType.choices}
    assert "cassette" not in PACKAGED_SUBTYPE_MAP
    for key, value in PACKAGED_SUBTYPE_MAP.items():
        assert value in valid, f"{key!r} -> {value!r} is not a real subtype"
