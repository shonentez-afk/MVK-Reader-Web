"""Stage111Z29A: source-verified unfiltered original GetSignal ring window.

Private original IDR _Unit115.pas:
  007D1A80 Initialize Params: length=0, Envelope=0, NoDC=true,
    sequential flag (+0x14)=false, availability flag (+0x15)=true,
    initial position [+0x20..+0x24]=FRxPos.
  007D1998 CheckDataAvailability:
    normal latest (+0x14=0, +0x15=1) accepts the requested window;
    sequential (+0x14=1) checks that RxPos-start>=requested samples,
    and rejects overrun where RxPos-start>BufferSize.
  007D0C5E..0086: sequential end=start+length; normal end=FRxPos.
  007D2228: circular read by FBufferMask; prefix zero fill if there are
    fewer than 'length' live samples in the valid [FValidPos,FRxPos) span.

This pure model intentionally *tightens* one corner of the original IDR:
a sequential start before FValidPos is REJECTED even when old Delphi
CheckDataAvailability might not catch the stale memory. It is not claimed
as bitwise original runtime parity; no archive zero padding is allowed.

No sockets, application packets, BIN changes, Delphi binaries, or UI.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class GetSignalRingWindow:
    source: str
    request_mode: str
    ready: bool
    first_real_index: int | None
    last_exclusive_index: int | None
    next_sequential_position: int | None
    zero_prefix_samples: int
    real_samples: int
    requested_samples: int
    rx_position: int
    valid_position: int
    original_runtime_parity_verified: bool = False
    zero_fill_allowed_only_for_original_live_ring: bool = True


def _positive_int(x, label, *, zero=False):
    if type(x) is not int or x < (0 if zero else 1) or x > 2**64-1:
        raise ValueError("GetSignal original ring: invalid " + label)


def plan_getsignal_ring_window(*, rx_position: int, valid_position: int,
                               ring_capacity: int, output_length: int,
                               sequential_start: int | None = None
                               ) -> GetSignalRingWindow:
    """Resolve original +0x14 latest-vs-sequential modes without reading data.

    A waiting sequential request returns ready=False; incomplete or
    overwritten data NEVER become current measurements. Original latest
    behavior with an incomplete ring is marked as zero-prefix candidate.
    """
    _positive_int(rx_position,"FRxPos",zero=True)
    _positive_int(valid_position,"FValidPos",zero=True)
    _positive_int(ring_capacity,"FBufferSize")
    _positive_int(output_length,"GetSignal OutputLength")
    if (ring_capacity & (ring_capacity-1) or
            rx_position < valid_position or
            rx_position-valid_position > ring_capacity or
            output_length > ring_capacity):
        raise ValueError("GetSignal original ring: impossible positions/capacity")
    if sequential_start is None:
        available=min(output_length,rx_position-valid_position)
        return GetSignalRingWindow(
            source="PRIVATE_IDR_UNIT115_007D1998_007D0C5E_007D2228",
            request_mode="LATEST_RX_POSITION",
            ready=True,
            first_real_index=rx_position-available if available else None,
            last_exclusive_index=rx_position,
            next_sequential_position=None,
            zero_prefix_samples=output_length-available,
            real_samples=available,
            requested_samples=output_length,
            rx_position=rx_position,
            valid_position=valid_position,
        )
    _positive_int(sequential_start,"Params+0x20 sequential position",zero=True)
    if sequential_start>rx_position:
        raise ValueError("GetSignal original ring: start in future")
    lag=rx_position-sequential_start
    # Source CheckDataAvailability at 007D19DA..1A00 raises a buffer
    # overrun rather than resuming from the newest samples.
    if lag>ring_capacity:
        raise ValueError("GetSignal original ring: buffer overflow due to insufficient processing speed")
    if sequential_start<valid_position:
        raise ValueError("GetSignal original ring: sequential history overwritten; refuse stale buffer")
    if output_length > lag:
        return GetSignalRingWindow(
            source="PRIVATE_IDR_UNIT115_007D1998_007D0C5E_007D2228",
            request_mode="SEQUENTIAL_PARAMS_POSITION",
            ready=False,first_real_index=None,last_exclusive_index=None,
            next_sequential_position=None,zero_prefix_samples=0,real_samples=0,
            requested_samples=output_length,rx_position=rx_position,
            valid_position=valid_position,
        )
    end=sequential_start+output_length
    return GetSignalRingWindow(
        source="PRIVATE_IDR_UNIT115_007D1998_007D0C5E_007D2228",
        request_mode="SEQUENTIAL_PARAMS_POSITION",
        ready=True,first_real_index=sequential_start,
        last_exclusive_index=end,next_sequential_position=end,
        zero_prefix_samples=0,real_samples=output_length,
        requested_samples=output_length,rx_position=rx_position,
        valid_position=valid_position,
    )


def read_getsignal_ring_source(ring: np.ndarray, *, rx_position: int,
                               valid_position: int, output_length: int,
                               sequential_start: int | None = None
                               ) -> tuple[np.ndarray, GetSignalRingWindow]:
    """Read raw chronological Float32, prior to optional DC and reverse.

    In the original *live* ring the latest path may be prefixed with zeros;
    caller MUST show zero_prefix_samples. For offline BIN use exact BIN
    windows and refuse missing data instead of invoking this ring adapter.
    """
    data=np.asarray(ring,dtype=np.float32)
    if (data.ndim != 1 or not len(data) or len(data)&(len(data)-1) or
            not bool(np.isfinite(data).all())):
        raise ValueError("GetSignal original ring: nonfinite or non-power-of-two ring")
    plan=plan_getsignal_ring_window(
        rx_position=rx_position,valid_position=valid_position,
        ring_capacity=len(data),output_length=output_length,
        sequential_start=sequential_start)
    if not plan.ready:
        raise ValueError("GetSignal original ring: sequential data not yet available")
    result=np.zeros(output_length,dtype=np.float32)
    if plan.real_samples:
        positions=np.arange(
            plan.first_real_index,plan.last_exclusive_index,dtype=np.int64)
        result[plan.zero_prefix_samples:]=data[positions & (len(data)-1)]
    return result,plan
