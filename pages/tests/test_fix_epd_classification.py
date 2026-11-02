"""Filling a missing category and a missing declared amount.

Both fields are shared: the category decides which bar of every breakdown
chart a material lands in, and declared_amount is the divisor on every figure
the record produces. So the interesting behaviour is what the command
REFUSES, not what it writes.
"""
import io

import pytest
from django.core.management import CommandError, call_command

from pages.models.epd import EPD, MaterialCategory

pytestmark = pytest.mark.django_db

HEADER = "epd_id,name,proposed_category_id,proposed_declared_amount\n"


# The category tree ships with the database, so these are fetched rather than
# created: creating one raises on the unique category_id.
@pytest.fixture
def unknown_category(db):
    cat, _ = MaterialCategory.objects.get_or_create(
        category_id="0.0.0",
        defaults={"name_en": "Unknown", "name_de": "Unbekannt", "level": 0})
    return cat


@pytest.fixture
def rebar(db):
    cat, _ = MaterialCategory.objects.get_or_create(
        category_id="4.1.01",
        defaults={"name_en": "Steel reinforing bar",
                  "name_de": "Betonstahl", "level": 2})
    return cat


def make_epd(name, category=None, amount=1000):
    return EPD.objects.create(
        name=name, category=category, declared_unit="kg",
        declared_amount=amount, type="official", names={})


def write_csv(tmp_path, epd, cid="", amount=""):
    path = tmp_path / "proposal.csv"
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(HEADER)
        fh.write('%s,"%s","%s","%s"\n' % (epd.id, epd.name, cid, amount))
    return str(path)


def run(path, **kw):
    out = io.StringIO()
    call_command("fix_epd_classification", csv=path, stdout=out,
                 stderr=io.StringIO(), **kw)
    return out.getvalue()


# --- it fills what is missing -----------------------------------------------

def test_an_unknown_category_is_replaced(tmp_path, unknown_category, rebar):
    epd = make_epd("TMT Bars", category=unknown_category)
    run(write_csv(tmp_path, epd, cid="4.1.01"), apply=True)
    epd.refresh_from_db()
    assert epd.category == rebar


def test_a_missing_category_is_filled(tmp_path, rebar):
    epd = make_epd("TMT Bars", category=None)
    run(write_csv(tmp_path, epd, cid="4.1.01"), apply=True)
    epd.refresh_from_db()
    assert epd.category == rebar


def test_a_zero_declared_amount_is_filled(tmp_path):
    epd = make_epd("Ready Mix Concrete (M30, M35, M40 & M45)", amount=0)
    run(write_csv(tmp_path, epd, amount="1"), apply=True)
    epd.refresh_from_db()
    assert epd.declared_amount == 1


# --- it refuses to overwrite a real value -----------------------------------

def test_a_real_category_is_never_replaced(tmp_path, rebar):
    other, _ = MaterialCategory.objects.get_or_create(
        category_id="1.1.01",
        defaults={"name_en": "Cement", "name_de": "Zement", "level": 2})
    epd = make_epd("TMT Bars", category=other)
    out = run(write_csv(tmp_path, epd, cid="4.1.01"), apply=True)
    epd.refresh_from_db()
    assert epd.category == other
    assert "already set, left alone   : 1" in out


def test_a_real_declared_amount_is_never_replaced(tmp_path):
    """The amount divides every figure the record produces. Changing one
    silently would move the carbon of every building already using it."""
    epd = make_epd("Steel", amount=1000)
    out = run(write_csv(tmp_path, epd, amount="1"), apply=True)
    epd.refresh_from_db()
    assert epd.declared_amount == 1000
    assert "already set, left alone   : 1" in out


def test_a_zero_or_negative_proposal_is_refused(tmp_path):
    epd = make_epd("Something", amount=0)
    run(write_csv(tmp_path, epd, amount="0"), apply=True)
    epd.refresh_from_db()
    assert epd.declared_amount == 0


def test_an_unknown_category_id_is_refused(tmp_path, unknown_category):
    epd = make_epd("TMT Bars", category=unknown_category)
    out = run(write_csv(tmp_path, epd, cid="9.9.99"), apply=True)
    epd.refresh_from_db()
    assert epd.category == unknown_category
    assert "category id not found     : 1" in out


# --- a dry run must not write ----------------------------------------------

def test_dry_run_writes_nothing(tmp_path, unknown_category, rebar):
    epd = make_epd("TMT Bars", category=unknown_category, amount=0)
    out = run(write_csv(tmp_path, epd, cid="4.1.01", amount="1"))
    epd.refresh_from_db()
    assert epd.category == unknown_category
    assert epd.declared_amount == 0
    assert "DRY RUN" in out


def test_an_empty_csv_is_refused(tmp_path):
    path = tmp_path / "empty.csv"
    io.open(path, "w", encoding="utf-8").write(HEADER)
    with pytest.raises(CommandError, match="empty"):
        run(str(path))
