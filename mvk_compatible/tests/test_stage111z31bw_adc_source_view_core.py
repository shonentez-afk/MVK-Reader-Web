"""Stage111Z31BW: original ADC H/V source tables and real source-window guards."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import numpy as np
import pytest

from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_adc_view_controls import (
    ADC_HORIZONTAL_MS,ADC_VERTICAL_DIVISORS,
    original_adc_horizontal_options,original_adc_vertical_options,
    source_adc_horizontal_view,validate_source_adc_horizontal_trace,
    source_adc_vertical_view,
)


def test_original_idp_14_horizontal_13_vertical_tags_and_bytes():
    # Data recovered from operator-owned 008D33BC / 008D33F4;
    # labels are source semantics; no original private bytes here.
    assert ADC_HORIZONTAL_MS==(
        20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1)
    assert ADC_VERTICAL_DIVISORS==(
        1,2,5,10,20,50,100,200,500,1000,2000,5000,10000)
    assert [v["tag"] for v in original_adc_horizontal_options()]==list(range(14))
    assert [v["tag"] for v in original_adc_vertical_options()]==list(range(13))
    assert original_adc_horizontal_options()[0]["caption"]=="20 с"
    assert original_adc_horizontal_options()[-1]["caption"]=="1 мс"


def test_source_wave_real_samples_and_h_scale_integer_division(tmp_path):
    archive=fixture_zip(tmp_path,sample_count=8192)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive),channel=1,tick_index=0)
    h=source_adc_horizontal_view(flow,9)   # 20 ms, 1310 samples at 65536 Hz
    assert h["milliseconds"]==20
    assert h["requested_samples"]==1310
    assert h["getsignal_seconds"]==1310/65536
    trace=flow.waveform(0.,h["getsignal_seconds"],"ac")
    verified=validate_source_adc_horizontal_trace(flow,trace,h)
    assert verified["actual_window_samples"]==1310
    assert not verified["truncated_by_archive_end"]
    assert trace["window_samples"]==1310
    assert trace["rms_m_s2"]>=0
    assert not verified["fft_or_signal_recomputed_by_view"]
    v=source_adc_vertical_view(
        flow,trace,2,bound_source_sha256=h["source_bin_sha256"])
    assert v["divisor"]==5 and v["y_min"]==-v["y_max"]
    assert v["window_peak_from_core"]==trace["peak_m_s2"]
    assert v["source_window_basis"]=="GETSIGNAL_FULL_WINDOW_PEAK_NOT_PLOT_LOD"
    assert v["original_graph_default_vscale_verified"] is False
    assert sha256(archive.read_bytes()).hexdigest()


def test_h_scale_truncation_and_source_switch_never_reuse_old_axis(tmp_path):
    archive=fixture_zip(tmp_path,sample_count=4096)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive),channel=1,tick_index=0)
    h=source_adc_horizontal_view(flow,0) # request 20s, only 4096 exist
    trace=flow.waveform(0,h["getsignal_seconds"],"ac")
    result=validate_source_adc_horizontal_trace(flow,trace,h)
    assert result["truncated_by_archive_end"]
    assert result["actual_window_samples"]==4096
    with pytest.raises(ValueError,match="count"):
        validate_source_adc_horizontal_trace(
            flow,dict(trace,window_samples=4095),h)
    with pytest.raises(ValueError,match="Tag"):
        source_adc_horizontal_view(flow,14)
    with pytest.raises(ValueError,match="Tag"):
        source_adc_vertical_view(flow,trace,13,bound_source_sha256=h["source_bin_sha256"])
    newer=flow.select(channel=2)
    with pytest.raises(ValueError,match="Stale|another"):
        validate_source_adc_horizontal_trace(newer,trace,h)
    with pytest.raises(ValueError,match="Stale"):
        source_adc_vertical_view(newer,trace,1,bound_source_sha256=h["source_bin_sha256"])


def test_original_vscale_fir_uses_full_calculated_array_not_display_lod(tmp_path):
    archive=fixture_zip(tmp_path,sample_count=120000)
    flow=OfflineMeasurementFlow.bind(OfflineSession.open(archive),channel=1,tick_index=0)
    h=source_adc_horizontal_view(flow,8)  # 50ms with real FIR history
    # Read a full FIR window with enough actual history, do not pad zeros.
    seconds=h["getsignal_seconds"]
    trace=flow.envelope(20,.75,seconds,fake_profile(i=1.,q=.4),
                        display_order="chronological",points=10)
    full=trace["cursor_full_samples_float32"]
    assert len(full)>10
    v=source_adc_vertical_view(
        flow,trace,0,
        bound_source_sha256=flow.source_record()["source_bin_sha256"])
    assert v["source_window_basis"]=="VERIFIED_FULL_POST_FIR_FLOAT32_NOT_PLOT_LOD"
    assert v["window_peak_from_core"]==float(np.max(np.abs(full)))
    assert len(trace["amplitude"])<=10
    forged=dict(trace,cursor_full_samples_float32=full.copy())
    forged["cursor_full_samples_float32"][0]+=1
    with pytest.raises(ValueError,match="SHA"):
        source_adc_vertical_view(
            flow,forged,0,
            bound_source_sha256=flow.source_record()["source_bin_sha256"])
