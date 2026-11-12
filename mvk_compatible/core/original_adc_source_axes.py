"""STAGE111Z31BX: source-derived ADC X geometry and ADC/Spectrum linkage.

_Private originals are NOT bundled._ Static basis: Unit128 0084B2F8
(ScrLeft=duration, ScrWidth=-duration; ms if H<10000 otherwise seconds),
00848033 (Series.XScale=1000/Fs or 1/Fs), 00847EAC (GetSignal),
0084B4AC (ADCGrapher.UpdateCursor mouse X only). GetSignal is reversed;
negative grapher X width restores chronological left->right rendering.
This is NOT a proof of Win32 bitmap pixel parity.
"""
from __future__ import annotations
import math
import numpy as np

from .offline_measurement_flow import OfflineMeasurementFlow
from .original_adc_view_controls import (
    ADC_HORIZONTAL_MS,source_adc_horizontal_view,
    validate_source_adc_horizontal_trace,
)

SOURCE="SOURCE_ADC_REVERSE_X_AND_SPECTRUM_CORE_QT_STAGE111Z31BX"


def source_adc_grapher_x(flow:OfflineMeasurementFlow,trace:dict,tag:int)->dict:
    if not isinstance(flow,OfflineMeasurementFlow) or not isinstance(trace,dict):
        raise ValueError("Current source GetSignal flow and trace required")
    if trace.get("display_order")!="getsignal_buffer" or "code" in trace:
        raise ValueError("Source reverse X requires unfiltered reversed GetSignal")
    selected=source_adc_horizontal_view(flow,tag)
    status=validate_source_adc_horizontal_trace(flow,trace,selected)
    ms=ADC_HORIZONTAL_MS[tag]
    scalar=1. if ms>=10000 else 1000.
    units="с" if ms>=10000 else "мс"
    fs=status["actual_sample_rate_hz"]
    left=float(np.float32(ms/1000. if ms>=10000 else ms))
    width=float(np.float32(-left))
    xscale=float(np.float32(scalar/fs))
    xx=trace.get("time_s")
    yy=trace.get("amplitude")
    if (not isinstance(xx,(tuple,list)) or not isinstance(yy,(tuple,list))
            or len(xx)!=len(yy) or not 1<=len(xx)<=200_000):
        raise ValueError("GetSignal plot LOD missing")
    start=float(trace["start_s"])
    positions=tuple(float(np.float32((float(t)-start)*scalar)) for t in xx)
    if (not all(math.isfinite(x) and -1e-3<=x<=left+1e-3
                for x in positions)
            or not math.isfinite(xscale) or xscale<=0):
        raise ValueError("Source ADC X outside declared original graph")
    window=trace.get("input_source_window")
    if not isinstance(window,dict) or window.get("channel")!=flow.channel:
        raise ValueError("Source ADC Float32 input window not verified")
    return {
        "source":SOURCE,"tag":tag,"selected_adc":flow.channel,
        "source_bin_sha256":status["source_bin_sha256"],
        "source_window_sha256":window.get("source_float32_le_sha256"),
        "axis_unit":units,"axis_scale_from_seconds":scalar,
        "axis_max":left,"scr_left_single":left,"scr_width_single":width,
        "series_xscale_single":xscale,
        "series_samples":status["actual_window_samples"],
        "requested_samples":status["requested_samples"],
        "truncated_by_archive_end":status["truncated_by_archive_end"],
        "plot_x_single":positions,
        "reversed_source_axis":True,"plot_samples_mutated":False,
        "original_pixel_coordinate_parity_verified":False,
    }


def source_adc_grapher_cursor(flow:OfflineMeasurementFlow,trace:dict,
                              axes:dict,x_coord:float)->dict:
    """Original buffer X -> real BIN sample without reading decimated Y."""
    if not isinstance(axes,dict) or not isinstance(trace,dict):
        raise ValueError("Source axis/trace required")
    fresh=source_adc_grapher_x(flow,trace,axes.get("tag"))
    for key in ("source_bin_sha256","source_window_sha256",
                "series_samples","axis_max","axis_unit","selected_adc"):
        if fresh[key]!=axes.get(key):
            raise ValueError("Source graph changed ADC or BIN after render")
    if (isinstance(x_coord,bool) or
            not isinstance(x_coord,(int,float)) or not math.isfinite(x_coord)
            or not 0.<=x_coord<=axes["axis_max"]):
        raise ValueError("Cursor X outside original H viewport")
    fs=flow.source_record()["sample_rate_hz"]
    idx=int(math.floor(x_coord/axes["axis_scale_from_seconds"]*fs+.5))
    if not 0<=idx<axes["series_samples"]:
        raise ValueError("Cursor past available original GetSignal samples")
    first=round(float(trace["start_s"])*fs)
    original=first+axes["series_samples"]-idx-1
    return {
        "source":SOURCE,"buffer_index":idx,
        "original_bin_sample_index":original,
        "source_archive_time_s":(first+idx)/fs,
        "physical_sample_time_s":original/fs,
        "plot_x":idx/fs*axes["axis_scale_from_seconds"],
        "source_bin_sha256":axes["source_bin_sha256"],
        "original_pixel_parity_verified":False,
    }


def source_adc_spectrum_joint_receipt(flow:OfflineMeasurementFlow,
                                      wave:dict,spectrum:dict)->dict:
    """Same BIN, selected ADC and actual Core outputs; different windows OK."""
    if (not isinstance(flow,OfflineMeasurementFlow)
            or not isinstance(wave,dict) or not isinstance(spectrum,dict)):
        raise ValueError("Both independent source calculations required")
    record=flow.source_record()
    if (wave.get("channel")!=flow.channel or spectrum.get("channel")!=flow.channel
            or wave.get("file")!=record["data_file_label"]
            or spectrum.get("file")!=record["data_file_label"]):
        raise ValueError("Signal and spectrum belong to different source ADC/file")
    w=spectrum.get("input_source_window")
    a=wave.get("input_source_window")
    if (not isinstance(w,dict) or not isinstance(a,dict)
            or w.get("channel")!=flow.channel or a.get("channel")!=flow.channel
            or not a.get("source_float32_le_sha256")
            or not w.get("source_float32_le_sha256")):
        raise ValueError("Missing verified source Float32 window")
    n=spectrum.get("n_fft")
    xs=spectrum.get("frequency_hz")
    ys=spectrum.get("amplitude")
    if (type(n) is not int or n<2 or n&(n-1)
            or not isinstance(xs,(list,tuple)) or not isinstance(ys,(list,tuple))
            or len(xs)!=n//2 or len(ys)!=n//2):
        raise ValueError("Full N/2 FFT absent from current source")
    if not math.isfinite(float(wave.get("rms_m_s2",float("nan")))):
        raise ValueError("PageAdc source RMS invalid")
    return {
        "source":SOURCE,"adc":flow.channel,
        "source_bin_sha256":record["source_bin_sha256"],
        "wave_input_float32_sha256":a["source_float32_le_sha256"],
        "spectrum_input_float32_sha256":w["source_float32_le_sha256"],
        "full_spectrum_bins":n//2,
        "source_dsp_tick":None if flow.direct_bin else flow.tick_index,
        "independent_core_results_used":True,
        "different_time_windows_allowed":True,
        "physical_calibration_verified":False,
        "original_win32_same_run_verified":False,
        "hardware_commands_sent":False,
    }


def source_adc_envelope_axes(flow:OfflineMeasurementFlow, trace:dict, tag:int)->dict:
    """Source PageAdc FIR X: original raw H, actual post-filter XScale.

    Unit128 00847F0D computes the *raw* GetSignal length from H/Fs.
    Unit115 GetSignal 007D0C8D expands that length with the filter's
    GetAdjustedEnvelopeLength 007D1158, then writes OutputLength and
    OutputSampleRate at +28/+2C. Unit128 00848033..00848079 uses
    that *output* rate for Series.XScale. The same 0084B2F8 source H
    menu keeps ScrLeft=H and ScrWidth=-H. Thus a valid output can
    extend beyond the H viewport: original TQGrapher clips, not pads.

    This is source-derived signal/geometry, NOT Win32 pixel parity or
    exact running Delphi/x87 FIR numerical parity.
    """
    from hashlib import sha256
    from .envelope_idr_candidate import envelope_plan

    if not isinstance(flow,OfflineMeasurementFlow) or not isinstance(trace,dict):
        raise ValueError("Source FIR requires verified PageAdc flow and trace")
    raw=source_adc_horizontal_view(flow,tag)
    rec=flow.source_record()
    if (trace.get("channel")!=flow.channel
            or trace.get("file")!=rec["data_file_label"]
            or trace.get("display_order")!="getsignal_buffer"):
        raise ValueError("Source FIR output belongs to another ADC/BIN or order")
    code=trace.get("code")
    if type(code) is not int or not 1<=code<=31:
        raise ValueError("Source FIR requires original EnvelopeCode 1..31")
    full=np.asarray(trace.get("cursor_full_samples_float32"))
    if (full.ndim!=1 or full.dtype!=np.dtype("<f4")
            or not 1<=full.size<=10_000_000
            or not bool(np.isfinite(full).all())):
        raise ValueError("Source FIR needs ALL actual finite Float32 samples")
    full_digest=sha256(np.asarray(full,dtype="<f4").tobytes()).hexdigest()
    if (full_digest!=trace.get("cursor_full_samples_sha256")
            or full_digest!=trace.get(
                "post_fir_getsignal_return_float32_sha256")):
        raise ValueError("Source FIR full-output SHA does not match reversed GetSignal")
    if trace.get("output_samples")!=int(full.size):
        raise ValueError("Source FIR output count differs from full buffer")
    rate=trace.get("output_sample_rate_hz")
    if (type(rate) not in (int,float) or not math.isfinite(rate)
            or rate<=0 or not float(rate).is_integer()):
        raise ValueError("Source FIR rate must be actual integer OutputSampleRate")
    rate=int(rate)
    if rate>int(raw["actual_sample_rate_hz"]):
        raise ValueError("Source FIR cannot oversample original GetSignal")
    plan=envelope_plan(
        raw["requested_samples"],int(raw["actual_sample_rate_hz"]),code)
    if rate!=plan["reported_output_rate_hz"]:
        raise ValueError("Source FIR output rate differs from source filter chain")
    win=trace.get("input_source_window")
    if (not isinstance(win,dict) or win.get("channel")!=flow.channel
            or not isinstance(win.get("source_float32_le_sha256"),str)
            or win.get("sample_rate_hz")!=raw["actual_sample_rate_hz"]
            or win.get("no_zero_padding") is not True
            or win.get("source_sample_count")!=plan["adjusted_input_length"]):
        raise ValueError("Source FIR input must contain full adjusted history")
    first=win.get("first_archive_sample_index")
    last=win.get("last_archive_sample_exclusive")
    if (type(first) is not int or type(last) is not int
            or first<0 or last-first!=plan["adjusted_input_length"]
            or last>rec["sample_count"]):
        raise ValueError("Source FIR input archive coordinates are inconsistent")
    xvals=trace.get("time_s")
    yvals=trace.get("amplitude")
    if (not isinstance(xvals,(tuple,list))
            or not isinstance(yvals,(tuple,list))
            or not 1<=len(xvals)==len(yvals)<=200_000):
        raise ValueError("Source FIR plotted LOD is missing")
    scalar=1. if raw["milliseconds"]>=10000 else 1000.
    unit="с" if scalar==1. else "мс"
    left=float(np.float32(raw["milliseconds"]/1000.
                           if scalar==1. else raw["milliseconds"]))
    xscale=float(np.float32(scalar/rate))
    xx=tuple(float(np.float32(float(t)*scalar)) for t in xvals)
    if (not math.isfinite(xscale) or xscale<=0 or
            not all(math.isfinite(x) and x>=-1e-5 and
                    x<=full.size/rate*scalar+0.01 for x in xx)):
        raise ValueError("Source FIR graph X outside actual filter output")
    return {
        "source":SOURCE,"kind":"SOURCE_FIR","tag":tag,
        "selected_adc":flow.channel,
        "source_bin_sha256":raw["source_bin_sha256"],
        "source_window_sha256":win["source_float32_le_sha256"],
        "filtered_float32_sha256":full_digest,
        "profile_source":trace.get("profile_source"),
        "local_original_idp_sha_verified":(
            trace.get("profile_source")==
            "USER_SUPPLIED_LOCAL_IDP_SHA256_VERIFIED"),
        "envelope_code":code,
        "axis_unit":unit,"axis_scale_from_seconds":scalar,
        "axis_max":left,"scr_left_single":left,
        "scr_width_single":float(np.float32(-left)),
        "series_xscale_single":xscale,
        "series_samples":int(full.size),
        "output_sample_rate_hz":rate,
        "requested_raw_samples":raw["requested_samples"],
        "required_input_samples":plan["adjusted_input_length"],
        "real_adjusted_history_verified":True,
        "historical_fir_latency_to_archive_time_verified":False,
        "source_full_reverse_buffer_verified":True,
        "plot_x_single":xx,
        "data_or_filtered_array_recomputed_by_axes":False,
        "original_delphi_x87_output_numeric_parity_verified":False,
        "original_win32_gdi_pixel_parity_verified":False,
    }


def source_adc_envelope_cursor(flow:OfflineMeasurementFlow, trace:dict,
                               axes:dict,x_coord:float)->dict:
    """Source FIR X to full filtered output index, not a LOD vertex.

    The filter's absolute archive event time is intentionally *not*
    inferred from start_s: FIR history/phase latency was not proven.
    """
    if not isinstance(flow,OfflineMeasurementFlow) or not isinstance(axes,dict):
        raise ValueError("Bound source FIR axes required")
    rec=flow.source_record()
    win=trace.get("input_source_window") if isinstance(trace,dict) else None
    if (axes.get("kind")!="SOURCE_FIR"
            or axes.get("selected_adc")!=flow.channel
            or axes.get("source_bin_sha256")!=rec["source_bin_sha256"]
            or not isinstance(win,dict)
            or win.get("channel")!=flow.channel
            or win.get("source_float32_le_sha256")!=axes.get("source_window_sha256")
            or trace.get("cursor_full_samples_sha256")!=axes.get(
                "filtered_float32_sha256")
            or trace.get("post_fir_getsignal_return_float32_sha256")!=axes.get(
                "filtered_float32_sha256")
            or trace.get("output_samples")!=axes.get("series_samples")
            or trace.get("code")!=axes.get("envelope_code")
            or trace.get("display_order")!="getsignal_buffer"):
        raise ValueError("Source FIR axes are stale or belong to another BIN/ADC")
    if (isinstance(x_coord,bool) or not isinstance(x_coord,(int,float))
            or not math.isfinite(x_coord)
            or not 0.<=x_coord<=axes["axis_max"]):
        raise ValueError("Source FIR cursor outside original H viewport")
    rate=axes["output_sample_rate_hz"]
    scalar=axes["axis_scale_from_seconds"]
    index=int(math.floor(x_coord/scalar*rate+0.5))
    if not 0<=index<axes["series_samples"]:
        raise ValueError("Source FIR cursor beyond real output (no fake tail)")
    return {
        "source":SOURCE,"kind":"SOURCE_FIR",
        "output_index":index,
        "output_buffer_relative_s":index/rate,
        "plot_x":index/rate*scalar,
        "original_reversed_output_index":axes["series_samples"]-1-index,
        "selected_adc":flow.channel,
        "source_bin_sha256":rec["source_bin_sha256"],
        "filtered_float32_sha256":axes["filtered_float32_sha256"],
        "original_absolute_fir_sample_time_verified":False,
        "original_win32_mouse_pixel_parity_verified":False,
    }
