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


def original_adc_vertical_options():
    return tuple({
        "tag":tag,"divisor":div,
        "caption":f"1/{div} диапазона Y",
        "original_source_table":"008D33F4",
    } for tag,div in enumerate(ADC_VERTICAL_DIVISORS))


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
    baseline=peak if peak>0 else 1.
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
        "y_min":-half,"y_max":half,
        "unit":"условн. ед. BIN" if flow.direct_bin else "расч. ед.",
        "original_graph_default_vscale_verified":False,
        "original_source_divider_verified":True,
        "original_delphi_canvas_parity_verified":False,
        "waveform_or_fir_data_mutated":False,
        "device_io_performed":False,
    }
