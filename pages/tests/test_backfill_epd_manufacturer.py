"""The manufacturer backfill must fill blanks and refuse everything else.

The command exists because 3,080 manufacturer-specific EPDs carry no maker,
so the picker cannot find them by company. The UltraTech cement EPD is in
BEAT under four names, none containing "UltraTech".

What is being protected here is not the filling, which is easy. It is the two
refusals. An EPD record is shared by every building that uses it, so a maker
written from a guess, or a maker overwritten because a spreadsheet disagreed,
is a silent change to data other people rely on.
"""
import io

import pytest
from django.core.management import CommandError, call_command

from pages.models.epd import EPD

pytestmark = pytest.mark.django_db

HEADER = "epd_id,name,proposed_manufacturer,sourced_from\n"


def make_epd(name, manufacturer=None):
    return EPD.objects.create(
        name=name,
        manufacturer=manufacturer,
        declared_unit="kg",
        declared_amount=1000,
        type="official",
        names={},
    )


def write_csv(tmp_path, rows):
    path = tmp_path / "proposal.csv"
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(HEADER)
        for epd, mfr, how in rows:
            fh.write('%s,"%s","%s","%s"\n' % (epd.id, epd.name, mfr, how))
    return str(path)


def run(path, **kw):
    out = io.StringIO()
    call_command("backfill_epd_manufacturer", csv=path, stdout=out,
                 stderr=io.StringIO(), **kw)
    return out.getvalue()


# --- it fills a blank ------------------------------------------------------

def test_apply_fills_a_blank_manufacturer(tmp_path):
    epd = make_epd("Portland Slag Cement (PSC)")
    run(write_csv(tmp_path, [(epd, "UltraTech Cement Ltd.", "epd5019")]),
        apply=True)
    epd.refresh_from_db()
    assert epd.manufacturer == "UltraTech Cement Ltd."


def test_an_empty_string_counts_as_blank(tmp_path):
    """Some importers wrote "" rather than NULL. Both must be fillable."""
    epd = make_epd("Portland Composite Cement (PCC)", manufacturer="")
    run(write_csv(tmp_path, [(epd, "UltraTech Cement Ltd.", "epd5019")]),
        apply=True)
    epd.refresh_from_db()
    assert epd.manufacturer == "UltraTech Cement Ltd."


# --- it refuses, twice -----------------------------------------------------

def test_a_row_with_no_manufacturer_is_skipped(tmp_path):
    """The 37 India EPDs whose maker could not be sourced must stay empty
    rather than receive anything derived from their product name."""
    epd = make_epd("ACC M15 Ready Mixed Concrete (RMC)")
    out = run(write_csv(tmp_path, [(epd, "", "NOT SOURCED")]), apply=True)
    epd.refresh_from_db()
    assert not epd.manufacturer
    assert "no manufacturer given     : 1" in out


def test_an_existing_manufacturer_is_never_overwritten(tmp_path):
    epd = make_epd("Steel Rebar", manufacturer="Tata Steel Limited")
    out = run(write_csv(tmp_path, [(epd, "Somebody Else Ltd.", "epd5018")]),
              apply=True)
    epd.refresh_from_db()
    assert epd.manufacturer == "Tata Steel Limited"
    assert "already set, left alone   : 1" in out


# --- a dry run must not write ---------------------------------------------

def test_dry_run_writes_nothing(tmp_path):
    epd = make_epd("Portland Pozzolano Cement (PPC)")
    out = run(write_csv(tmp_path, [(epd, "UltraTech Cement Ltd.", "epd5019")]))
    epd.refresh_from_db()
    assert not epd.manufacturer
    assert "DRY RUN" in out


# --- it refuses a CSV it cannot trust --------------------------------------

def test_a_csv_missing_its_columns_is_refused(tmp_path):
    path = tmp_path / "bad.csv"
    io.open(path, "w", encoding="utf-8").write("name,maker\nfoo,bar\n")
    with pytest.raises(CommandError, match="missing column"):
        run(str(path))


def test_an_empty_csv_is_refused(tmp_path):
    path = tmp_path / "empty.csv"
    io.open(path, "w", encoding="utf-8").write(HEADER)
    with pytest.raises(CommandError, match="empty"):
        run(str(path))


# --- the point of the whole exercise ---------------------------------------

def test_the_maker_becomes_searchable(tmp_path):
    """Filling the field is only worth doing because the picker's search
    already covers manufacturer. If that ever stops being true, this fails."""
    from django.db.models import Q
    epd = make_epd("Portland Slag Cement (PSC)")
    run(write_csv(tmp_path, [(epd, "UltraTech Cement Ltd.", "epd5019")]),
        apply=True)
    found = EPD.objects.filter(
        Q(name__icontains="ultratech")
        | Q(material_name__icontains="ultratech")
        | Q(product_name__icontains="ultratech")
        | Q(manufacturer__icontains="ultratech"))
    assert list(found) == [epd]


# --- renames are opt-in, and never lose the published title ----------------

def write_csv_with_name(tmp_path, epd, mfr, new_name):
    path = tmp_path / "rename.csv"
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write("epd_id,name,proposed_manufacturer,sourced_from,proposed_name\n")
        fh.write('%s,"%s","%s","%s","%s"\n' % (epd.id, epd.name, mfr, "epd5019", new_name))
    return str(path)


def test_a_rename_is_applied_and_the_original_title_is_kept(tmp_path):
    epd = make_epd("Portland Slag Cement (PSC)")
    run(write_csv_with_name(tmp_path, epd, "UltraTech Cement Ltd.",
                            "UltraTech Portland Slag Cement (PSC)"), apply=True)
    epd.refresh_from_db()
    assert epd.name == "UltraTech Portland Slag Cement (PSC)"
    assert epd.source_name == "Portland Slag Cement (PSC)"
    assert epd.manufacturer == "UltraTech Cement Ltd."


def test_a_rename_does_not_clobber_an_existing_source_name(tmp_path):
    """source_name is the published title. If one is already recorded it is
    the real one, and must survive a second rename."""
    epd = make_epd("Portland Slag Cement (PSC)")
    epd.source_name = "Aditya Birla Portland Slag Cement (PSC)"
    epd.save()
    run(write_csv_with_name(tmp_path, epd, "UltraTech Cement Ltd.",
                            "UltraTech Portland Slag Cement (PSC)"), apply=True)
    epd.refresh_from_db()
    assert epd.source_name == "Aditya Birla Portland Slag Cement (PSC)"


def test_no_rename_happens_without_the_column(tmp_path):
    epd = make_epd("Portland Slag Cement (PSC)")
    run(write_csv(tmp_path, [(epd, "UltraTech Cement Ltd.", "epd5019")]),
        apply=True)
    epd.refresh_from_db()
    assert epd.name == "Portland Slag Cement (PSC)"


def test_a_dry_run_does_not_rename(tmp_path):
    epd = make_epd("Portland Slag Cement (PSC)")
    out = run(write_csv_with_name(tmp_path, epd, "UltraTech Cement Ltd.",
                                  "UltraTech Portland Slag Cement (PSC)"))
    epd.refresh_from_db()
    assert epd.name == "Portland Slag Cement (PSC)"
    assert "would be renamed          : 1" in out


def test_a_rename_moves_the_material_name_that_mirrored_the_title(tmp_path):
    """display_name composes from material_name, so a rename that moves only
    `name` never reaches the picker. This is how the first run failed."""
    epd = make_epd("Portland Slag Cement (PSC)")
    epd.material_name = "Portland Slag Cement (PSC)"
    epd.save()
    run(write_csv_with_name(tmp_path, epd, "UltraTech Cement Ltd.",
                            "UltraTech Portland Slag Cement (PSC)"), apply=True)
    epd.refresh_from_db()
    assert epd.material_name == "UltraTech Portland Slag Cement (PSC)"
    assert epd.display_name == "UltraTech Portland Slag Cement (PSC)"


def test_a_rename_leaves_a_hand_split_material_name_alone(tmp_path):
    """A material_name that says something the title does not is somebody's
    judgement, not a mirror, and must survive."""
    epd = make_epd("Xtend Pro 42")
    epd.material_name = "Cement mortar"
    epd.save()
    run(write_csv_with_name(tmp_path, epd, "Greenex Environmental",
                            "Greenex Xtend Pro 42"), apply=True)
    epd.refresh_from_db()
    assert epd.name == "Greenex Xtend Pro 42"
    assert epd.material_name == "Cement mortar"
