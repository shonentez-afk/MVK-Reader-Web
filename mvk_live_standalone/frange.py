"""Original per-ADC FRange provenance from the Native Go *config*, not AUX4700.

The device's first accepted FC03 full register image contains one Float32
factor per ADC at register 0x0100 + channel*0x0100 + 0x0E. Native Go
multiplies incoming uncalibrated Float32 by this factor EXACTLY ONCE
when writing the verified BIN spool and live source ring. MVK Live only
displays the factor: NEVER multiply it into the wave, FFT or RMS again.
"""
from __future__ import annotations

import math


def original_applied_frange(status: dict | None, adc: int) -> float | None:
    """Return already-applied original FRange, or None before calibration.

    Any PRESENT but malformed 8-channel set is rejected rather than falling
    back to 1 or relabelling unscaled device samples as physical units.
    """
    if type(adc) is not int or not 1<=adc<=8:
        raise ValueError("FRange ADC index must be 1..8")
    if status is None:
        return None
    if not isinstance(status, dict):
        raise ValueError("FRange expects one verified Native status mapping")
    ranges=status.get("adc_frange_from_config")
    if ranges is None:
        return None
    if (type(status.get("full_register_snapshots")) is not int or
            status["full_register_snapshots"]<=0):
        raise ValueError("FRange reported without a full instrument register image")
    if not isinstance(ranges,list) or len(ranges)!=8:
        raise ValueError("FRange must have exactly 8 verified ADC coefficients")
    for gain in ranges:
        if (type(gain) not in (float,int) or
                not math.isfinite(gain) or not 0<gain<=1e7):
            raise ValueError("Invalid real ADC FRange; never substitute unity")
    return float(ranges[adc-1])
