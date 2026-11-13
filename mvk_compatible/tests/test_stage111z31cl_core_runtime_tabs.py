"""Stage111Z31CL: original TTabSheet runtime visibility, pure Core.

A form having 7 DFM pages is NOT the same as showing 7 tab headers.
Original _Unit128: startup page only; observed loaded archive screenshot
13.11.2026: exactly Tasks/Time signal/Spectrum visible at once.
"""
import pytest

from ..core.original_runtime_tabs import (
    PAGES,SOURCE,ORIGINAL_IDLE_VISIBLE,ORIGINAL_ARCHIVE_VISIBLE,
    original_runtime_visible_pages,original_runtime_tab_contract,
)


def test_exact_original_startup_and_archive_visible_tab_sets():
    assert len(PAGES)==7
    assert ORIGINAL_IDLE_VISIBLE==("PageStart",)
    assert ORIGINAL_ARCHIVE_VISIBLE==(
        "PageStart","PageAdc","PageSpectrum")
    idle=original_runtime_tab_contract(has_measurement=False)
    assert idle["visible"]==("PageStart",)
    assert idle["visible_count"]==1
    assert idle["startup_only_one_tab"]
    loaded=original_runtime_tab_contract(has_measurement=True)
    assert loaded["visible"]==ORIGINAL_ARCHIVE_VISIBLE
    assert loaded["visible_count"]==3
    assert loaded["archive_only_three_default"]
    assert loaded["all_seven_handlers_remain_mounted"]
    assert not loaded["original_runtime_reachability_parity_verified"]
    assert not loaded["instrument_command_sent"]
    assert SOURCE.startswith("SOURCE_DERIVED_ORIGINAL_TABS")


def test_explicit_source_task_route_exposes_only_selected_hidden_page():
    config=original_runtime_visible_pages(
        has_measurement=False,current_page="PageConfig")
    assert config==("PageStart","PageConfig")
    file=original_runtime_visible_pages(
        has_measurement=True,current_page="PageFile")
    assert file==("PageStart","PageAdc","PageSpectrum","PageFile")
    status=original_runtime_visible_pages(
        has_measurement=True,current_page="PageStatus")
    assert status==("PageStart","PageStatus","PageAdc","PageSpectrum")
    for page in PAGES:
        assert page in original_runtime_visible_pages(
            has_measurement=True,current_page=page)
    all_tabs=original_runtime_visible_pages(
        has_measurement=False,technical=True)
    assert all_tabs==PAGES
    assert original_runtime_tab_contract(
        has_measurement=True,technical=True)["visible_count"]==7


@pytest.mark.parametrize("kwargs",[
    dict(has_measurement=0),
    dict(has_measurement=1),
    dict(has_measurement=True,technical=1),
    dict(has_measurement=None),
    dict(has_measurement=True,current_page="PageReboot"),
    dict(has_measurement=True,current_page=1),
])
def test_reject_invalid_source_runtime_visibility_inputs(kwargs):
    with pytest.raises(ValueError):
        original_runtime_visible_pages(**kwargs)
