"""An unknown construction technique must not vanish silently.

Migration 0046 renamed and merged techniques alongside the categories. The
template still offers the old names - 42 of the 90 in its dropdown no longer
exist, including "Stones and Tiles", which its own example row uses. Each one
imported with classification = None and said nothing.
"""
import inspect

from pages.views.building import import_building as ib


def test_the_miss_is_logged_rather_than_swallowed():
    src = inspect.getsource(ib.import_structural_components)
    assert "except AssemblyTechnique.DoesNotExist:" in src
    after = src.split("except AssemblyTechnique.DoesNotExist:", 1)[1][:1200]
    assert "logger.warning" in after, "the miss is still silent"


def test_the_bare_pass_is_gone():
    """`pass` under that except is what made 42 dropdown values disappear
    without trace."""
    src = inspect.getsource(ib.import_structural_components)
    after = src.split("except AssemblyTechnique.DoesNotExist:", 1)[1]
    body = after.split("\n\n", 1)[0]
    assert "\n                    pass" not in body


def test_the_mismatch_is_written_up():
    """It is not fixed in code: the spec's technique table carries merges and
    drops, not only renames, and guessing at those would put a wrong technique
    on a record silently."""
    import os
    assert os.path.exists("docs/import_technique_mismatches.md")
