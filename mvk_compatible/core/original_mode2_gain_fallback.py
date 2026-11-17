"""Read-only TMVKThread channel-storage gain/units facts from original MVKView.

Three independent original files: mvkview.idp (header), Projects.7z
(_Unit125.pas) and mvk_idr(1).sqlite (source/function index).

00806964: channels 8/9 bypass the ADC cell list and load float32 1.0.
           ADC 0..7 read GetFloatByAddr(0x0E), then change ONLY 0 to 1.
008069AC: channels 8/9 clear the output string; ADC 0..7 get the
           text using GetIndexByAddr(0x10) followed by GetValueText.

This models TMvkChannelStorage metadata, NOT original PageStatus TACH
ResultTacho field units ('Hz'), hardware RPM or live calibration. It neither
invents missing ADC gain nor modifies captured ADC/TACH samples. NO device I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE = "STAGE111Z31FG_TMVKTHREAD_SOURCE_STORAGE_GAIN_00806964_008069AC"
ADC_CHANNEL_COUNT = 8
TACH_CHANNEL_COUNT = 2
CHANNEL_COUNT = ADC_CHANNEL_COUNT + TACH_CHANNEL_COUNT
GAIN_CELL_ADDR = 0x0E
UNITS_CELL_ADDR = 0x10
UNITY_GAIN = 1.0
UNITY_GAIN_FLOAT32_BITS = 0x3F800000


class OriginalGainFallbackError(ValueError):
    """Input cannot be interpreted as original MVKView storage metadata."""


def _channel(channel: int) -> int:
    if type(channel) is not int or not 0 <= channel < CHANNEL_COUNT:
        raise OriginalGainFallbackError("Original source channel must be 0..9")
    return channel


def source_gain_zero_guard(gain: float) -> float:
    """Apply x87 FUCOMPP / JP / JNZ: only numeric zero becomes unity.

    Caller must provide the actual loaded float32 source value, not a guessed
    substitute for a missing instrument register or cell list.
    """
    if type(gain) not in (int, float):
        raise OriginalGainFallbackError("Original gain must be numeric")
    result = float(gain)
    return UNITY_GAIN if result == 0.0 else result


def source_gain_fallback(channel: int, adc_gain: float | None = None) -> tuple[float | None, str]:
    """Channel 8/9 have proven 1.0; ADC 0..7 require an observed cell value."""
    _channel(channel)
    if channel >= ADC_CHANNEL_COUNT:
        return UNITY_GAIN, "00806988_CHANNEL_GE_8_UNITY"
    if adc_gain is None:
        # Original 00806971/7D reads a *real* TMvkCellList. Its value is NOT
        # necessarily zero simply because the compatible side cannot see it.
        return None, "0080697D_ADC_CELL_0x0E_NOT_OBSERVED"
    return (source_gain_zero_guard(adc_gain),
            "0080697D_ADC_CELL_0x0E_THEN_0080699E_ZERO_GUARD")


def source_units_for_channel(
        channel: int, adc_units: str | None = None) -> tuple[str | None, str]:
    """TACH storage units are empty; missing ADC cell text stays unknown."""
    _channel(channel)
    if channel >= ADC_CHANNEL_COUNT:
        return "", "008069E1_CHANNEL_GE_8_EMPTY"
    if adc_units is None:
        return None, "008069D8_ADC_CELL_0x10_TEXT_NOT_OBSERVED"
    if type(adc_units) is not str:
        raise OriginalGainFallbackError("ADC source units must be a string")
    return adc_units, "008069D8_ADC_CELL_0x10_GETINDEXBYADDR_TEXT"


@dataclass(frozen=True)
class SourceGainUnits:
    channel: int
    gain: float | None
    units: str | None
    gain_source: str
    units_source: str
    is_adc: bool

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "channel": self.channel,
            "is_adc": self.is_adc,
            "gain": self.gain,
            "units": self.units,
            "gain_source": self.gain_source,
            "units_source": self.units_source,
            "original_runtime_gain_verified": False,
            "original_runtime_units_verified": False,
            "original_tach_rpm_verified": False,
            "original_pagestatus_result_units_overridden": False,
            "native_tach_samples_rescaled": False,
        }


def resolve_channel_gain_units(
        channel: int, adc_units: str | None = None,
        adc_gain: float | None = None) -> SourceGainUnits:
    """One channel's source-storage metadata; no inferred ADC calibration."""
    _channel(channel)
    gain, gain_source = source_gain_fallback(channel, adc_gain)
    units, units_source = source_units_for_channel(channel, adc_units)
    return SourceGainUnits(channel, gain, units, gain_source, units_source,
                           channel < ADC_CHANNEL_COUNT)


def resolve_all_channels(
        adc_units_text: str | None = None,
        adc_gains: dict[int, float] | None = None) -> tuple[SourceGainUnits, ...]:
    """Return 8 ADC unknown/observed records followed by 2 source TACH facts."""
    if adc_gains is not None and (type(adc_gains) is not dict or
                                  any(type(i) is not int or i not in range(8)
                                      for i in adc_gains)):
        raise OriginalGainFallbackError("ADC gains must map channel indices 0..7")
    return tuple(resolve_channel_gain_units(
        i, adc_units_text, adc_gains.get(i) if adc_gains is not None else None)
        for i in range(CHANNEL_COUNT))