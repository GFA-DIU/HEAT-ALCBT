"""The building report export is switched off.

Hiding the button is not enough on its own: the export is a POST to a named
URL, so a replayed request, a bookmarked form or a second tab left open
before the change would still reach the view and produce a PDF carrying
figures BEAT no longer agrees with. The view has to refuse as well, and the
button and the view have to be driven by the SAME flag - two flags would
drift and one of them would be wrong.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import RequestFactory

from pages.views.building import building_report
from pages.views.building.building_report import export_building

TEMPLATE = Path("templates/pages/building/building.html")


@pytest.fixture(scope="module")
def source():
    return TEMPLATE.read_text(encoding="utf-8")


def _post():
    request = RequestFactory().post("/building/x/export/", {"format": "pdf"})
    # login_required only looks at is_authenticated, so this reaches the view
    # without touching the database - the flag is checked before any query.
    request.user = SimpleNamespace(is_authenticated=True)
    return request


# --- the flag itself -------------------------------------------------------

def test_the_export_is_off():
    assert building_report.REPORT_EXPORT_ENABLED is False


# --- the view refuses ------------------------------------------------------

def test_the_view_refuses_while_the_flag_is_off():
    response = export_building(_post(), "11111111-1111-1111-1111-111111111111")
    assert response.status_code == 403


def test_the_refusal_says_why():
    """A bare 403 looks like a permissions problem and gets reported as a bug."""
    response = export_building(_post(), "11111111-1111-1111-1111-111111111111")
    assert b"temporarily unavailable" in response.content


def test_the_view_builds_the_report_again_once_the_flag_is_on():
    """Without this the suite would still pass if the guard were left in
    permanently, or if someone replaced it with an unconditional refusal."""
    sentinel = RuntimeError("reached the building lookup")
    with mock.patch.object(building_report, "REPORT_EXPORT_ENABLED", True), \
            mock.patch.object(building_report, "get_object_or_404",
                              side_effect=sentinel):
        with pytest.raises(RuntimeError, match="reached the building lookup"):
            export_building(_post(), "11111111-1111-1111-1111-111111111111")


# --- the button is hidden by the same flag ---------------------------------

def test_the_template_hides_the_export_dropdown(source):
    before = source.split("<!-- Export dropdown -->", 1)[0]
    assert before.rstrip().endswith("{% if report_export_enabled %}")


def test_the_template_hides_the_post_form_too(source):
    """The hidden form carries the CSRF token and the action URL. Left in the
    page it is everything a replayed POST needs."""
    before = source.split('<form id="export-form"', 1)[0]
    assert before.rstrip().endswith("{% if report_export_enabled %}")


def test_the_guards_balance(source):
    """An unclosed {% if %} swallows the rest of the page silently."""
    assert source.count("{% if report_export_enabled %}") == 2


def test_the_view_passes_the_flag_to_the_template():
    detail = Path("pages/views/building/building.py").read_text(encoding="utf-8")
    assert 'context["report_export_enabled"] = REPORT_EXPORT_ENABLED' in detail
    assert ("from pages.views.building.building_report import "
            "REPORT_EXPORT_ENABLED") in detail
