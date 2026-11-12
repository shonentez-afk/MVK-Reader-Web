"""Stage111Z31BN: restored Delphi V axis from PRIVATE _Unit128, synthetic only.

These tests assert source Tag/Page/Position, bound gain and entire Float32 Y
remain independent. No original runtime, device, user BIN or source is copied.
"""
import hashlib

import numpy as np
import pytest

from ..core.direct_bin_session import DirectBinSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_spectrum_view_binding import source_spectrum_gain
from ..core.original_spectrum_vertical_view import (
    source_spectrum_vertical_view, ORIGIN_TSXML, ORIGIN_PAIRED, ORIGIN_DB,
)
from ..core.mvk_spectrum_menu_runtime_idr_candidate import (
    source_vertical_mode_transition,source_vertical_selection,
    source_vertical_page,
)
from ..core.spectrum_graph_default_vscale_idr_candidate import (
    spectrum_graph_default_vscale,
)
from ..core.original_visible_spectrum_pair import (
    compare_visible_original_spectrum_pair,
)
from .test_stage111z16_direct_bin_tsxml import _make_pair
def _with_tsxml_gain(sidecar,gain):
    """Synthetic TSXML-only helper; never import PySide6 in Linux Core."""
    raw=sidecar.read_text(encoding="utf-8")
    sidecar.write_text(raw.replace(
        "</Channel>",f"<InternalChannelGain>{gain}</InternalChannelGain>"
        "</Channel>"),encoding="utf-8")
from .test_stage111z31q_same_window_spectrum import _manifest, SOURCE_N, SOURCE_FS


def _spectrum_with_gain(tmp_path, mode, gain="6.25"):
    path, xml, _ = _make_pair(tmp_path, n=8192, adc=4)
    if gain is not None:
        _with_tsxml_gain(xml,gain)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(path),channel=4)
    spec=flow.spectrum(1024, mode, start_s=0,
                       max_hz=1e9,max_points=512,backend="idr_float32")
    return flow,spec,source_spectrum_gain(flow,spec,mode=mode)


@pytest.mark.parametrize("mode,scale",[(1,10.),(2,100.),(3,1000.)])
def test_delphi_mode_default_is_bottom_anchored_and_uses_real_tsxml_f_range(
        tmp_path,mode,scale):
    flow,spec,gain=_spectrum_with_gain(tmp_path,mode)
    choice=source_vertical_mode_transition(
        mode,former_tag=0,former_position=0)
    assert choice["source_menu_tag"]==3
    assert choice["full"]==100000
    assert choice["page"]==100
    assert choice["delphi_position"]==99900  # _Unit128 0084C71A..C73A
    view=source_spectrum_vertical_view(
        flow,spec,choice,source_gain=gain)
    assert view["f_range_origin"]==ORIGIN_TSXML
    assert view["f_range_single"]==6.25
    assert view["graph_default_vscale_candidate"]==scale
    # Source computes/stores intermediate values as IEEE-754 Single.
    assert view["y_min"]==pytest.approx(0.,abs=.00003*scale)
    assert view["y_max"]==pytest.approx(scale/1000.,rel=5e-5)
    assert view["source_anchored_without_local_y_offset"]
    assert not view["original_runtime_f_range_verified"]
    assert not view["original_win32_canvas_pixel_parity_verified"]
    assert not view["physical_calibration_verified"]
    original_bits=np.asarray(spec["amplitude"],dtype="<f4").view("<u4").copy()
    # Source scroll motion must never change FFT bins/summary/FRange.
    other=source_vertical_selection(
        mode,3,old_tag=3,old_position=99800)
    shifted=source_spectrum_vertical_view(
        flow,spec,other,source_gain=gain)
    assert shifted["y_min"]>view["y_min"]
    assert shifted["y_max"]>view["y_max"]
    np.testing.assert_array_equal(
        np.asarray(spec["amplitude"],dtype="<f4").view("<u4"),original_bits)


def test_db_has_absolute_original_minus_page_to_zero_without_any_f_range(tmp_path):
    flow,spec,gain=_spectrum_with_gain(tmp_path,0,gain=None)
    choice=source_vertical_mode_transition(0,former_tag=0,former_position=0)
    assert choice["source_menu_tag"]==0
    assert choice["page"]==150
    assert choice["delphi_position"]==0
    view=source_spectrum_vertical_view(flow,spec,choice,source_gain=gain)
    assert view["f_range_origin"]==ORIGIN_DB
    assert view["f_range_single"] is None
    assert view["y_min"]==-150.
    assert view["y_max"]==0.
    assert view["graph_default_vscale_candidate"] is None
    assert view["source_anchored_without_local_y_offset"]


def test_missing_linear_gain_stays_unknown_not_guessed_from_local_y(tmp_path):
    flow,spec,gain=_spectrum_with_gain(tmp_path,1,gain=None)
    assert gain.frange_single is None
    choice=source_vertical_mode_transition(1)
    assert source_spectrum_vertical_view(
        flow,spec,choice,source_gain=gain) is None


def test_past_original_mode_position_reinterpreted_in_new_v_table_and_clamped():
    physical=source_vertical_mode_transition(
        1,former_tag=0,former_position=0)
    assert physical["delphi_position"]==99900
    db=source_vertical_mode_transition(
        0,former_tag=3,former_position=physical["delphi_position"])
    assert db["delphi_position"]==0
    # Mode1->Mode2 retains the new physical Tag3 bottom viewport.
    another=source_vertical_mode_transition(
        2,former_tag=3,former_position=99900)
    assert another["delphi_position"]==99900
    for bad in [True,1.5,-1,100001]:
        with pytest.raises(ValueError):
            source_vertical_mode_transition(1,former_position=bad)


def test_reject_source_gain_for_other_adc_even_when_bin_bytes_are_identical(
        tmp_path):
    p4,x4,_=_make_pair(tmp_path,n=8192,adc=4)
    p6,x6,_=_make_pair(tmp_path,n=8192,adc=6)
    _with_tsxml_gain(x4,"2.5")
    _with_tsxml_gain(x6,"12.5")
    flow4=OfflineMeasurementFlow.bind(DirectBinSession.open(p4),channel=4)
    spec4=flow4.spectrum(1024,1,max_hz=1e9,max_points=512)
    gain4=source_spectrum_gain(flow4,spec4,mode=1)
    flow6=flow4.select(channel=6)
    spec6=flow6.spectrum(1024,1,max_hz=1e9,max_points=512)
    assert flow4.source_record()["source_bin_sha256"]==(
        flow6.source_record()["source_bin_sha256"])
    with pytest.raises(ValueError,match="Stale source FRange"):
        source_spectrum_vertical_view(
            flow6,spec6,source_vertical_mode_transition(1),
            source_gain=gain4)
    bound=source_spectrum_vertical_view(
        flow6,spec6,source_vertical_mode_transition(1),
        source_gain=source_spectrum_gain(flow6,spec6,mode=1))
    assert bound["f_range_single"]==12.5


def test_operator_same_window_pair_anchors_linear_y_without_invented_gain(
        tmp_path):
    path,_,samples=_make_pair(tmp_path,adc=4,n=SOURCE_N*3)
    first=SOURCE_N
    ref,evidence,_=_manifest(
        tmp_path/"reference",samples[first:first+SOURCE_N],
        mode=1,code=0,offset=first)
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(path),channel=4)
    spec=flow.spectrum(
        SOURCE_N,1,start_s=first/SOURCE_FS,
        max_hz=1e9,max_points=SOURCE_N//2,backend="idr_float32")
    gain=source_spectrum_gain(flow,spec,mode=1)
    assert gain.frange_single is None
    choice=source_vertical_mode_transition(1)
    assert source_spectrum_vertical_view(
        flow,spec,choice,source_gain=gain) is None
    pair=compare_visible_original_spectrum_pair(flow,spec,ref,evidence)
    assert pair["paired_numeric_pass"]
    anchored=source_spectrum_vertical_view(
        flow,spec,choice,source_gain=gain,visible_pair=pair)
    assert anchored["f_range_origin"]==ORIGIN_PAIRED
    assert anchored["operator_original_y_pair_matched"]
    assert anchored["f_range_single"]==1.
    assert not anchored["original_win32_canvas_pixel_parity_verified"]
    tampered=dict(spec,amplitude=list(spec["amplitude"]))
    tampered["amplitude"][12]+=1.
    with pytest.raises(ValueError,match="no longer matches"):
        source_spectrum_vertical_view(
            flow,tampered,choice,source_gain=gain,visible_pair=pair)
