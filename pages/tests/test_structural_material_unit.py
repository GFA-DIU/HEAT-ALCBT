"""The unit the material row posts must be the unit the model accepts.

Two pairings carry a dimensionless multiplier rather than a unit:

    Area component   + m²-declared EPD  -> "Number of layers"
    Length component + m-declared EPD   -> "Number of full-length elements"

get_epd_dimension_info() returns Unit.UNKNOWN for both, StructuralProduct.clean()
enforces it, and impact_calculation's direct-match step multiplies the assembly
quantity by that count. handle_select_product() used to rewrite UNKNOWN to the
EPD's declared unit before handing it to the form, so the browser posted 'm2',
the save was refused, and 2,006 m² EPDs plus 170 m EPDs - 38% of the library -
could not be added by hand at all. The Excel importer never had the rewrite, so
the same material imported fine and only the form failed.

These tests fail against that code: the endpoint returned 'm2', and the round
trip raised ValidationError.
"""
import json

import pytest
from django.urls import reverse

from pages.models.assembly import (Assembly, AssemblyDimension, AssemblyMode,
                                   StructuralProduct)
from pages.models.epd import EPD, EPDType, MaterialCategory, Unit

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    from allauth.account.models import EmailAddress
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = User.objects.create_user("unitfix", "unitfix@example.com", "testpass123")
    EmailAddress.objects.create(
        user=u, email="unitfix@example.com", verified=True, primary=True)
    return u


@pytest.fixture
def make_epd(db):
    def _make(name, declared_unit):
        return EPD.objects.create(
            names=[{"value": name, "lang": "en"}],
            type=EPDType.CUSTOM,
            declared_amount=1,
            category=MaterialCategory.objects.first(),
            declared_unit=declared_unit,
            conversions=[],
        )
    return _make


def _select(client, epd, dimension):
    """What the browser asks for when you pick a material in component mode."""
    return client.post(reverse("building_step_structural"), {
        "action": "select_structural_product",
        "epd_id": str(epd.id),
        "mode": "component",
        "dimension": dimension,
    })


@pytest.mark.parametrize("declared_unit, dimension, label", [
    (Unit.M2, AssemblyDimension.AREA, "Number of layers"),
    (Unit.M, AssemblyDimension.LENGTH, "Number of full-length elements"),
])
def test_the_row_asks_for_a_count_not_a_unit(
        client, user, make_epd, declared_unit, dimension, label):
    """The GFRG panels are one of the 2,006 m² EPDs this blocked."""
    epd = make_epd("Glass Fiber Reinforced Gypsum (GFRG) panels", declared_unit)
    client.force_login(user)

    resp = _select(client, epd, dimension)
    assert resp.status_code == 200, resp.content[:300]

    html = resp.content.decode()
    assert 'class="material-unit-value" value="unknown"' in html, (
        "the row posts a real unit, which StructuralProduct.clean() refuses")
    assert label in html, "the placeholder no longer says what to type"
    # The count is shown as "n", a plain number. It used to be "#", which read
    # as a reference or an ID rather than a quantity.
    assert 'data-unit="unknown">n<' in html, html[html.find("material-unit"):][:200]
    assert 'data-unit="unknown">#<' not in html


@pytest.mark.parametrize("declared_unit, dimension", [
    (Unit.M2, AssemblyDimension.AREA),
    (Unit.M, AssemblyDimension.LENGTH),
])
def test_what_the_row_posts_is_what_the_model_accepts(
        client, user, make_epd, declared_unit, dimension):
    """Close the loop: take the unit out of the rendered row and save with it."""
    epd = make_epd("Panel %s" % declared_unit, declared_unit)
    client.force_login(user)

    html = _select(client, epd, dimension).content.decode()
    marker = 'class="material-unit-value" value="'
    posted = html.split(marker, 1)[1].split('"', 1)[0]

    assembly = Assembly.objects.create(mode=AssemblyMode.CUSTOM, dimension=dimension)
    product = StructuralProduct.objects.create(
        assembly=assembly, epd=epd, quantity=2, input_unit=posted)
    assert product.pk is not None
    assert product.input_unit == Unit.UNKNOWN


def test_a_real_unit_is_still_refused_and_says_why(make_epd):
    """The old message read "Expected unit: 'unknown'", which told nobody
    anything. 'unknown' is the unit of a plain number, so say that."""
    from django.core.exceptions import ValidationError

    epd = make_epd("GFRG panel", Unit.M2)
    assembly = Assembly.objects.create(
        mode=AssemblyMode.CUSTOM, dimension=AssemblyDimension.AREA)

    with pytest.raises(ValidationError) as exc:
        StructuralProduct.objects.create(
            assembly=assembly, epd=epd, quantity=2, input_unit=Unit.M2)

    message = " ".join(exc.value.message_dict["input_unit"])
    assert "number of layers" in message.lower()
    assert "no unit" in message.lower()


def test_centimetres_do_not_pass_as_square_centimetres(make_epd):
    """`"cm" in "cm2"` is True. The check compared against a bare string, so a
    thickness in cm satisfied a cross-section in cm2 by substring and was stored
    as an area a hundred times too small."""
    from django.core.exceptions import ValidationError

    epd = make_epd("Steel section", Unit.M3)
    assembly = Assembly.objects.create(
        mode=AssemblyMode.CUSTOM, dimension=AssemblyDimension.LENGTH)

    # LENGTH + m3 expects CM2 (share of cross-section). 'cm2' contains 'cm'.
    with pytest.raises(ValidationError):
        StructuralProduct.objects.create(
            assembly=assembly, epd=epd, quantity=5, input_unit=Unit.CM)
