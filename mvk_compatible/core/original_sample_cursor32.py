"""Source SampleHeader.Index is uint32; storage and Go RX positions are uint64.

Verify every device-cursor difference modulo 2**32 independently of the
real capture-local counter; never authorize invented samples or another run.
"""
from __future__ import annotations

U32_MOD=1 << 32
U32_MASK=U32_MOD-1


def u32_preview_bounds(first:int,end:int,count:int)->bool:
    return (type(first) is int and type(end) is int and type(count) is int
            and 0<=first<U32_MOD and 0<=end<U32_MOD
            and 0<count<U32_MOD and ((end-first)&U32_MASK)==count)


def u32_matches_go_status(
        preview_end:int,source_end:int|None,*,status_samples:int,
        window_samples:int,captured_samples:int|None=None)->bool:
    if (type(status_samples) is not int or status_samples<0
            or type(window_samples) is not int or window_samples<=0
            or status_samples<window_samples
            or type(preview_end) is not int
            or not 0<=preview_end<U32_MOD):
        return False
    if captured_samples is not None and (
            type(captured_samples) is not int
            or not window_samples<=captured_samples<=status_samples
            or captured_samples>=1<<64):
        return False
    if source_end is None:
        return True  # Older Go producer made no absolute-index claim.
    if type(source_end) is not int or not 0<=source_end<U32_MOD:
        return False
    lag=(status_samples-captured_samples if captured_samples is not None
         else status_samples-window_samples)
    if not 0<=lag<U32_MOD:
        return False
    delta=(source_end-preview_end)&U32_MASK
    return delta==lag if captured_samples is not None else delta<=lag


def u32_has_advanced(before:int,after:int,*,received_since_last:int)->bool:
    if (type(before) is not int or type(after) is not int
            or type(received_since_last) is not int
            or not 0<=before<U32_MOD or not 0<=after<U32_MOD
            or not 0<received_since_last<U32_MOD):
        return False
    delta=(after-before)&U32_MASK
    return 0<delta<=received_since_last


def extended_u32_window(first:int,end:int,count:int,
                        captured_samples:int)->tuple[int,int]:
    """Least nonnegative device index epoch consistent with real RX count.

    This is only a local graph axis and NOT original DSP clock time.
    """
    if (not u32_preview_bounds(first,end,count)
            or type(captured_samples) is not int
            or not count<=captured_samples<1<<64):
        raise ValueError("Invalid original uint32 ADC cursor window")
    epoch=max(0,(captured_samples-end+U32_MOD-1)//U32_MOD)
    extended_end=end+epoch*U32_MOD
    extended_first=extended_end-count
    if extended_first<0 or (extended_first&U32_MASK)!=first:
        raise ValueError("Inconsistent original uint32 ADC index epoch")
    return extended_first,extended_end
