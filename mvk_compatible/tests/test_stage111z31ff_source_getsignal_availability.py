"""Stage111Z31FF: original GetSignal source cursor and PageAdc live menu tests.

The tests require no device, raw vendor data or outbound TCP.
"""
from __future__ import annotations

import pytest

from ..core.original_getsignal_live_source import (
    SOURCE_BUFFER_SAMPLES,source_getsignal_readiness,
    source_live_adc_menu_length,
)


def _source(**kw):
    args=dict(rx_pos=65536,valid_pos=0,last_processed_pos=0,
              signal_length=65536,contiguous=False,allow_overlap=True,
              preview_samples=65536)
    args.update(kw)
    return source_getsignal_readiness(**args)


def test_getsignal_source_buffer_size_and_initial_overlap_special_branch():
    assert SOURCE_BUFFER_SAMPLES==0x200000
    out=_source(rx_pos=1024,signal_length=65536,preview_samples=1024)
    # Original 007D19A1..007D19AF: if AllowOverlap && !Contiguous,
    # CheckDataAvailability returns true irrespective of fresh N.
    assert out.original_check_data_availability
    # But 007D2228 may zero-fill unavailable history in the original;
    # the live preview must never invent those samples.
    assert not out.verified_preview_window_ready
    assert out.selected_window_start_pos_64 is None
    assert out.receipt()["original_dsp_runtime_parity_verified"] is False


def test_getsignal_source_no_overlap_waits_for_full_new_window():
    wait=_source(rx_pos=96000,last_processed_pos=65536,
                 signal_length=32768,allow_overlap=False,
                 preview_samples=65536)
    assert not wait.original_check_data_availability
    assert not wait.verified_preview_window_ready
    assert wait.next_processed_pos_64 is None
    ready=_source(rx_pos=98304,last_processed_pos=65536,
                  signal_length=32768,allow_overlap=False,
                  preview_samples=65536)
    assert ready.original_check_data_availability
    assert ready.verified_preview_window_ready
    assert ready.selected_window_start_pos_64==65536
    assert ready.selected_window_end_pos_64==98304
    assert ready.next_processed_pos_64==98304


def test_getsignal_contiguous_source_overflow_and_source_cursor_64bit():
    original=_source(rx_pos=40000,last_processed_pos=30000,
                     signal_length=4096,contiguous=True,
                     allow_overlap=False,preview_samples=16000)
    assert original.original_check_data_availability
    assert original.selected_window_start_pos_64==30000
    assert original.selected_window_end_pos_64==34096
    assert original.next_processed_pos_64==34096
    with pytest.raises(OverflowError,match="Buffer overflow"):
        _source(rx_pos=SOURCE_BUFFER_SAMPLES+8192,
                last_processed_pos=0,
                signal_length=4096,contiguous=True,
                allow_overlap=False,preview_samples=65536)
    # Full 64-bit source cursor is not a 32-bit device Sample.Index.
    large=(1<<32)+65536
    read=_source(rx_pos=large,
                 last_processed_pos=large-65536,
                 signal_length=65536,allow_overlap=False,
                 preview_samples=65536)
    assert read.verified_preview_window_ready
    assert read.source_rxpos_64==large


def test_getsignal_validpos_and_real_preview_limit_both_protect_history():
    model=_source(rx_pos=200000,valid_pos=150000,
                  signal_length=65536,preview_samples=65536)
    assert model.original_check_data_availability
    assert not model.verified_preview_window_ready
    model=_source(rx_pos=200000,valid_pos=0,
                  signal_length=65536,preview_samples=32768)
    assert model.original_check_data_availability
    assert not model.verified_preview_window_ready
    model=_source(rx_pos=200000,valid_pos=0,
                  signal_length=65536,preview_samples=65536)
    assert model.verified_preview_window_ready


@pytest.mark.parametrize("kwargs",(
    {"rx_pos":True},{"rx_pos":-1},{"rx_pos":1<<64},
    {"valid_pos":65537},{"last_processed_pos":65537},
    {"signal_length":0},{"signal_length":1<<32},
    {"preview_samples":SOURCE_BUFFER_SAMPLES+1},
    {"buffer_samples":123456},{"contiguous":1},{"allow_overlap":"true"},
))
def test_getsignal_invalid_original_cursor_is_rejected(kwargs):
    with pytest.raises(ValueError):
        _source(**kwargs)


def test_getsignal_exact_14_source_horizontal_menu_integer_sample_count():
    expected=(20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1)
    assert tuple(source_live_adc_menu_length(i,65536)[1]
                 for i in range(14))==expected
    assert source_live_adc_menu_length(4,65536)==(65536,1000)
    assert source_live_adc_menu_length(5,65536)==(32768,500)
    assert source_live_adc_menu_length(13,65536)==(65,1)
    assert source_live_adc_menu_length(0,65536)==(1310720,20000)
    with pytest.raises(ValueError):
        source_live_adc_menu_length(13,512)  # integer truncation -> 0
    with pytest.raises(ValueError):
        source_live_adc_menu_length(True,65536)
