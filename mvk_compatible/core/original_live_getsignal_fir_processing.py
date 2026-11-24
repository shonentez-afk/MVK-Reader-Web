"""Source-backed live GetSignal: full FIR values, peak-preserving LOD and cursor.

Original triple-source contract:
  Projects.7z/_Unit115.pas 007D0C30, 007D1158, 007D1C48, 007D1E70;
  mvk_idr(1).sqlite same addresses + call graph;
  mvkview.idp source FIR taps/rates/stage metadata and private coefficient profile.

No hardware socket, no commands, no private FIR banks embedded. Only the
SHA-validated, rate/Freeze-admitted Go 2**21 ring returned by the local IPC
may be used for numerical candidates. Not audited Win32 x87 equivalence.
"""
from __future__ import annotations
import hashlib
import math
import numpy as np

from .envelope_idr_candidate import (
    EnvelopeProfile, envelope_plan, process_original_envelope_candidate,
)
from .original_adc_view_controls import ADC_HORIZONTAL_MS
from .storage_f_range_idr_candidate import prepare_original_fft_input,DOMAIN_ORIGINAL_STORAGE
from .original_source_long_window import SourceLongWindow


def source_live_fir_job_key(window, tag, code, mode=0):
    """Stable identity for a SINGLE Go ring snapshot and source selection."""
    req=window.request
    if (type(tag) is not int or not 0<=tag<len(ADC_HORIZONTAL_MS)
            or type(code) is not int or not 1<=code<=31):
        raise ValueError("Source filtered GetSignal Tag/Code invalid")
    return (req.session_id,req.request_id,req.adc,tag,code,int(mode))


def source_live_fir_configuration_key(window, tag, code):
    req=window.request
    return (req.session_id,req.adc,tag,code)


def source_live_filtered_getsignal(
        window:SourceLongWindow, profile:EnvelopeProfile,
        *,tag:int,code:int,mode:int=0,
        max_plot_points:int=4000,cancelled=None)->dict:
    """Do full original-structure FIR off the GUI thread.

    A synthetic test profile may test arithmetic, but Qt authorizes ONLY
    profile.provenance == USER_SUPPLIED_LOCAL_IDP_SHA256_VERIFIED.
    The original Ring-selected HTag/ADC/code must survive a SHA recheck.
    Never pad, truncate input, relabel a plain preview or multiply the
    already calibrated source a second time.
    """
    if not isinstance(window,SourceLongWindow) or not isinstance(profile,EnvelopeProfile):
        raise ValueError("Source GetSignal requires source window and FIR profile")
    if type(max_plot_points) is not int or not 64<=max_plot_points<=20000:
        raise ValueError("Source GetSignal invalid plot budget")
    req=window.request
    job_key=source_live_fir_job_key(window,tag,code,mode)
    if (req.h_tag!=-3 or req.original_h_tag!=tag or req.envelope_code!=code or
            req.original_bspec_lines!=0 or
            window.preview.source_ring_provenance_verified is not True or
            window.preview.session_id!=req.session_id):
        raise ValueError("Filtered GetSignal: foreign local ring/HTag/FIR request")
    channel=window.preview.channels.get(req.adc)
    if (channel is None or channel.rate_hz!=req.sample_rate_hz or
            channel.captured_samples!=req.capture_end):
        raise ValueError("Filtered GetSignal: stale ADC/Fs/FRxPos")
    input_values=channel.samples
    selected=req.sample_rate_hz*ADC_HORIZONTAL_MS[tag]//1000
    plan=envelope_plan(selected,req.sample_rate_hz,code)
    if (req.samples!=plan['adjusted_input_length'] or
            len(input_values)!=req.samples):
        raise ValueError("Filtered GetSignal: full original history not available")
    if cancelled is not None and cancelled():
        raise InterruptedError("Filtered GetSignal stopped before DSP")
    digest=hashlib.sha256(input_values.tobytes()).hexdigest()
    if digest!=channel.sha256:
        raise ValueError("Filtered GetSignal: original Go ring SHA mismatch")
    scale=channel.source_f_range_single
    normalized=prepare_original_fft_input(input_values,f_range=scale,
        input_domain=DOMAIN_ORIGINAL_STORAGE)["samples_before_dc_removal"]
    dsp=process_original_envelope_candidate(
        normalized,req.sample_rate_hz,code,profile,
        f_range=scale,cancelled=cancelled)
    full=np.asarray(dsp['getsignal_buffer'],dtype='<f4')
    if (len(full)==0 or not np.all(np.isfinite(full)) or
            not np.array_equal(full,dsp['chronological'][::-1])):
        raise ValueError("Filtered GetSignal: reversed output invalid")
    if cancelled is not None and cancelled():
        raise InterruptedError("Filtered GetSignal interrupted after DSP")
    full.setflags(write=False)
    fs_out=dsp['output_sample_rate_hz']
    # Strict ≤budget peak-preserving full-resolution projection; cursor
    # uses FULL processed float32, never decimated plot coordinates.
    n=len(full)
    if n<=max_plot_points:
        indices=np.arange(n,dtype=np.int64)
    else:
        segment=math.ceil((n-2)/((max_plot_points-2)//2))
        picked=[0]
        for start in range(1,n-1,segment):
            if cancelled is not None and cancelled():
                raise InterruptedError("Filtered GetSignal interrupted during LOD")
            stop=min(n-1,start+segment)
            part=full[start:stop]
            minimum=start+int(np.argmin(part))
            maximum=start+int(np.argmax(part))
            picked.extend(sorted({minimum,maximum}))
        picked.append(n-1)
        indices=np.asarray(picked,dtype=np.int64)
    if len(indices)>max_plot_points or len(indices)>n:
        raise ValueError("Filtered GetSignal: plot LOD exceeded budget")
    result=dict(
        job_key=job_key,configuration_key=source_live_fir_configuration_key(
            window,tag,code),
        source_session_id=req.session_id,source_request_id=req.request_id,
        adc=req.adc,source_h_tag=tag,envelope_code=code,source_mode=mode,
        source_rate_hz=req.sample_rate_hz,
        original_selected_ms=ADC_HORIZONTAL_MS[tag],
        received_samples=req.capture_end,
        source_pre_fir_samples=req.samples,
        output_samples=n,
        output_rate_hz=fs_out,
        full_reversed_getsignal=full,
        output_float32_sha256=hashlib.sha256(full.tobytes()).hexdigest(),
        source_float32_sha256=digest,
        plot_x_ms=indices.astype(np.float64)*1000./fs_out,
        # Source 0084B2F8 chooses seconds for H>=10 s and ms below.
        # Existing plot_x_ms remains for backward-compatible core callers.
        source_cursor_axis_unit=("с" if ADC_HORIZONTAL_MS[tag]>=10000 else "мс"),
        source_cursor_axis_max=(ADC_HORIZONTAL_MS[tag]/1000.
                                if ADC_HORIZONTAL_MS[tag]>=10000
                                else float(ADC_HORIZONTAL_MS[tag])),
        source_cursor_plot_x=(indices.astype(np.float64)/fs_out
                              if ADC_HORIZONTAL_MS[tag]>=10000
                              else indices.astype(np.float64)*1000./fs_out),
        plot_y=full[indices],
        plot_points=len(indices),
        rms_m_s2=dsp['rms_m_s2'],
        f_range_applied_to_calibrated_input=1.0,
        calibration_already_applied=True,
        live_original_f_range_single=scale,
        live_original_f_range_source=(channel.source_range_state or {}).get("origin","TmvkChannelStorage.Create_007D0A61"),
        source_range_state=channel.source_range_state,
        native_bin_exporter_gain_applied=False,
        original_delphi_numerical_parity_verified=False,
        original_canvas_cursor_parity_verified=False,
    )
    result['plot_y'].setflags(write=False)
    return result


def source_live_filtered_cursor(
        result:dict,x_ms:float,*,adjacent_x_ms:float|None=None)->dict|None:
    """Select from FULL reversed FIR, optionally using one logical pixel.

    The existing no-adjacent-X call retains its tested nearest-index
    candidate. With adjacent_x_ms, source UpdateCursor 007CA9A5
    prefers the signed Y peak of the current pixel column. Without
    actual running Win32 PixelLeft/stoiM this remains a Qt candidate.
    """
    if (not isinstance(result,dict) or isinstance(x_ms,bool)
            or not isinstance(x_ms,(int,float)) or not math.isfinite(x_ms)):
        raise ValueError("Filtered cursor requires a valid full-data result and X")
    values=result["full_reversed_getsignal"]
    fs=result["output_rate_hz"]
    if x_ms<0 or x_ms>result["original_selected_ms"] or len(values)==0:
        return None
    first=math.floor(float(x_ms)*fs/1000.+.5)
    if not 0<=first<len(values):
        return None
    left=right=first
    if adjacent_x_ms is not None:
        if (isinstance(adjacent_x_ms,bool) or
                not isinstance(adjacent_x_ms,(int,float))
                or not math.isfinite(adjacent_x_ms)):
            raise ValueError("Filtered next-pixel X must be finite")
        second=math.floor(float(adjacent_x_ms)*fs/1000.+.5)
        left=max(0,min(first,second))
        right=min(len(values)-1,max(first,second))
        if left>right:return None
    index=(left+int(np.argmax(values[left:right+1]))
           if right>left else left)
    return dict(
        output_index=index,
        plot_x_ms=index*1000./fs,
        value_from_full_filtered_float32=float(values[index]),
        output_float32_sha256=result['output_float32_sha256'],
        source_float32_sha256=result['source_float32_sha256'],
        source_session_id=result['source_session_id'],
        source_request_id=result['source_request_id'],
        source_pixel_signed_peak_candidate=adjacent_x_ms is not None,
        column_first_index=left,column_last_index_inclusive=right,
        original_delphi_cursor_parity_verified=False,
        original_win32_pixel_rounding_verified=False,
    )
