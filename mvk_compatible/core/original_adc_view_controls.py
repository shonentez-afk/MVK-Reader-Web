"""Source PageAdc 14x13 scales; bind GetSignal, actual ADC and visible Qt.

Private source evidence: owner IDR _Unit128.pas:
  0084AB98 dynamic popGraphHScale (14 items, gvar_008D33BC);
  0084B194 mAdcHScale1Click / 00847EAC integer GetSignal count;
  0084B22C mAdcVScale1Click / 0084B2F8 PaintBox scales;
  0084AF39 gvar_008D33F4 (13 divisors).
The two integer tables were independently re-read in the owner IDP.
Only derived numerical constants are distributed, not PAS/IDP/DFM bytes.

Source x-axis uses a reversed TQGrapher ScrWidth and localizable units.
Qt still has a chronological versus GetSignal-buffer display choice.
The Y baseline below is a documented LOCAL source-window peak candidate:
it is NOT the original GraphDefaultVScale, Delphi x87 or sensor calibration.
"""
from __future__ import annotations

from hashlib import sha256
import math

import numpy as np

from .offline_measurement_flow import OfflineMeasurementFlow
from .direct_bin_session import DirectBinSession
from .spectrum_graph_default_vscale_idr_candidate import (
    spectrum_graph_default_vscale,
)

SOURCE="SOURCE_DERIVED_ADC_HV_GETSIGNAL_CORE_QT_STAGE111Z31BW"
ADC_HORIZONTAL_MS=(20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1)
ADC_VERTICAL_DIVISORS=(1,2,5,10,20,50,100,200,500,1000,2000,5000,10000)


def _tag(name,value,count):
    if type(value) is not int or not 0 <= value < count:
        raise ValueError(f"{name}: original source Tag outside menu")
    return value


def original_adc_horizontal_options():
    return tuple({
        "tag":tag, "milliseconds":ms, "seconds":ms/1000.,
        "caption":f"{ms//1000} с" if ms>=1000 else f"{ms} мс",
        "original_source_table": "008D33BC",
    } for tag,ms in enumerate(ADC_HORIZONTAL_MS))


def original_adc_vertical_physical_caption(tag:int, baseline_m_s2:float)->str:
    """Original PageAdc Y popup: nominal physical height, not a divisor.

    Original IDP 008D33F4 holds 13 Y divisors; the screen captions are
    their numeric heights relative to the channel's GraphDefaultVScale.
    In the screenshot the base is 1000, so Tag0..12 read
    1000,500,200,...,0.1 m/s2. A caller without verified FRange must
    label its *local* baseline as uncalibrated; formatting never grants
    physical device calibration.
    """
    tag=_tag("ADC V",tag,len(ADC_VERTICAL_DIVISORS))
    if (isinstance(baseline_m_s2,bool) or
            not isinstance(baseline_m_s2,(int,float)) or
            not math.isfinite(float(baseline_m_s2)) or baseline_m_s2<=0):
        raise ValueError("ADC Y captions need finite positive current baseline")
    height=float(baseline_m_s2)/ADC_VERTICAL_DIVISORS[tag]
    if not math.isfinite(height) or height<=0:
        raise ValueError("ADC Y caption cannot represent current height")
    # Exactly original operator text unit "м/с2" (not a fictitious
    # dimensionless menu "1/N диапазона Y"). Russian decimal comma.
    return f"{height:.9g}".replace(".",",")+" м/с2"


def original_adc_vertical_options(*, baseline_m_s2:float|None=None):
    return tuple({
        "tag":tag,"divisor":div,
        "caption":(original_adc_vertical_physical_caption(
            tag,baseline_m_s2) if baseline_m_s2 is not None
            else f"1/{div} диапазона Y"),
        "original_source_table":"008D33F4",
    } for tag,div in enumerate(ADC_VERTICAL_DIVISORS))


def local_adc_vertical_peak_fit(peak:float)->float:
    """Safe *local* 1/2/5 Y baseline using the verified FULL window peak.

    When TSXML FRange is unknown, avoid presenting a long, spurious
    0,229360819 m/s2 scale derived from an arbitrary raw Float32 peak.
    The source original builds its Y menu from channel FRange instead;
    this 20%-headroom fallback is explicitly NOT that algorithm or device
    calibration. Never fit to the reduced on-screen curve.
    """
    if (isinstance(peak,bool) or not isinstance(peak,(float,int))
            or not math.isfinite(float(peak)) or float(peak)<0):
        raise ValueError("ADC local Y baseline needs a finite positive peak")
    target=max(1e-12,float(peak)*1.2)
    if not math.isfinite(target):
        raise ValueError("ADC local Y baseline peak overflows")
    decade=10.**math.floor(math.log10(target))
    for step in (1.,2.,5.,10.):
        candidate=decade*step
        if candidate>=target*(1.-1e-12) and math.isfinite(candidate):
            return float(candidate)
    raise ValueError("ADC local Y baseline cannot fit peak")


def source_live_adc_vertical_view(*,full_peak:float,tag:int,
                                  source_frange1:bool)->dict:
    """Pure live Y view over accepted Go Float32; no TX or new GetSignal.

    Source original TMvkChannelStorage.FRange=1 is allowed only when the
    caller has independently verified original source-ring provenance.
    Otherwise fit the FULL (not LOD) waveform peak locally to 1/2/5.
    This view only sets TQGrapher-equivalent bounds; physical calibration
    and original x87 numerical parity are not thereby certified.
    """
    tag=_tag("ADC V",tag,len(ADC_VERTICAL_DIVISORS))
    if type(source_frange1) is not bool:
        raise ValueError("Source FRange1 provenance must be explicit")
    if (isinstance(full_peak,bool) or not isinstance(full_peak,(int,float))
            or not math.isfinite(float(full_peak)) or float(full_peak)<0):
        raise ValueError("Live ADC full peak must be finite/nonnegative")
    if source_frange1:
        graph=spectrum_graph_default_vscale(1.0,1)
        baseline=float(graph["candidate_graph_default_vscale_single"])
        origin="SOURCE_LIVE_FRANGE1_GRAPH_DEFAULT_X87_UNATTESTED"
    else:
        baseline=local_adc_vertical_peak_fit(full_peak)
        origin="LIVE_PREVIEW_LOCAL_125_UNCALIBRATED"
    divisor=ADC_VERTICAL_DIVISORS[tag]
    half=float(np.float32(baseline/divisor))
    if not math.isfinite(half) or half<=0:
        raise ValueError("Live ADC Y scale is not a finite positive Single")
    return {
        "source":SOURCE,"tag":tag,"divisor":divisor,
        "axis_baseline_m_s2_nominal":baseline,
        "source_f_range1_verified":source_frange1,
        "axis_baseline_origin":origin,
        "window_peak_from_full_source":float(full_peak),
        "local_half_height":half,"y_min":-half,"y_max":half,
        "original_delphi_canvas_parity_verified":False,
        "physical_sensor_calibration_verified":False,
        "wave_samples_recomputed_by_view":False,
        "device_io_performed":False,
    }


def source_adc_horizontal_view(flow:OfflineMeasurementFlow,tag:int)->dict:
    """Integer GetSignal request length: SelectedSampleRate * ms // 1000.

    No zero padding or resampling; the presentation may be shorter if the
    selected verified file contains less data than the requested duration.
    """
    if not isinstance(flow,OfflineMeasurementFlow):
        raise ValueError("A verified selected measurement is required")
    tag=_tag("ADC H",tag,len(ADC_HORIZONTAL_MS))
    record=flow.source_record()
    fs=float(record["sample_rate_hz"])
    if not math.isfinite(fs) or fs<1 or not fs.is_integer():
        raise ValueError("Original ADC H menu requires integral sample rate")
    ms=ADC_HORIZONTAL_MS[tag]
    requested=int(fs)*ms//1000
    if requested < 1 or requested>30_000_000:
        raise ValueError("Selected original H scale cannot produce valid samples")
    return {
        "source":SOURCE,"tag":tag,"milliseconds":ms,
        "caption":original_adc_horizontal_options()[tag]["caption"],
        "nominal_seconds":ms/1000.,"requested_samples":requested,
        "getsignal_seconds":requested/fs,
        "actual_sample_rate_hz":fs,"selected_adc":flow.channel,
        "source_bin_sha256":record["source_bin_sha256"],
        "original_integer_length_reconstructed":True,
        "original_windows_canvas_x_parity_verified":False,
        "device_io_performed":False,
    }


def validate_source_adc_horizontal_trace(flow:OfflineMeasurementFlow,
                                         trace:dict,choice:dict)->dict:
    """Check a real unfiltered GetSignal against selected menu/sample count."""
    if not isinstance(trace,dict) or not isinstance(choice,dict):
        raise ValueError("Source ADC trace/menu contract required")
    current=source_adc_horizontal_view(flow,choice.get("tag"))
    if current!=choice:
        raise ValueError("Stale ADC H scale source or changed selected BIN/ADC")
    if trace.get("channel")!=flow.channel:
        raise ValueError("GetSignal trace belongs to another ADC")
    fs=current["actual_sample_rate_hz"]
    if trace.get("sample_rate_hz")!=fs:
        raise ValueError("GetSignal did not use actual sample rate")
    start=float(trace["start_s"])
    if not math.isfinite(start) or start<0:
        raise ValueError("Invalid original waveform start")
    sample_index=round(start*fs)
    remaining=flow.source_record()["sample_count"]-sample_index
    expected=min(current["requested_samples"],remaining)
    if expected<1 or trace.get("window_samples")!=expected:
        raise ValueError("Rendered GetSignal count differs from original H request")
    if not isinstance(trace.get("input_source_window"),dict):
        raise ValueError("GetSignal missing verified input Float32 window")
    if trace.get("requested_window_truncated_by_archive_end")!=(expected<current["requested_samples"]):
        raise ValueError("Original H window truncated flag inconsistent with real archive")
    return {
        **current,"actual_window_samples":expected,
        "truncated_by_archive_end":expected<current["requested_samples"],
        "source_input_window_verified":True,
        "fft_or_signal_recomputed_by_view":False,
    }


def source_adc_vertical_view(flow:OfflineMeasurementFlow,trace:dict,tag:int,
                             *,bound_source_sha256:str)->dict:
    """Source 13 divider tags, local positive peak computed from FULL Core.

    For plain GetSignal its 'peak_m_s2' is calculated before waveform LOD.
    For FIR the un-decimated immutable Float32 cursor must match its SHA.
    Neither result is claimed to be the original source GraphDefaultVScale.
    """
    if not isinstance(flow,OfflineMeasurementFlow) or not isinstance(trace,dict):
        raise ValueError("Actual ADC flow and calculated waveform required")
    tag=_tag("ADC V",tag,len(ADC_VERTICAL_DIVISORS))
    record=flow.source_record()
    if (bound_source_sha256!=record["source_bin_sha256"]
            or trace.get("channel")!=flow.channel
            or trace.get("file")!=record["data_file_label"]
            or not isinstance(trace.get("input_source_window"),dict)):
        raise ValueError("Stale or wrong ADC/ZIP/BIN waveform for Y axis")
    if "cursor_full_samples_float32" in trace:
        full=np.asarray(trace["cursor_full_samples_float32"],dtype="<f4")
        if (full.ndim!=1 or full.size==0 or full.size>10_000_000
                or not bool(np.isfinite(full).all())
                or sha256(full.tobytes()).hexdigest()!=trace.get("cursor_full_samples_sha256")):
            raise ValueError("Full FIR waveform SHA/Float32 invalid")
        peak=float(np.max(np.abs(full)))
        basis="VERIFIED_FULL_POST_FIR_FLOAT32_NOT_PLOT_LOD"
    else:
        # The independent GetSignal calculates this peak BEFORE min/max LOD.
        peak=float(trace.get("peak_m_s2",float("nan")))
        if ("window_samples" not in trace or trace["window_samples"]<1
                or not math.isfinite(peak) or peak<0):
            raise ValueError("No original GetSignal full-window peak")
        basis="GETSIGNAL_FULL_WINDOW_PEAK_NOT_PLOT_LOD"
    baseline=local_adc_vertical_peak_fit(peak)
    baseline_origin="LOCAL_UNCALIBRATED_FULL_SIGNAL_PEAK_125_HEADROOM"
    frange=None
    graph_default=None
    x87_boundary_risk=False
    # The original Single TMvkChannelStorage.FRange is set from a positive
    # TSXML InternalChannelGain by the identified loader. Use this SAME
    # channel-scoped static metadata as the spectrum Core. Do not apply it
    # as physical calibration or infer it for a Native ZIP.
    if type(flow.session) is DirectBinSession:
        matches=[e for e in flow.session.channel_files if
                 e.adc==flow.channel and
                 e.bin_sha256==record["source_bin_sha256"]]
        if len(matches)!=1:
            raise ValueError("Source TSXML FRange from another BIN/ADC")
        meta=matches[0].source_metadata
        value=meta.original_f_range_single_candidate
        if value is not None:
            if (meta.data_type!="Single" or meta.gain_loader_branch!=
                    "DECLARED_POSITIVE_NO_APPLY_RANGE_SOURCE_BRANCH"):
                raise ValueError("Unsupported original loader FRange branch")
            frange=float(value)
            graph=spectrum_graph_default_vscale(frange,1)
            baseline=float(graph["candidate_graph_default_vscale_single"])
            graph_default=baseline
            x87_boundary_risk=bool(
                graph["original_x87_boundary_requires_runtime_reference"])
            baseline_origin="TSXML_FRANGE_125_GRAPH_DEFAULT_STATIC_CANDIDATE"
    divisor=ADC_VERTICAL_DIVISORS[tag]
    half=float(np.float32(baseline/divisor))
    if not math.isfinite(half) or half<=0:
        raise ValueError("ADC Y view not representable as positive Float32")
    return {
        "source":SOURCE,"tag":tag,"divisor":divisor,
        "selected_adc":flow.channel,
        "source_bin_sha256":record["source_bin_sha256"],
        "source_window_basis":basis,
        "window_peak_from_core":peak,
        "local_half_height":half,
        "axis_baseline_m_s2_nominal":baseline,
        "y_caption_unit_nominal_not_device_calibration":True,
        "axis_baseline_origin":baseline_origin,
        "source_f_range_single":frange,
        "graph_default_vscale_candidate":graph_default,
        "native_x87_boundary_risk":x87_boundary_risk,
        "original_graph_default_vscale_numeric_runtime_verified":False,
        "y_min":-half,"y_max":half,
        "unit":"условн. ед. BIN" if flow.direct_bin else "расч. ед.",
        "original_graph_default_vscale_verified":False,
        "original_source_divider_verified":True,
        "original_delphi_canvas_parity_verified":False,
        "waveform_or_fir_data_mutated":False,
        "device_io_performed":False,
    }
