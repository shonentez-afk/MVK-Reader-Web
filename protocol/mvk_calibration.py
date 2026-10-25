"""Read-only MVK01 Modbus calibration decoding and physical units.

No network access or device control is performed by this module.
Conversion is confirmed against matching TCP/10230 and BIN for ADC4
on two devices; other channels require independent end-to-end validation.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Sequence


CHANNELS = 8
ADC_CALIBRATION_BASE = 0x0020
CHANNEL_BASE = 0x0100
CHANNEL_STRIDE = 0x0100
SENSOR_SENSITIVITY_OFFSET = 0x02
CONVERSION_GAIN_OFFSET = 0x0E


@dataclass(frozen=True)
class ChannelCalibration:
    channel: int
    sensor_sensitivity_v_per_ms2: float
    conversion_gain: float


def register_addresses(channel: int) -> tuple[int, int]:
    """Return (sensitivity, conversion gain) zero-based FC03 addresses."""
    if not isinstance(channel, int) or isinstance(channel, bool) or not 0 <= channel < CHANNELS:
        raise ValueError("channel must be an integer from 0 to 7")
    base = CHANNEL_BASE + channel * CHANNEL_STRIDE
    return base + SENSOR_SENSITIVITY_OFFSET, base + CONVERSION_GAIN_OFFSET


def decode_cdab_float32(raw: bytes) -> float:
    """Decode device float: high 16-bit word appears second (CDAB)."""
    if len(raw) != 4:
        raise ValueError("expected exactly 4 bytes (two Modbus registers)")
    value = struct.unpack(">f", raw[2:4] + raw[0:2])[0]
    if not math.isfinite(value):
        raise ValueError("non-finite Modbus float")
    return value


def parse_channel(channel: int, sensitivity_registers: bytes, gain_registers: bytes) -> ChannelCalibration:
    register_addresses(channel)
    sensitivity = decode_cdab_float32(sensitivity_registers)
    gain = decode_cdab_float32(gain_registers)
    if sensitivity <= 0 or gain <= 0:
        raise ValueError("calibration values must be positive")
    return ChannelCalibration(channel, sensitivity, gain)


def samples_to_acceleration(raw_samples: Sequence[float], conversion_gain: float) -> list[float]:
    """Raw TCP/10230 float32 values -> acceleration in m/s².

    Input must be RAW TCP data, not already calibrated BIN samples.
    """
    if not math.isfinite(conversion_gain) or conversion_gain <= 0:
        raise ValueError("conversion gain must be positive and finite")
    out = []
    for sample in raw_samples:
        if not math.isfinite(sample):
            raise ValueError("raw sample is not finite")
        out.append(sample * conversion_gain)
    return out
