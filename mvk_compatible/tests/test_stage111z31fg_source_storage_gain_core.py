"""Three-source source gain fallback tests; synthetic only, no instrument IO."""
from __future__ import annotations

import json
import math

import pytest

from ..core.original_mode2_gain_fallback import (
    ADC_CHANNEL_COUNT, CHANNEL_COUNT, GAIN_CELL_ADDR, UNITS_CELL_ADDR,
    UNITY_GAIN, UNITY_GAIN_FLOAT32_BITS, OriginalGainFallbackError,
    source_gain_fallback, source_gain_zero_guard, source_units_for_channel,
    resolve_channel_gain_units, resolve_all_channels,
)


def test_constants_are_source_immediates():
    assert (ADC_CHANNEL_COUNT, CHANNEL_COUNT) == (8, 10)
    assert (GAIN_CELL_ADDR, UNITS_CELL_ADDR) == (0x0E, 0x10)
    assert (UNITY_GAIN, UNITY_GAIN_FLOAT32_BITS) == (1.0, 0x3F800000)


@pytest.mark.parametrize("ch", (8, 9))
def test_tach_source_storage_gain_and_units_are_static(ch):
    obj = resolve_channel_gain_units(ch)
    assert (obj.gain, obj.units, obj.is_adc) == (1.0, "", False)
    assert obj.gain_source.startswith("00806988")
    assert obj.units_source.startswith("008069E1")
    receipt = obj.receipt()
    assert not receipt["original_runtime_gain_verified"]
    assert not receipt["original_tach_rpm_verified"]
    assert not receipt["native_tach_samples_rescaled"]


@pytest.mark.parametrize("ch", (0, 1, 7))
def test_no_adc_cell_means_unknown_not_automatic_unity(ch):
    assert source_gain_fallback(ch)[0] is None
    assert source_units_for_channel(ch)[0] is None
    item = resolve_channel_gain_units(ch)
    assert item.gain is None and item.units is None
    assert "NOT_OBSERVED" in item.gain_source
    assert "NOT_OBSERVED" in item.units_source


@pytest.mark.parametrize("gain,expected", ((0.0, 1.0), (-0.0, 1.0),
                                           (1.0, 1.0), (2.5, 2.5),
                                           (1e-6, 1e-6), (-3.0, -3.0)))
def test_observed_adc_gain_only_zero_becomes_unity(gain, expected):
    assert source_gain_zero_guard(gain) == expected
    result, origin = source_gain_fallback(2, gain)
    assert result == expected
    assert origin.startswith("0080697D")


def test_nan_is_not_silently_repaired():
    assert math.isnan(source_gain_zero_guard(float("nan")))
    assert math.isnan(resolve_channel_gain_units(2, adc_gain=float("nan")).gain)


@pytest.mark.parametrize("bad", (-1, 10, 999, True, False, 1.1, "8", None))
def test_invalid_channel_indices_fail_closed(bad):
    with pytest.raises(OriginalGainFallbackError):
        resolve_channel_gain_units(bad)


@pytest.mark.parametrize("bad", (True, False, "1", None, (), {}, []))
def test_zero_guard_non_numeric_disallowed(bad):
    with pytest.raises(OriginalGainFallbackError):
        source_gain_zero_guard(bad)


def test_adc_units_reject_invalid_but_tach_ignores_unused_adc_text():
    with pytest.raises(OriginalGainFallbackError):
        source_units_for_channel(2, 123)
    assert source_units_for_channel(9, 123)[0] == ""
    assert source_units_for_channel(3, "м/с²")[0] == "м/с²"


def test_ten_records_keep_adc_unobserved_and_tach_source_default():
    rows = resolve_all_channels()
    assert len(rows) == 10
    assert [row.channel for row in rows] == list(range(10))
    assert [row.gain for row in rows[:8]] == [None] * 8
    assert [row.gain for row in rows[8:]] == [1.0] * 2
    assert [row.units for row in rows[8:]] == [""] * 2
    assert "00806988" in json.dumps([row.receipt() for row in rows])


def test_only_explicit_adc_observations_produce_non_null_gain():
    records = resolve_all_channels("м/с²", {0: 2.5, 7: 0.0})
    assert (records[0].gain, records[0].units) == (2.5, "м/с²")
    assert records[1].gain is None
    assert records[7].gain == 1.0
    assert records[9].units == ""


@pytest.mark.parametrize("bad", ({8: 2.0}, {True: 1.0}, {-1: 1.0}, [1.0]))
def test_unverified_adc_mapping_fails_closed(bad):
    with pytest.raises(OriginalGainFallbackError):
        resolve_all_channels(adc_gains=bad)


def test_native_tach_receipt_has_storage_fallback_but_no_fake_rpm():
    from ..core.native_r6_tach_evidence import NativeTachChannel
    row = NativeTachChannel(9, True, 'TACH1_NATIVE_UNCALIBRATED.f32',
                            2, 128, 512, 0, 64, 32768, 0, 0, None, True)
    record = row.receipt()
    source = record['original_source_storage_gain_units']
    assert (source['channel'], source['gain'], source['units']) == (8, 1.0, '')
    assert source['original_runtime_gain_verified'] is False
    assert source['original_tach_rpm_verified'] is False
    assert source['native_tach_samples_rescaled'] is False
    assert not record['physical_rpm_verified']


def test_both_native_tach_receipts_keep_distinct_original_channel_indices():
    from ..core.native_r6_tach_evidence import NativeTachChannel
    for native, original in ((9, 8), (10, 9)):
        r = NativeTachChannel(native, False, None, 0, 0, 0, 0, 0,
                              0, 0, 0, None, False).receipt()
        proof = r['original_source_storage_gain_units']
        assert proof['channel'] == original
        assert proof['gain'] == 1.0 and proof['units'] == ''
        assert r['present'] is False