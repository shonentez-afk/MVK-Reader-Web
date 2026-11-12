"""Stage111Z31BY: true filtered GetSignal output X/time from Unit115/128.

All test coefficients are synthetic. No original IDP, PAS, BIN or device.
"""
from __future__ import annotations
from hashlib import sha256
import numpy as np
import pytest

from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile
from ..core.offline_export import OfflineSession
from ..core.offline_measurement_flow import OfflineMeasurementFlow
from ..core.original_adc_view_controls import source_adc_horizontal_view
from ..core.original_adc_spectrum_actions import OriginalEnvelopeCursor
from ..core.original_adc_source_axes import (
    source_adc_envelope_axes,source_adc_envelope_cursor,
)


@pytest.mark.parametrize("code,output_rate,history",[
    (20,32768,102), (1,16384,388),
])
def test_full_fir_output_x_uses_actual_rate_instead_of_raw_fs(
        tmp_path,code,output_rate,history):
    archive=fixture_zip(tmp_path,sample_count=120000)
    before=sha256(archive.read_bytes()).hexdigest()
    flow=OfflineMeasurementFlow.bind(
        OfflineSession.open(archive),channel=1,tick_index=0)
    h=source_adc_horizontal_view(flow,9)
    assert h["requested_samples"]==1310
    trace=flow.envelope(code,.75,h["getsignal_seconds"],
        fake_profile(i=1.,q=.4),display_order="getsignal_buffer",points=12)
    axis=source_adc_envelope_axes(flow,trace,9)
    assert axis["kind"]=="SOURCE_FIR"
    assert axis["source_bin_sha256"]==flow.source_record()["source_bin_sha256"]
    assert axis["axis_max"]==20. and axis["scr_width_single"]==-20.
    assert axis["axis_unit"]=="мс"
    assert axis["output_sample_rate_hz"]==output_rate
    assert axis["series_xscale_single"]==float(np.float32(1000./output_rate))
    assert axis["requested_raw_samples"]==1310
    assert axis["required_input_samples"]==1310+history
    assert trace["input_source_window"]["source_sample_count"]==1310+history
    assert axis["series_samples"]==trace["output_samples"]
    assert axis["series_samples"]>len(trace["amplitude"])
    assert len(axis["plot_x_single"])==len(trace["amplitude"])
    assert axis["real_adjusted_history_verified"]
    assert not axis["data_or_filtered_array_recomputed_by_axes"]
    assert not axis["local_original_idp_sha_verified"]
    assert not axis["original_delphi_x87_output_numeric_parity_verified"]
    assert not axis["original_win32_gdi_pixel_parity_verified"]
    # In a reversed GetSignal buffer X=0 refers to the latest filtered
    # output; the canvas's negative ScrWidth places it on the right.
    full=OriginalEnvelopeCursor.from_trace(flow,trace)
    x=10.
    mapped=source_adc_envelope_cursor(flow,trace,axis,x)
    picked=full.pick(mapped["output_buffer_relative_s"])
    assert mapped["output_index"]==picked["output_index"]
    assert picked["filtered_output_sha256"]==axis["filtered_float32_sha256"]
    assert picked["value_from_full_filtered_float32"]==float(
        trace["cursor_full_samples_float32"][mapped["output_index"]])
    assert not mapped["original_absolute_fir_sample_time_verified"]
    assert sha256(archive.read_bytes()).hexdigest()==before


def test_fir_cursor_denies_fabricated_tail_bad_source_and_corrupted_full_array(
        tmp_path):
    archive=fixture_zip(tmp_path,sample_count=120000)
    flow=OfflineMeasurementFlow.bind(
        OfflineSession.open(archive),channel=1,tick_index=0)
    h=source_adc_horizontal_view(flow,9)
    trace=flow.envelope(20,.75,h["getsignal_seconds"],
        fake_profile(i=1.,q=.4),display_order="getsignal_buffer",points=10)
    axes=source_adc_envelope_axes(flow,trace,9)
    with pytest.raises(ValueError,match="outside|beyond"):
        source_adc_envelope_cursor(flow,trace,axes,20.1)
    with pytest.raises(ValueError,match="outside|beyond"):
        source_adc_envelope_cursor(flow,trace,axes,-.01)
    with pytest.raises(ValueError,match="stale"):
        source_adc_envelope_cursor(flow.select(channel=2),trace,axes,10.)
    with pytest.raises(ValueError,match="stale"):
        source_adc_envelope_cursor(
            flow,dict(trace,code=19),axes,10.)
    with pytest.raises(ValueError,match="SHA"):
        source_adc_envelope_axes(flow,
            dict(trace,post_fir_getsignal_return_float32_sha256="0"*64),9)
    with pytest.raises(ValueError,match="history"):
        source_adc_envelope_axes(flow,
            dict(trace,input_source_window={
                **trace["input_source_window"],"source_sample_count":100}),9)
    with pytest.raises(ValueError,match="order"):
        source_adc_envelope_axes(flow,
            dict(trace,display_order="chronological"),9)
    broken=np.asarray(trace["cursor_full_samples_float32"]).copy()
    broken[0]+=10.
    with pytest.raises(ValueError,match="SHA"):
        source_adc_envelope_axes(flow,
            dict(trace,cursor_full_samples_float32=broken),9)


def test_no_private_profile_no_history_no_fir_fabrication(tmp_path):
    archive=fixture_zip(tmp_path,sample_count=8192)
    flow=OfflineMeasurementFlow.bind(
        OfflineSession.open(archive),channel=1,tick_index=0)
    h=source_adc_horizontal_view(flow,9)
    with pytest.raises(ValueError,match="history"):
        flow.envelope(20,0.,h["getsignal_seconds"],
            fake_profile(i=1.,q=.4),display_order="getsignal_buffer")
    with pytest.raises((ValueError,TypeError)):
        flow.envelope(20,.05,h["getsignal_seconds"],None,
            display_order="getsignal_buffer")
