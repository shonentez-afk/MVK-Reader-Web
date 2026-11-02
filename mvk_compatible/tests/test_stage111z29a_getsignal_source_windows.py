"""Stage111Z29A: synthetic source gates for original latest/sequential GetSignal.

No original user waveform, private IDP/EXE, or instrument network is used.
"""
from __future__ import annotations

import numpy as np
import pytest

from mvk_compatible.core.getsignal_source_window import (
    plan_getsignal_ring_window, read_getsignal_ring_source,
)
from mvk_compatible.core.getsignal_input_evidence import (
    archive_input_window_evidence,compare_local_input_windows,SCHEMA,
)
from mvk_compatible.core.offline_export import OfflineSession
from .test_offline_core import fixture_zip


def _ring():
    # contains valid absolute indices 2..9 in an 8-sample capacity
    return np.array([8,9,2,3,4,5,6,7],dtype="<f4")


def test_original_getsignal_latest_no_history_zero_prefix_is_explicit():
    samples,plan=read_getsignal_ring_source(
        _ring(),rx_position=10,valid_position=4,output_length=8)
    np.testing.assert_array_equal(samples,[0,0,4,5,6,7,8,9])
    assert plan.ready and plan.request_mode=="LATEST_RX_POSITION"
    assert plan.first_real_index==4 and plan.last_exclusive_index==10
    assert plan.zero_prefix_samples==2 and plan.real_samples==6
    assert plan.original_runtime_parity_verified is False
    assert plan.zero_fill_allowed_only_for_original_live_ring


def test_original_getsignal_sequential_source_uses_start_plus_length_not_rx():
    samples,plan=read_getsignal_ring_source(
        _ring(),rx_position=10,valid_position=2,output_length=4,
        sequential_start=5)
    np.testing.assert_array_equal(samples,[5,6,7,8])
    assert plan.ready and plan.request_mode=="SEQUENTIAL_PARAMS_POSITION"
    assert plan.first_real_index==5 and plan.last_exclusive_index==9
    assert plan.next_sequential_position==9
    assert plan.zero_prefix_samples==0
    latest,_=read_getsignal_ring_source(
        _ring(),rx_position=10,valid_position=2,output_length=4)
    np.testing.assert_array_equal(latest,[6,7,8,9])
    assert not np.array_equal(samples,latest)


def test_original_source_future_sequential_returns_waiting_not_fabricated():
    kwargs=dict(rx_position=10,valid_position=2,ring_capacity=8,
                output_length=4,sequential_start=8)
    plan=plan_getsignal_ring_window(**kwargs)
    assert not plan.ready and plan.next_sequential_position is None
    assert plan.real_samples==0 and plan.zero_prefix_samples==0
    with pytest.raises(ValueError,match="not yet available"):
        read_getsignal_ring_source(
            _ring(),rx_position=10,valid_position=2,
            output_length=4,sequential_start=8)


def test_original_overrun_AND_unchecked_stale_history_both_rejected():
    with pytest.raises(ValueError,match="overflow"):
        plan_getsignal_ring_window(
            rx_position=10,valid_position=2,ring_capacity=8,
            output_length=4,sequential_start=1)
    # Source CheckDataAvailability may not catch this shorter lag,
    # but copying expired ring bytes would claim a false old measurement.
    with pytest.raises(ValueError,match="overwritten"):
        plan_getsignal_ring_window(
            rx_position=10,valid_position=4,ring_capacity=8,
            output_length=4,sequential_start=3)


def test_original_source_64bit_wrapping_does_not_overflow_numpy_index():
    base=(1<<63)+10
    ring=np.arange(8,dtype="<f4")
    samples,plan=read_getsignal_ring_source(
        ring,rx_position=base,valid_position=base-6,output_length=8)
    np.testing.assert_array_equal(samples,[0,0,4,5,6,7,0,1])
    assert plan.first_real_index==base-6 and plan.last_exclusive_index==base


def test_original_source_latest_with_no_received_samples_not_attested_data():
    samples,plan=read_getsignal_ring_source(
        np.zeros(8,dtype="<f4"),rx_position=0,valid_position=0,
        output_length=4)
    assert not np.any(samples)
    assert plan.real_samples==0 and plan.zero_prefix_samples==4


@pytest.mark.parametrize("opts",[
    dict(rx_position=10,valid_position=1,ring_capacity=8,output_length=4),
    dict(rx_position=8,valid_position=9,ring_capacity=8,output_length=4),
    dict(rx_position=8,valid_position=0,ring_capacity=7,output_length=4),
    dict(rx_position=8,valid_position=0,ring_capacity=8,output_length=9),
    dict(rx_position=8,valid_position=0,ring_capacity=8,output_length=0),
    dict(rx_position=True,valid_position=0,ring_capacity=8,output_length=4),
    dict(rx_position=8.0,valid_position=0,ring_capacity=8,output_length=4),
    dict(rx_position=8,valid_position=0,ring_capacity=8,output_length=4,sequential_start=-1),
])
def test_source_invalid_ring_request_is_fail_closed(opts):
    with pytest.raises(ValueError,match="GetSignal original ring"):
        plan_getsignal_ring_window(**opts)


def test_real_archive_shared_input_fingerprint_pre_dc_getsignal_vs_fft(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    wave=session.waveform(1,0,.0625,'ac',points=8000)
    spec=session.spectrum(1,4096,0,start_s=0,max_hz=32768,max_points=2048)
    a=wave["input_source_window"]
    b=spec["input_source_window"]
    assert a["schema"]==b["schema"]==SCHEMA
    assert a["first_archive_sample_index"]==0
    assert a["last_archive_sample_exclusive"]==4096
    assert a["source_sample_count"]==4096
    assert a["no_zero_padding"] and a["source_is_native_r6_sha_audited_export"]
    assert b["no_zero_padding"] and not b["original_same_run_bin_verified"]
    eq=compare_local_input_windows(a,b)
    assert eq["same_input_bytes_and_bounds"]
    assert not eq["getsignal_processing_equals_getspectrum_processing"]
    assert not eq["original_delphi_runtime_parity_verified"]
    assert wave["requested_window_truncated_by_archive_end"] is False
    assert spec["end_s"]==4096/65536


def test_different_fft_window_or_channel_cannot_pass_same_source_contract(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    wave=session.waveform(1,0,.0625,'acdc',points=8000)
    smaller=session.spectrum(1,1024,1,start_s=0,max_hz=32768,max_points=512)
    other=session.spectrum(2,4096,1,start_s=0,max_hz=32768,max_points=2048)
    assert not compare_local_input_windows(
        wave["input_source_window"],smaller["input_source_window"]
    )["same_input_bytes_and_bounds"]
    assert not compare_local_input_windows(
        wave["input_source_window"],other["input_source_window"]
    )["same_input_bytes_and_bounds"]


def test_archive_no_zero_padding_even_if_original_live_ring_allows_it(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    with pytest.raises(ValueError,match="данных"):
        session.spectrum(1,8192,0,start_s=0)
    with pytest.raises(ValueError,match="real BIN history"):
        archive_input_window_evidence(
            np.ones(3,dtype="<f4"),first=0,end=4,
            sample_rate_hz=65536,native_audit=False,channel=1)
    with pytest.raises(ValueError,match="incompatible"):
        compare_local_input_windows(
            {"schema":SCHEMA},{"schema":SCHEMA})


def test_archive_input_provenance_rejects_bools_nans_and_bad_bounds():
    data=np.ones(10,dtype="<f4")
    for x,y,fs,audit in [
        (True,4,1000.,True),(0,True,1000.,True),
        (-1,4,1000.,True),(4,4,1000.,True),
        (0,11,1000.,True),(0,4,float("nan"),True),
        (0,4,1000.,1),
    ]:
        with pytest.raises(ValueError):
            archive_input_window_evidence(
                data,first=x,end=y,sample_rate_hz=fs,native_audit=audit,
                channel=1,source_raw_sha256='0'*64)


def test_identical_float32_array_on_other_adc_or_capture_is_not_same_window():
    samples=np.arange(64,dtype="<f4")
    base=dict(first=0,end=32,sample_rate_hz=65536,native_audit=True)
    a=archive_input_window_evidence(
        samples,channel=1,source_raw_sha256="a"*64,**base)
    other_adc=archive_input_window_evidence(
        samples,channel=2,source_raw_sha256="a"*64,**base)
    other_run=archive_input_window_evidence(
        samples,channel=1,source_raw_sha256="b"*64,**base)
    assert a["source_float32_le_sha256"]==other_adc["source_float32_le_sha256"]
    assert not compare_local_input_windows(a,other_adc)["same_input_bytes_and_bounds"]
    assert not compare_local_input_windows(a,other_run)["same_input_bytes_and_bounds"]
