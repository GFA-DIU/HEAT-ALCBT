"""Error labels that did not say which section they came from.

"row 1: quantity: Quantity must be greater than 0." appeared under the
Structural Components block in the preview and read as a structural fault. It
came from the Operational Energy Carriers sheet. Both endpoints emitted a bare
"row N" into the same error panel, so the two were indistinguishable.
"""
import inspect

from pages.views.building import import_building as ib


def test_the_energy_carrier_rows_say_so():
    src = inspect.getsource(ib.import_operational_energy_carriers)
    assert 'f"energy carrier row {row_idx + 1}"' in src


def test_the_structural_rows_say_so():
    src = inspect.getsource(ib.import_structural_components)
    assert 'f"structural row {row_idx + 1}"' in src


def test_no_endpoint_emits_an_unnamed_row_label():
    """Every other section already named its tab - "led row 1", "ahu row 1".
    These two were the exceptions, and they collided."""
    src = inspect.getsource(ib)
    assert 'label = f"row {row_idx + 1}"' not in src
