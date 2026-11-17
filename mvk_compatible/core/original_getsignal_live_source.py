"""Source GetSignal/CheckDataAvailability runtime, source Mode2 PageAdc.

Private triple-source provenance (not bundled): mvkview.idp addresses
007D0C30 / 007D1998 / 00847EAC; Projects.7z _Unit115.pas +
_Unit128.pas; mvk_idr(1).sqlite function/call graph.

GetSignal Length is calculated from bAdcHScale Tag integer milliseconds,
not from the current size of a preview or arbitrary 30s live window.
CheckDataAvailability compares UInt64 FRxPos - LastProcessedPos to
SignalLength, with AllowOverlap+not-Contiguous special case and a
2^21 source storage overwrite exception. This is a read-only LOCAL
reconstruction, not a claim that this app has the same 2M storage.
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE_BUFFER_SAMPLES = 0x200000
UINT64_MAX=(1<<64)-1
SOURCE = "ORIGINAL_GETSIGNAL_CHECK_DATA_AVAILABILITY_007D1998"

@dataclass(frozen=True)
class OriginalGetSignalReadiness:
    original_check_data_availability: bool
    verified_preview_window_ready: bool
    source_buffer_samples: int
    source_rxpos_64: int
    source_last_processed_pos_64: int
    source_valid_pos_64: int
    requested_samples: int
    selected_window_start_pos_64: int | None
    selected_window_end_pos_64: int | None
    next_processed_pos_64: int | None
    source_contiguous: bool
    source_allow_overlap: bool
    source: str = SOURCE
    original_dsp_runtime_parity_verified: bool = False

    def receipt(self) -> dict:
        return {
            "source": self.source,
            "original_check_data_availability":
                self.original_check_data_availability,
            "verified_preview_window_ready":
                self.verified_preview_window_ready,
            "source_buffer_samples":self.source_buffer_samples,
            "source_rxpos_64":self.source_rxpos_64,
            "source_last_processed_pos_64":self.source_last_processed_pos_64,
            "source_valid_pos_64":self.source_valid_pos_64,
            "requested_samples":self.requested_samples,
            "selected_window_start_pos_64":self.selected_window_start_pos_64,
            "selected_window_end_pos_64":self.selected_window_end_pos_64,
            "next_processed_pos_64":self.next_processed_pos_64,
            "source_contiguous":self.source_contiguous,
            "source_allow_overlap":self.source_allow_overlap,
            "original_dsp_runtime_parity_verified":False,
        }


def _uint(value:int,label:str,*,max_value:int=UINT64_MAX)->int:
    if type(value) is not int or not 0 <= value <= max_value:
        raise ValueError(f"{label} must be a nonnegative source unsigned integer")
    return value


def source_getsignal_readiness(
    *, rx_pos:int, valid_pos:int, last_processed_pos:int,
    signal_length:int, contiguous:bool, allow_overlap:bool,
    preview_samples:int, buffer_samples:int=SOURCE_BUFFER_SAMPLES,
)->OriginalGetSignalReadiness:
    """Source 007D1998 availability + separate fail-closed preview check.

    The original special case AllowOverlap=True/Contiguous=False allows
    GetSignal to proceed without enough fresh samples, then its internal
    buffer reader may zero-fill missing data. We NEVER authorize that for
    an independently verified real-only preview. Its second Boolean is
    strictly the *existing* Go preview length; never fake signal bytes.

    The original contiguous overflow exception is emitted separately:
    if FRxPos-LastProcessedPos > FBufferSize during a source-ready
    contiguous read, it raises "Buffer overflow due to insufficient
    processing speed", rather than returning a fabricated window.
    """
    rx=_uint(rx_pos,"FRxPos")
    valid=_uint(valid_pos,"FValidPos")
    last=_uint(last_processed_pos,"LastProcessedPos")
    length=_uint(signal_length,"SignalLength",max_value=(1<<32)-1)
    verified=_uint(preview_samples,"Preview samples",max_value=(1<<32)-1)
    buf=_uint(buffer_samples,"FBufferSize",max_value=(1<<32)-1)
    if (length==0 or buf==0 or buf&(buf-1) or
            valid>rx or last>rx or verified>buf or
            type(contiguous) is not bool or type(allow_overlap) is not bool):
        raise ValueError("Invalid original GetSignal source cursor/flags")
    fresh=rx-last
    source_ready=(
        (allow_overlap and not contiguous)
        or fresh>=length
    )
    if contiguous and source_ready and fresh>buf:
        raise OverflowError(
            "Buffer overflow due to insufficient processing speed")
    # _Unit115.GetSignal 007D0C64..007D0C86:
    # Contiguous increments LastProcessedPos by N; otherwise sets it
    # to the current 64-bit FRxPos. The selected window ends at that
    # resulting position and begins exactly N real samples earlier.
    end=(last+length if contiguous else rx) if source_ready else None
    start=(end-length if end is not None and end>=length else None)
    # 'valid_pos' models the original invalidation boundary. The
    # independent live window is MORE restrictive: its last 'verified'
    # calibrated Float32 samples are SHA-bound and no older data may
    # be silently loaded from 2M source ring or from an old session.
    safe=(
        source_ready and start is not None and
        start>=valid and rx-start<=buf and
        start>=rx-verified and end<=rx
    )
    return OriginalGetSignalReadiness(
        source_ready,bool(safe),buf,rx,last,valid,length,
        start,end,end if source_ready else None,
        contiguous,allow_overlap,
    )


def source_live_adc_menu_length(tag:int, sample_rate:int)->tuple[int,int]:
    """_Unit128:00847F0D source ADC H Tag -> Fs*ms div 1000."""
    from .original_adc_view_controls import ADC_HORIZONTAL_MS
    if type(tag) is not int or not 0<=tag<len(ADC_HORIZONTAL_MS):
        raise ValueError("Source bAdcHScale Tag 0..13 required")
    fs=_uint(sample_rate,"SelectedSampleRate",max_value=1_000_000)
    if fs==0:
        raise ValueError("No source ADC sample rate")
    milliseconds=ADC_HORIZONTAL_MS[tag]
    result=fs*milliseconds//1000
    if result==0 or result>(1<<32)-1:
        raise ValueError(
            "Selected original bAdcHScale cannot yield any real samples")
    return result,milliseconds
