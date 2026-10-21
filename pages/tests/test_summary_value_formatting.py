"""The plug & equipment row read "1 kWh/yr" while the total counted 1,150,790.89.

The panel renders values server-side and then re-formats them in the browser
with thousand separators. parseFloat stops at the first character it cannot
read, so a value the server had ALREADY grouped - "1,150,790.890" - parsed as
1, and the row was overwritten with it.

Only the plug & equipment row is rendered with floatformat's "g" suffix, which
is why it was the only row that looked wrong, and why the total disagreed with
the sum of what was on screen.
"""
import re
from pathlib import Path

import pytest
from django.template.defaultfilters import floatformat

TEMPLATE = Path("templates/pages/add-building/components/"
                "operational-details/energy-consumption-summary.html")


@pytest.fixture(scope="module")
def source():
    return TEMPLATE.read_text(encoding="utf-8")


def _js_parse_float(text):
    """What JavaScript's parseFloat makes of a string."""
    match = re.match(r"[-+]?[0-9]*\.?[0-9]+", text.strip())
    return float(match.group(0)) if match else float("nan")


def test_the_bug_is_real_without_the_strip():
    """Guards the premise: a grouped figure really does parse as 1."""
    assert _js_parse_float("1,150,790.890") == 1.0


def test_the_separators_are_stripped_before_parsing(source):
    body = source.split("function reformatValueSpan", 1)[1][:700]
    assert "replace(/,/g, '')" in body, body[:300]
    assert "parseFloat(text)" in body


def test_the_strip_happens_before_the_parse(source):
    body = source.split("function reformatValueSpan", 1)[1][:700]
    assert body.index("replace(/,/g, '')") < body.index("parseFloat(")


def test_a_grouped_value_survives_the_round_trip():
    """1,150,790.890 must come back as 1150790.89, not 1."""
    rendered = floatformat("1150790.890", "-3g")
    assert "," in rendered, rendered
    assert _js_parse_float(rendered.replace(",", "")) == pytest.approx(1150790.89)


def test_the_plug_row_is_still_grouped_server_side(source):
    """The grouping is deliberate - see test_lift_and_plug_load. The fix is in
    the parsing, not in removing it."""
    assert 'floatformat:"-3g"' in source


@pytest.mark.parametrize("value", ["258570.000", "4320000.0", "11330.4", "1150790.890"])
def test_every_rows_rendering_round_trips(value):
    """Both filters the panel uses must survive the browser's re-format."""
    for arg in (-3, "-3g"):
        rendered = floatformat(value, arg)
        parsed = _js_parse_float(rendered.replace(",", ""))
        assert parsed == pytest.approx(float(value)), (arg, rendered, parsed)
