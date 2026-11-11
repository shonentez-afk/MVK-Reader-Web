"""Stage111Z31BB: all-seven-page safe source state and original axis/domain.

Source DFM/IDR addresses are checked through derived constants, with
synthetic FFT references only. No original device or runtime needed.
"""
import dataclasses
import pytest

from mvk_compatible.core.original_offline_view_state import (
    OriginalOfflineView, PAGES, DEFAULT_HZ, SAFE_TRANSITIONS,
    UNSAFE_OR_UNVERIFIED, original_reference_axis_contract,
)
from mvk_compatible.core.mvk_original_scale_tables_idr_candidate import (
    HORIZONTAL_HZ, FFT_WINDOW_SAMPLES,
)
from mvk_compatible.core.original_pagestatus_source import MODE_NAMES


def test_original_reference_short_curve_but_full_25600_axis():
    ref=original_reference_axis_contract(131072,32768)
    assert ref["full_horizontal_menu_axis_end_hz"]==25600
    assert ref["tqgrapher_display_series_end_hz"]==12800
    assert ref["empty_right_frequency_span_hz"]==12800
    assert ref["tqgrapher_display_series_bins"]==51200
    assert ref["tqgrapher_raw_power_bins"]==65536
    assert ref["axis_end_is_not_derived_from_series_end"]
    assert not ref["fft_samples_or_bins_modified"]
    assert not ref["original_runtime_display_mode_verified"]
    full=original_reference_axis_contract(262144,65536)
    assert full["tqgrapher_display_series_end_hz"]==25600
    assert full["empty_right_frequency_span_hz"]==0


def test_all_seven_pages_and_eight_channels_route_as_offline_core():
    state=OriginalOfflineView.initial()
    assert state.snapshot()["page"]=="PageStart"
    assert DEFAULT_HZ==25600
    assert not state.snapshot()["hscroll_visible"]
    assert len(PAGES)==7
    assert len(MODE_NAMES)==15
    for page in PAGES:
        for channel in range(1,9):
            advanced=state.transition("select_page",page).transition(
                "select_channel",channel)
            assert advanced.page==page
            assert advanced.channel==channel
            assert advanced.spectrum_mode==state.spectrum_mode
            assert advanced.snapshot()["device_command_issued"] is False
    assert state.page=="PageStart"  # original immutable


def test_original_horizontal_menu_tags_panning_and_preserving_position():
    old=OriginalOfflineView.initial()
    for tag,hz in enumerate(HORIZONTAL_HZ):
        narrowed=old.transition("select_spectrum_hscale",tag)
        assert narrowed.hscale_tag==tag
        assert narrowed.snapshot()["hscale_hz"]==hz
        assert narrowed.snapshot()["hscroll_visible"]==(tag!=0)
        assert narrowed.snapshot()["hscroll"]["qt_maximum"]==25600-hz
        last=narrowed.transition("scroll_spectrum_horizontal",25600-hz)
        assert last.hscroll_position==25600-hz
        # Source H re-selection clamps previous integer scroll offset.
        restored=last.transition("select_spectrum_hscale",0)
        assert restored.hscroll_position==0
        assert not restored.snapshot()["hscroll_visible"]


def test_all_four_tags_and_six_vertical_scales_reset_by_mode():
    state=OriginalOfflineView.initial()
    for mode in range(4):
        modified=state.transition("select_spectrum_mode",mode)
        assert modified.spectrum_mode==mode
        assert modified.vscale_tag==(0 if mode==0 else 3)
        assert modified.vscroll_position==0
        for tag in range(6):
            x=modified.transition("select_spectrum_vscale",tag)
            assert x.vscale_tag==tag
            assert x.snapshot()["vscale_menu"]
            assert x.snapshot()["vscroll"]["qt_maximum"]>=0
    assert state.spectrum_mode==0


def test_original_vertical_scrolling_preserves_source_integer_position():
    s=OriginalOfflineView.initial().transition('select_spectrum_vscale',1)
    assert s.snapshot()['vscroll']['qt_maximum']==50
    scrolled=s.transition('scroll_spectrum_vertical',17)
    assert scrolled.vscroll_position==17
    assert scrolled.snapshot()['vscroll']['delphi_position']==17
    reset=scrolled.transition('select_spectrum_mode',1)
    assert reset.vscale_tag==3
    assert reset.vscroll_position==0
    with pytest.raises(ValueError):
        s.transition('scroll_spectrum_vertical',51)


def test_all_fft_menu_modes_and_status_modes_are_distinct_view_only():
    state=OriginalOfflineView.initial()
    for idx,n in enumerate(FFT_WINDOW_SAMPLES):
        selected=state.transition("select_spectrum_fft_lines",idx)
        assert selected.snapshot()["n_fft_requested"]==n
        assert not selected.snapshot()["real_archive_fft_history_verified"]
    for idx in range(len(MODE_NAMES)):
        assert state.transition("select_status_tab",idx).status_tab==idx


@pytest.mark.parametrize("action,value",[
    ("device_connect",True),("device_config_upload",1),
    ("device_calibration_start","A"),("device_rate_change",150),
    ("device_config_download",None),("device_register_write",0),
    ("unknown",0),(" ",0),
])
def test_original_device_and_unknown_commands_cannot_execute(action,value):
    assert action not in SAFE_TRANSITIONS
    if action.startswith("device_"):
        assert action in UNSAFE_OR_UNVERIFIED
    with pytest.raises(PermissionError):
        OriginalOfflineView.initial().transition(action,value)


@pytest.mark.parametrize("action,value",[
    ("select_page","PageReboot"),
    ("select_channel",0),("select_channel",True),
    ("select_status_tab",15),("select_spectrum_mode",4),
    ("select_spectrum_hscale",10),
    ("select_spectrum_hscale",False),
    ("scroll_spectrum_horizontal",-1),
    ("select_spectrum_vscale",6),
    ("select_spectrum_fft_lines",6),
])
def test_invalid_source_ui_transitions_fail_closed(action,value):
    with pytest.raises(ValueError):
        OriginalOfflineView.initial().transition(action,value)


def test_source_state_rejects_invalid_restore_and_mutable_data():
    with pytest.raises(ValueError):
        OriginalOfflineView(page="Invalid")
    with pytest.raises(ValueError):
        OriginalOfflineView(hscale_tag=2,hscroll_position=26000)
    with pytest.raises(ValueError):
        OriginalOfflineView(spectrum_mode=0,vscale_tag=2,vscroll_position=150)
    with pytest.raises(ValueError):
        OriginalOfflineView.initial().snapshot(n_fft=131072)
    with pytest.raises(ValueError):
        original_reference_axis_contract(131072,32768.5)
    assert dataclasses.is_dataclass(OriginalOfflineView)
    with pytest.raises(dataclasses.FrozenInstanceError):
        OriginalOfflineView.initial().channel=4
