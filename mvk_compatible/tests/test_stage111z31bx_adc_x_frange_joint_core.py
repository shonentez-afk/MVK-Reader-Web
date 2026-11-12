"""Stage111Z31BX: source TQGrapher X, TSXML Y, linked ADC/FFT Core guards."""
from __future__ import annotations
import numpy as np
import pytest

from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from ..core.offline_export import OfflineSession
from ..core.direct_bin_session import DirectBinSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_adc_source_axes import (
    source_adc_grapher_x,source_adc_grapher_cursor,
    source_adc_spectrum_joint_receipt,
)
from ..core.original_adc_view_controls import source_adc_vertical_view


def test_reverse_x_ms_source_order_and_real_buffer_indices(tmp_path):
    p=fixture_zip(tmp_path,sample_count=8192)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(p),channel=1,tick_index=0)
    trace=flow.waveform(0.,1310/65536.,"ac",display_order="getsignal_buffer")
    g=source_adc_grapher_x(flow,trace,9)
    assert g["selected_adc"]==1
    assert g["axis_unit"]=="мс" and g["axis_max"]==20.
    assert g["scr_left_single"]==20. and g["scr_width_single"]==-20.
    assert g["series_xscale_single"]==float(np.float32(1000./65536.))
    assert g["series_samples"]==1310
    assert len(g["plot_x_single"])==len(trace["amplitude"])
    assert g["source_bin_sha256"]==flow.source_record()["source_bin_sha256"]
    a=source_adc_grapher_cursor(flow,trace,g,0.)
    assert a["buffer_index"]==0 and a["original_bin_sample_index"]==1309
    b=source_adc_grapher_cursor(flow,trace,g,1309*1000/65536.)
    assert b["original_bin_sample_index"]==0
    with pytest.raises(ValueError,match="past available"):
        source_adc_grapher_cursor(flow,trace,g,20.)
    with pytest.raises(ValueError,match="reverse X"):
        source_adc_grapher_x(
            flow,flow.waveform(0.,1310/65536.,"ac",
                               display_order="chronological"),9)
    with pytest.raises(ValueError,match="ADC|source|GetSignal"):
        source_adc_grapher_cursor(flow.select(channel=2),trace,g,1.)


@pytest.mark.parametrize("tag,seconds",[(0,20.),(1,10.)])
def test_original_x_switches_to_seconds_and_keeps_real_archive_truncation(
        tmp_path,tag,seconds):
    p=fixture_zip(tmp_path,sample_count=8192)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(p),channel=1,tick_index=0)
    d=flow.waveform(0.,seconds,"ac",display_order="getsignal_buffer")
    g=source_adc_grapher_x(flow,d,tag)
    assert g["axis_unit"]=="с"
    assert g["scr_left_single"]==seconds
    assert g["scr_width_single"]==-seconds
    assert g["series_xscale_single"]==float(np.float32(1./65536.))
    assert g["truncated_by_archive_end"]
    assert g["series_samples"]==8192


def test_original_positive_current_tsxml_f_range_for_adc_v_no_fake_calibration(
        tmp_path):
    p,sidecar,raw=_make_pair(tmp_path,adc=4,n=8192)
    sidecar.write_text(sidecar.read_text(encoding="utf-8").replace(
        "</Channel>","<InternalChannelGain>6.25</InternalChannelGain></Channel>"),
        encoding="utf-8")
    flow=OfflineMeasurementFlow.bind(DirectBinSession.open(p),channel=4)
    trace=flow.waveform(0.,.04,"ac",display_order="getsignal_buffer")
    current=flow.source_record()["source_bin_sha256"]
    v=source_adc_vertical_view(flow,trace,2,bound_source_sha256=current)
    assert v["divisor"]==5
    assert v["source_f_range_single"]==6.25
    assert v["graph_default_vscale_candidate"]==10.
    assert v["y_min"]==-2. and v["y_max"]==2.
    assert v["axis_baseline_origin"]=="TSXML_FRANGE_125_GRAPH_DEFAULT_STATIC_CANDIDATE"
    assert v["original_graph_default_vscale_numeric_runtime_verified"] is False
    np.testing.assert_array_equal(flow.samples()[0],raw)
    # Missing original metadata must NOT inherit the previous ADC4 FRange.
    p5,_,_=_make_pair(tmp_path,adc=5,n=8192)
    flow5=OfflineMeasurementFlow.bind(DirectBinSession.open(p5),channel=5)
    d5=flow5.waveform(0.,.04,"ac",display_order="getsignal_buffer")
    other=source_adc_vertical_view(
        flow5,d5,2,bound_source_sha256=flow5.source_record()["source_bin_sha256"])
    assert other["source_f_range_single"] is None
    assert other["axis_baseline_origin"]=="LOCAL_UNCALIBRATED_FULL_SIGNAL_PEAK"
    with pytest.raises(ValueError,match="Stale"):
        source_adc_vertical_view(flow5,trace,2,bound_source_sha256=current)


def test_same_source_bin_adc_wave_and_full_spectrum_not_decimated(tmp_path):
    p=fixture_zip(tmp_path,sample_count=8192)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(p),channel=1,tick_index=0)
    wave=flow.waveform(0.,.1,"ac",display_order="getsignal_buffer")
    fft=flow.spectrum(1024,1,0.,max_hz=1e9,max_points=1024,backend="numpy")
    joined=source_adc_spectrum_joint_receipt(flow,wave,fft)
    assert joined["adc"]==1
    assert joined["source_bin_sha256"]==flow.source_record()["source_bin_sha256"]
    assert joined["full_spectrum_bins"]==512
    assert joined["independent_core_results_used"]
    assert joined["different_time_windows_allowed"]
    assert not joined["hardware_commands_sent"]
    with pytest.raises(ValueError,match="different source"):
        source_adc_spectrum_joint_receipt(flow.select(channel=2),wave,fft)
    with pytest.raises(ValueError,match="Full N/2"):
        source_adc_spectrum_joint_receipt(flow,wave,
            dict(fft,amplitude=fft["amplitude"][:-1]))
