"""Stage111Z29C2: synthetic-only private original pre-FFT comparator.

Never use user-provided source IDP, BIN, x32dbg snapshots or passwords in CI.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import numpy as np
import pytest

from mvk_compatible.core.envelope_idr_candidate import (
    EnvelopeProfile,process_original_envelope_candidate)
from mvk_compatible.core.storage_f_range_idr_candidate import (
    prepare_original_fft_input,DOMAIN_CALIBRATED_BIN,DOMAIN_ORIGINAL_STORAGE)
from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.private_getspectrum_prefft_envelope_compare import (
    compare_original_prefft_envelope,main)
from .test_envelope_idr_candidate import fake_profile
from .test_offline_core import fixture_zip


@pytest.fixture
def private_synthetic_pair(tmp_path,monkeypatch):
    native=fixture_zip(tmp_path)
    idp=tmp_path/"synthetic_stub.idp"
    idp.write_bytes(b"SYNTHETIC FILTERS ONLY")
    profile=fake_profile(i=1.,q=.4)
    def fake_loader(cls,path):
        assert str(path)==str(idp)
        return profile
    monkeypatch.setattr(
        EnvelopeProfile,"from_original_local_idp",classmethod(fake_loader))
    samples,fs,_,_=OfflineSession.open(native).samples(1)
    first=len(samples)-2099
    original_ring=samples[first:].copy()
    norm=prepare_original_fft_input(
        original_ring,f_range=4.,input_domain=DOMAIN_ORIGINAL_STORAGE)
    expected=process_original_envelope_candidate(
        norm["samples_before_dc_removal"],int(fs),
        20,profile,f_range=1.)["chronological"]
    assert len(expected)==1024 and np.count_nonzero(expected)>0
    capture=tmp_path/"synthetic_before_fft.bin"
    capture.write_bytes(expected.tobytes())
    return native,idp,capture,first


def _compare(fx,**override):
    native,idp,capture,first=fx
    opts=dict(channel=1,first_sample=first,n_fft=1024,
              envelope_code=20,f_range=4.,
              input_domain=DOMAIN_ORIGINAL_STORAGE)
    opts.update(override)
    return compare_original_prefft_envelope(native,idp,capture,**opts)


def test_synthetic_same_window_original_storage_prefft_exact_and_private(private_synthetic_pair):
    native,idp,capture,_=private_synthetic_pair
    original_native=native.read_bytes()
    result=_compare(private_synthetic_pair)
    assert result["float32_total_words"]==1024
    assert result["float32_exact_words"]==1024
    assert result["original_pre_fft_full_array_bitwise_equal"]
    assert result["float32_max_ulp"]==0
    assert result["original_source_buffer_provenance_verified"] is False
    assert result["original_same_run_device_and_window_authenticated"] is False
    assert result["original_runtime_f_range_and_storage_domain_verified"] is False
    assert result["original_historical_before_fft_envelope_code_verified"] is False
    assert result["original_four_spectrum_modes_numeric_parity_verified"] is False
    assert result["private_original_paths_coefficients_samples_in_report"] is False
    assert str(native) not in json.dumps(result)
    assert str(idp) not in json.dumps(result)
    assert capture.name not in json.dumps(result)
    assert native.read_bytes()==original_native


@pytest.mark.parametrize("changes",[
    {"input_domain":DOMAIN_CALIBRATED_BIN},
    {"first_sample":100},
    {"f_range":2.5},
    {"channel":2},
])
def test_different_input_domain_start_scale_or_channel_does_not_false_pass(
    private_synthetic_pair,changes
):
    result=_compare(private_synthetic_pair,**changes)
    assert not result["original_pre_fft_full_array_bitwise_equal"]
    assert result["float32_exact_words"]<1024


def test_one_reference_ulp_reports_mismatch_index(private_synthetic_pair):
    _,_,capture,_=private_synthetic_pair
    words=np.frombuffer(capture.read_bytes(),dtype="<u4").copy()
    words[79]^=np.uint32(1)
    capture.write_bytes(words.tobytes())
    result=_compare(private_synthetic_pair)
    assert result["float32_first_mismatch_index"]==79
    assert result["float32_exact_words"]==1023
    assert result["float32_max_ulp"]>=1


@pytest.mark.parametrize("changes",[
    {"envelope_code":0},{"envelope_code":32},{"envelope_code":True},
    {"channel":True},{"channel":0},{"n_fft":0},{"n_fft":1000},
    {"f_range":0.0},{"f_range":float("nan")},
    {"input_domain":"auto_guess"},
    {"first_sample":-1},{"first_sample":True},
])
def test_invalid_original_runtime_metadata_refused(private_synthetic_pair,changes):
    with pytest.raises(ValueError):
        _compare(private_synthetic_pair,**changes)


def test_fake_zero_nan_short_prefft_never_certified(private_synthetic_pair):
    _,_,capture,_=private_synthetic_pair
    original=capture.read_bytes()
    capture.write_bytes(bytes(len(original)))
    with pytest.raises(ValueError,match="Zero-only"):
        _compare(private_synthetic_pair)
    words=np.frombuffer(original,dtype="<f4").copy()
    words[20]=np.nan
    capture.write_bytes(words.tobytes())
    with pytest.raises(ValueError,match="nonfinite"):
        _compare(private_synthetic_pair)
    capture.write_bytes(original[:-4])
    with pytest.raises(ValueError,match="length"):
        _compare(private_synthetic_pair)
    capture.write_bytes(original)
    with pytest.raises(ValueError,match="insufficient real"):
        _compare(private_synthetic_pair,first_sample=4090)


def test_cli_aggregate_only_safe_no_original_paths(private_synthetic_pair):
    native,idp,capture,first=private_synthetic_pair
    args=["--source-native-zip",str(native),
        "--local-original-idp",str(idp),
        "--original-before-fft-bin",str(capture),
        "--channel","1","--first-sample",str(first),
        "--n-fft","1024","--envelope-code","20",
        "--f-range","4","--input-domain",DOMAIN_ORIGINAL_STORAGE]
    output=io.StringIO()
    with redirect_stdout(output):
        assert main(args)==0
    report=json.loads(output.getvalue())
    assert report["float32_exact_words"]==1024
    assert str(native) not in output.getvalue()
    assert str(idp) not in output.getvalue()
    assert str(capture) not in output.getvalue()
