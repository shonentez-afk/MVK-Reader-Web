"""Stage111Z29C1 private comparator QA with *mocked synthetic* FIR profile.

No user's IDP nor source measurements enter GitHub. Production loader's
SHA256 policy is tested separately in test_envelope_idr_candidate.py;
only this test injects an artificial profile to exercise comparator logic.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pytest

from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.envelope_idr_candidate import (
    EnvelopeProfile,process_original_envelope_candidate)
from mvk_compatible.private_getsignal_envelope_compare import (
    compare_original_getsignal_envelope_return,main)
from .test_envelope_idr_candidate import fake_profile
from .test_offline_core import fixture_zip


@pytest.fixture
def sources(tmp_path,monkeypatch):
    native=fixture_zip(tmp_path)
    dummy_idp=tmp_path/"SYNTHETIC_NOT_ORIGINAL.idp"
    dummy_idp.write_bytes(b"SYNTHETIC ONLY; NEVER ORIGINAL FIRMWARE")
    profile=fake_profile(i=1.,q=.25)

    def fake_loader(cls,p):
        assert Path(p)==dummy_idp
        return profile
    monkeypatch.setattr(
        EnvelopeProfile,"from_original_local_idp",classmethod(fake_loader))

    samples,fs,_,_=OfflineSession.open(native).samples(1)
    expected=process_original_envelope_candidate(
        samples[0:2099],int(fs),20,profile,f_range=1.)
    assert expected["output_samples"]==1024
    reference=tmp_path/"synthetic_return.bin"
    reference.write_bytes(expected["getsignal_buffer"].tobytes())
    return native,dummy_idp,reference,expected


def _check(sources,**overrides):
    z,idp,reference,_=sources
    kw={
        "channel":1,"first_sample":0,"input_samples":2099,
        "envelope_code":20,"f_range":1.,"output_samples":1024
    }
    kw.update(overrides)
    return compare_original_getsignal_envelope_return(z,idp,reference,**kw)


def test_exact_synthetic_envelope_return_matches_but_no_original_claim(sources):
    z,idp,reference,_=sources
    original_z=z.read_bytes()
    result=_check(sources)
    assert result["float32_words_exact"]==1024
    assert result["float32_ulp_max"]==0
    assert result["float32_ulp_median"]==0
    assert result["candidate_matches_operator_captured_reverse_buffer_bitwise"]
    assert result["original_idp_fingerprint_verified"]
    assert not result["original_same_run_device_and_window_authenticated"]
    assert not result["original_f_range_from_original_runtime_verified"]
    assert not result["original_x87_extended_runtime_parity_verified"]
    assert not result["original_envelope_spectrum_four_mode_parity_verified"]
    assert result["private_sources_paths_coefficients_and_values_in_report"] is False
    assert str(z) not in json.dumps(result)
    assert reference.name not in json.dumps(result)
    assert z.read_bytes()==original_z


def test_chronological_buffer_is_not_getsignal_reverse_return(sources):
    _,_,reference,frame=sources
    reference.write_bytes(frame["chronological"].tobytes())
    r=_check(sources)
    assert r["float32_words_exact"]<1024
    assert not r["candidate_matches_operator_captured_reverse_buffer_bitwise"]


def test_wrong_f_range_window_channel_are_detected(sources):
    assert not _check(sources, f_range=2.)[
        "candidate_matches_operator_captured_reverse_buffer_bitwise"]
    assert not _check(sources,first_sample=1)[
        "candidate_matches_operator_captured_reverse_buffer_bitwise"]
    assert not _check(sources,channel=2)[
        "candidate_matches_operator_captured_reverse_buffer_bitwise"]
    with pytest.raises(ValueError,match="OutputLength"):
        _check(sources,envelope_code=1)


def test_one_modified_float32_word_reports_exact_mismatch(sources):
    _,_,ref,_=sources
    data=np.frombuffer(ref.read_bytes(),dtype="<u4").copy()
    data[17]^=np.uint32(1)
    ref.write_bytes(data.tobytes())
    r=_check(sources)
    assert r["float32_words_exact"]==1023
    assert r["first_float32_mismatch_index"]==17
    assert r["float32_ulp_max"]>=1


@pytest.mark.parametrize("kw",[
    dict(channel=True),dict(channel=9),dict(first_sample=-1),
    dict(input_samples=0),dict(envelope_code=0),dict(envelope_code=32),
    dict(envelope_code=True),dict(f_range=float("nan")),
    dict(f_range=0),dict(output_samples=0),dict(output_samples=True),
    dict(output_samples=600000),
])
def test_unknown_or_bad_original_metadata_refused(sources,kw):
    with pytest.raises(ValueError):
        _check(sources,**kw)


def test_missing_original_or_short_history_fails_closed(sources):
    z,idp,reference,_=sources
    with pytest.raises(ValueError,match="Insufficient real"):
        _check(sources,first_sample=4090)
    data=reference.read_bytes()
    reference.write_bytes(data[:-4])
    with pytest.raises(ValueError,match="length"):
        _check(sources)
    reference.write_bytes(b"\0"*len(data))
    with pytest.raises(ValueError,match="all zero"):
        _check(sources)


def test_cli_prints_only_aggregate_report_not_paths(sources):
    z,idp,ref,_=sources
    argv=[
        "--source-native-zip",str(z),
        "--local-original-idp",str(idp),
        "--original-getsignal-bin",str(ref),
        "--channel","1","--first-sample","0",
        "--input-samples","2099","--envelope-code","20",
        "--f-range","1.0","--output-samples","1024",
    ]
    buf=io.StringIO()
    with redirect_stdout(buf):
        assert main(argv)==0
    result=json.loads(buf.getvalue())
    assert result["float32_words_exact"]==1024
    assert str(z) not in buf.getvalue() and str(idp) not in buf.getvalue()
    assert str(ref) not in buf.getvalue()
