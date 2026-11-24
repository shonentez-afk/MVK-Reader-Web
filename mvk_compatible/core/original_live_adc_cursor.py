"""Original-structure PageAdc LIVE mouse cursor over real full GetSignal.

PRIVATE evidence (not distributed): Projects.7z/_Unit115.pas
TQGrapher.UpdateCursor 007CA75C/007CA76C/007CABE4 and
Projects.7z/_Unit128.pas pbAdcMouseMove 0084B4AC, plus the
owner IDR SQLite and DFM. The original uses X (ignores mouse Y),
strict PixelLeft..Right, reversed GetSignal, pmXor clGreen and
CursorAveraging=1 with FindPreciseXValue=False at construction.

This module does NOT reconstruct Win32 GDI device pixels, x87
rounding, or an instrument absolute timestamp. It NEVER reads TCP
or calls the hardware. It also never uses plotted LOD samples.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math

import numpy as np

from .native_r6_live_preview import LivePreview
from .original_adc_view_controls import ADC_HORIZONTAL_MS

SOURCE="SOURCE_PAGEADC_LIVE_FULL_FLOAT32_CURSOR_STAGE111Z31CW"


@dataclass(frozen=True)
class SourceLiveWaveCursor:
    session_id: str
    adc: int
    h_tag: int
    mode: str
    source_input_sha256: str
    source_getsignal_sha256: str
    full_reversed_getsignal: np.ndarray
    first_absolute_sample_index: int
    end_absolute_sample_exclusive: int
    sample_rate_hz: int
    axis_unit: str
    axis_max: float
    xscale_single: float
    source_ring_provenance_verified: bool


def bind_source_live_wave_cursor(wave:dict,preview:LivePreview,adc:int
                                 )->SourceLiveWaveCursor:
    """Check the entire current source buffer ONCE, not on every MouseMove."""
    if not isinstance(wave,dict) or not isinstance(preview,LivePreview):
        raise ValueError("LIVE cursor requires a recorded verified preview")
    if type(adc) is not int or adc not in preview.channels:
        raise ValueError("LIVE cursor cannot use a different ADC")
    channel=preview.channels[adc]
    tag=wave.get("original_bAdcHScale_tag")
    if type(tag) is not int or not 0<=tag<len(ADC_HORIZONTAL_MS):
        raise ValueError("LIVE cursor requires exact original PageAdc H Tag")
    milliseconds=ADC_HORIZONTAL_MS[tag]
    rate=channel.rate_hz
    requested=rate*milliseconds//1000
    full=wave.get("cursor_full_reversed_getsignal")
    evidence=wave.get("input_source_window")
    if (not isinstance(full,np.ndarray) or full.ndim!=1
            or full.dtype!=np.dtype("<f4") or full.flags.writeable
            or full.size!=requested or wave.get("window_samples")!=requested
            or wave.get("source_getsignal_exact_selected_count") is not True
            or wave.get("sample_rate_hz")!=rate
            or wave.get("channel")!=adc
            or wave.get("original_bAdcHScale_milliseconds")!=milliseconds
            or wave.get("mode") not in ("ac","acdc")
            or not isinstance(evidence,dict)):
        raise ValueError("LIVE cursor full GetSignal/HTag is stale or incomplete")
    digest=sha256(full.tobytes()).hexdigest()
    if (digest!=wave.get("cursor_full_reversed_sha256")
            or sha256(channel.samples.tobytes()).hexdigest()!=channel.sha256
            or evidence.get("preview_source_calibrated_sha256")!=channel.sha256
            or wave.get("cursor_full_source_window_sha256")!=
                evidence.get("source_float32_le_sha256")):
        raise ValueError("LIVE cursor full GetSignal/Go input SHA mismatch")
    first=evidence.get("live_first_adc_sample_index")
    end=evidence.get("live_last_adc_sample_exclusive")
    if (type(first) is not int or type(end) is not int
            or first<0 or end-first!=requested):
        raise ValueError("LIVE cursor has no valid uint64 source index window")
    scale=1. if milliseconds>=10000 else 1000.
    xmax=milliseconds/1000. if milliseconds>=10000 else float(milliseconds)
    xscale=float(np.float32(scale/rate))
    if (not 0.<xscale<=xmax or
            wave.get("cursor_axis_unit")!=("с" if scale==1. else "мс")
            or wave.get("cursor_axis_max")!=xmax
            or not math.isclose(wave.get("cursor_xscale_single",0.),
                                xscale,rel_tol=1e-7)):
        raise ValueError("LIVE cursor X geometry differs from source HScale")
    return SourceLiveWaveCursor(
        session_id=preview.session_id,adc=adc,h_tag=tag,mode=wave["mode"],
        source_input_sha256=channel.sha256,
        source_getsignal_sha256=digest,full_reversed_getsignal=full,
        first_absolute_sample_index=first,
        end_absolute_sample_exclusive=end,
        sample_rate_hz=rate,axis_unit=("с" if scale==1. else "мс"),
        axis_max=xmax,xscale_single=xscale,
        source_ring_provenance_verified=bool(
            preview.source_ring_provenance_verified))


def pick_source_live_wave_cursor(cursor:SourceLiveWaveCursor,x:float,
                                 *,adjacent_x:float|None=None)->dict|None:
    """Map graph X to the FULL reversed Float32 series and device index.

    When a second X for the next Qt pixel is supplied, choose the MAX
    SIGNED value from that one-pixel column, as in source 007CA9A5.
    Pixel slope/rounding is still a Qt-derived candidate (not Win32).
    """
    if not isinstance(cursor,SourceLiveWaveCursor):
        raise ValueError("LIVE cursor contract missing")
    if (isinstance(x,bool) or not isinstance(x,(int,float))
            or not math.isfinite(x)):
        raise ValueError("LIVE cursor X must be finite")
    if x<0 or x>cursor.axis_max:
        return None
    n=len(cursor.full_reversed_getsignal)
    first=math.trunc(float(x)/cursor.xscale_single)
    if not 0<=first<n:
        return None
    left=right=first
    if adjacent_x is not None:
        if (isinstance(adjacent_x,bool) or
                not isinstance(adjacent_x,(int,float))
                or not math.isfinite(adjacent_x)):
            raise ValueError("LIVE cursor next-pixel X must be finite")
        nxt=math.trunc(float(adjacent_x)/cursor.xscale_single)
        left=max(0,min(first,nxt))
        right=min(n-1,max(first,nxt))
        if left>right:
            return None
    if left==right:
        idx=left
    else:
        # Win32 source (FindPreciseXValue=False) chooses a signed
        # peak in its current one-pixel interval. Do not take max(abs).
        idx=left+int(np.argmax(cursor.full_reversed_getsignal[left:right+1]))
    value=float(cursor.full_reversed_getsignal[idx])
    absolute=cursor.end_absolute_sample_exclusive-1-idx
    if not cursor.first_absolute_sample_index<=absolute<cursor.end_absolute_sample_exclusive:
        raise ValueError("LIVE cursor cannot invent absolute ADC indices")
    return {
        "source":SOURCE,"adc":cursor.adc,
        "source_session_id":cursor.session_id,"source_h_tag":cursor.h_tag,
        "output_index":idx,
        "column_first_index":left,"column_last_index_inclusive":right,
        "plot_x":float(np.float32(idx*cursor.xscale_single)),
        "axis_unit":cursor.axis_unit,
        "full_float32_value":value,
        **({"original_uint64_tach_byte_index":absolute,
            "source_index_kind":"CAPTURE_LOCAL_TACH_BYTE"} if cursor.adc>=9 else
           {"original_uint64_adc_sample_index":absolute,
            "original_uint32_sample_index":absolute&0xFFFFFFFF}),
        "source_input_sha256":cursor.source_input_sha256,
        "source_getsignal_sha256":cursor.source_getsignal_sha256,
        "source_ac_dc_mode":cursor.mode,
        "uses_full_getsignal_not_plot_lod":True,
        "source_column_signed_peak_candidate":adjacent_x is not None,
        "original_win32_pixel_rounding_parity_verified":False,
        "original_delphi_numeric_parity_verified":False,
        "physical_sensor_calibration_verified":False,
        "device_io_performed":False,
    }
