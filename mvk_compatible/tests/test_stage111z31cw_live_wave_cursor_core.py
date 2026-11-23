"""PageAdc LIVE cursor: source X -> real full GetSignal/Go sample index.

Only synthetic Float32 arrays and per-window SHA, never real MVK01,
connected hardware, an original DFM/IDP or exported private samples.
"""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from ..core.native_r6_live_preview import (
    PreviewADC,LivePreview,provisional_waveform)
from ..core.offline_export import waveform_for_zip
from ..core.original_live_adc_cursor import (
    bind_source_live_wave_cursor,pick_source_live_wave_cursor)
from ..core.original_live_getsignal_fir_processing import (
    source_live_filtered_cursor)
from ..core.signal_idr_candidate import unfiltered_getsignal


def preview(fs=65536,n=4096,*,wrap=False):
    t=np.arange(n,dtype=np.float64)
    arr=np.asarray(
        .37+1.2*np.sin(2*np.pi*121*t/fs),dtype="<f4")
    arr.setflags(write=False)
    start=(1<<32)-2048 if wrap else 0
    end=start+n
    adc=PreviewADC(
        1,fs,start&0xFFFFFFFF,end&0xFFFFFFFF,arr,
        sha256(arr.tobytes()).hexdigest(),end)
    return LivePreview(
        "SYNTHETIC_SOURCE_CURSOR",
        datetime(2026,11,23,tzinfo=timezone.utc),
        20480,500,{1:adc})


@pytest.mark.parametrize("ac",[False,True])
@pytest.mark.parametrize("wrap",[False,True])
def test_source_live_plain_cursor_full_float32_and_absolute_uint64(ac,wrap):
    source=preview(wrap=wrap)
    end=source.channels[1].captured_samples
    wave=provisional_waveform(
        source,1,ac=ac,source_h_tag=9,
        capture_rxpos=end,last_processed_pos=0,
        source_allow_overlap=False)
    bound=bind_source_live_wave_cursor(wave,source,1)
    assert bound.axis_unit=="мс"
    assert bound.axis_max==20.
    assert len(bound.full_reversed_getsignal)==1310
    assert not bound.full_reversed_getsignal.flags.writeable
    assert bound.source_getsignal_sha256==wave["cursor_full_reversed_sha256"]
    assert bound.end_absolute_sample_exclusive==end
    assert wave["cursor_plot_is_peak_preserving_lod"] is True
    assert len(wave["cursor_plot_x"])<=4000
    assert wave["cursor_plot_x"][0]==0.
    expected=unfiltered_getsignal(
        source.channels[1].samples[-1310:],65536,no_dc=ac)
    np.testing.assert_array_equal(
        bound.full_reversed_getsignal.view("<u4"),
        expected.getsignal_buffer.view("<u4"))
    p=pick_source_live_wave_cursor(bound,0.5,adjacent_x=0.51)
    assert p is not None
    assert p["source_input_sha256"]==source.channels[1].sha256
    assert p["source_getsignal_sha256"]==bound.source_getsignal_sha256
    assert p["full_float32_value"]==float(
        bound.full_reversed_getsignal[p["output_index"]])
    assert p["original_uint64_adc_sample_index"]==end-1-p["output_index"]
    assert p["original_uint32_sample_index"]==(
        p["original_uint64_adc_sample_index"]&0xFFFFFFFF)
    assert p["uses_full_getsignal_not_plot_lod"]
    assert p["device_io_performed"] is False
    assert p["original_win32_pixel_rounding_parity_verified"] is False
    assert pick_source_live_wave_cursor(bound,-1.) is None
    assert pick_source_live_wave_cursor(bound,20.) is None
    assert source.channels[1].sha256==sha256(
        source.channels[1].samples.tobytes()).hexdigest()


def test_live_cursor_uses_original_second_axis_for_long_10s_window():
    source=preview(fs=512,n=5120)
    wave=provisional_waveform(
        source,1,ac=False,source_h_tag=1,
        capture_rxpos=5120,last_processed_pos=0)
    bound=bind_source_live_wave_cursor(wave,source,1)
    assert bound.axis_unit=="с"
    assert bound.axis_max==10.
    assert bound.xscale_single==pytest.approx(1/512.,rel=1e-7)
    assert wave["cursor_axis_unit"]=="с"
    assert wave["cursor_plot_x"][-1]<10.
    assert pick_source_live_wave_cursor(bound,5.)["output_index"]==2560


def test_no_fabricated_cursor_on_foreign_go_sha_tag_or_missing_history():
    source=preview()
    wave=provisional_waveform(
        source,1,source_h_tag=9,capture_rxpos=4096)
    for patch in (
        {"cursor_full_reversed_sha256":"0"*64},
        {"cursor_full_source_window_sha256":"0"*64},
        {"original_bAdcHScale_tag":5},
        {"window_samples":1},
    ):
        with pytest.raises(ValueError):
            bind_source_live_wave_cursor(dict(wave,**patch),source,1)
    with pytest.raises(ValueError):
        bind_source_live_wave_cursor(wave,source,2)
    normal=waveform_for_zip(
        Path("NO_FILE"),1,0.,.02,mode="acdc",
        sample_provider=source.samples_for_offline_candidate)
    assert "cursor_full_reversed_getsignal" not in normal
    for bad in (float("nan"),float("inf"),True):
        with pytest.raises(ValueError):
            pick_source_live_wave_cursor(
                bind_source_live_wave_cursor(wave,source,1),bad)


def test_fir_source_signed_peak_in_one_logical_pixel_not_abs_or_lod():
    values=np.asarray([0.,-5.,4.,2.,-2.,0.],dtype="<f4")
    values.setflags(write=False)
    result=dict(full_reversed_getsignal=values,output_rate_hz=1000,
        original_selected_ms=10,
        output_float32_sha256=sha256(values.tobytes()).hexdigest(),
        source_float32_sha256="a"*64,source_session_id="SYNTHETIC",
        source_request_id="FIR_SOURCE")
    same=source_live_filtered_cursor(result,1.0)
    assert same["output_index"]==1
    assert same["value_from_full_filtered_float32"]==-5.
    picked=source_live_filtered_cursor(
        result,1.0,adjacent_x_ms=3.0)
    assert picked["output_index"]==2
    assert picked["value_from_full_filtered_float32"]==4.
    assert picked["source_pixel_signed_peak_candidate"]
    assert picked["original_delphi_cursor_parity_verified"] is False
    with pytest.raises(ValueError):
        source_live_filtered_cursor(result,1.0,adjacent_x_ms=float("nan"))
