"""Stage111Z29C2: Stage111J float-ring /FRange BEFORE envelope FIR.

SYNTHETIC only: proves local processing contract and no double scaling.
Original runtime and same-run ring identity remain UNVERIFIED.
"""
from __future__ import annotations
import hashlib

import numpy as np
import pytest

from mvk_compatible.core.envelope_spectrum_idr_candidate import (
    envelope_spectrum_idr_candidate,required_original_history)
from mvk_compatible.core.storage_f_range_idr_candidate import (
    prepare_original_fft_input,DOMAIN_CALIBRATED_BIN,DOMAIN_ORIGINAL_STORAGE)
from mvk_compatible.core.offline_export import OfflineSession
from .test_envelope_idr_candidate import fake_profile
from .test_envelope_spectrum_idr_candidate import source_signal
from .test_offline_core import fixture_zip


def _sha_f32(a):
    return hashlib.sha256(np.asarray(a,dtype="<f4").tobytes()).hexdigest()


@pytest.mark.parametrize("mode",range(4))
def test_stage111j_source_read_before_iq_fir_for_all_spectrum_modes(mode):
    raw=source_signal(code=20,n_fft=1024)
    f_range=4.0
    # Synthetic PAdcFloatData is already the multiplication target; the
    # source original STORAGE hypothesis divides it once before FIR.
    original_storage=np.asarray(raw.astype(np.float64)*f_range,dtype="<f4")
    snapshot=original_storage.tobytes()
    expected=prepare_original_fft_input(
        original_storage,f_range=f_range,input_domain=DOMAIN_ORIGINAL_STORAGE
    )["samples_before_dc_removal"]
    profile=fake_profile(i=1.,q=.4)
    observed=envelope_spectrum_idr_candidate(
        original_storage,65536,20,profile,n_fft=1024,mode=mode,
        backend="numpy",f_range=f_range,input_domain=DOMAIN_ORIGINAL_STORAGE)
    reference=envelope_spectrum_idr_candidate(
        expected,65536,20,profile,n_fft=1024,mode=mode,
        backend="numpy",f_range=f_range,input_domain=DOMAIN_CALIBRATED_BIN)
    calibrated=envelope_spectrum_idr_candidate(
        original_storage,65536,20,profile,n_fft=1024,mode=mode,
        backend="numpy",f_range=f_range) # default NEVER normalizes BIN
    assert observed["input_domain"]==DOMAIN_ORIGINAL_STORAGE
    assert observed["channel_source"]=="RESEARCH_ASSUMED_ORIGINAL_FLOAT_STORAGE"
    assert observed["original_storage_read_divided_by_range"] is True
    assert observed["original_source_buffer_provenance_verified"] is False
    assert observed["calibrated_native_bin_is_original_storage_verified"] is False
    assert observed["pre_fir_read_is_original_runtime_verified"] is False
    assert observed["original_delphi_numerical_parity_verified"] is False
    assert "unverified" in observed["warning"]
    assert observed["pre_fir_read_float32_sha256"]==_sha_f32(expected)
    assert observed["pre_fir_read_sample_count"]==len(raw)==2099
    assert observed["pre_fft_envelope_float32_sha256"]==reference[
        "pre_fft_envelope_float32_sha256"]
    assert observed["spectrum_summary"]==reference["spectrum_summary"]
    np.testing.assert_array_equal(observed["amplitude"],reference["amplitude"])
    assert calibrated["input_domain"]==DOMAIN_CALIBRATED_BIN
    assert calibrated["original_storage_read_divided_by_range"] is False
    assert calibrated["pre_fir_read_float32_sha256"]==_sha_f32(original_storage)
    assert calibrated["pre_fir_read_float32_sha256"]!=observed[
        "pre_fir_read_float32_sha256"]
    assert original_storage.tobytes()==snapshot
    assert calibrated["power_integration_passes"]==max(0,mode-1)


@pytest.mark.parametrize("f_range",[1.0,2.5,510.5650329589844])
def test_envelope_read_uses_explicit_single_frange_without_second_gain(f_range):
    raw=source_signal()
    p=fake_profile(i=1.,q=.2)
    a=envelope_spectrum_idr_candidate(raw,65536,20,p,
        n_fft=1024,f_range=f_range,mode=1,backend="numpy")
    b=envelope_spectrum_idr_candidate(raw,65536,20,p,
        n_fft=1024,f_range=f_range,mode=1,backend="numpy",
        input_domain=DOMAIN_ORIGINAL_STORAGE)
    if f_range==1.0:
        assert a["pre_fir_read_float32_sha256"]==b[
            "pre_fir_read_float32_sha256"]
        np.testing.assert_array_equal(a["amplitude"],b["amplitude"])
    else:
        assert a["pre_fir_read_float32_sha256"]!=b[
            "pre_fir_read_float32_sha256"]
        assert max(a["amplitude"]) > 0 and max(b["amplitude"]) > 0
        # A linear chain at nonzero amplitude first divides by range,
        # then multiplies the final result ONCE, not twice.
        ix=int(np.argmax(a["amplitude"]))
        assert b["amplitude"][ix]==pytest.approx(
            a["amplitude"][ix]/f_range,rel=.003)


@pytest.mark.parametrize("bad",[None,True,"guess","original_byte_storage",""])
def test_envelope_does_not_silently_accept_invalid_source_domain(bad):
    with pytest.raises(ValueError,match="domain"):
        envelope_spectrum_idr_candidate(
            source_signal(),65536,20,fake_profile(),
            n_fft=1024,backend="numpy",input_domain=bad)


def test_archive_spectrum_envelope_uses_explicit_source_only_and_never_edits_bin(tmp_path):
    native=fixture_zip(tmp_path)
    original_zip_bytes=native.read_bytes()
    session=OfflineSession.open(native)
    samples,fs,_,_=session.samples(1)
    original_adc=samples.tobytes()
    f_range=2.5
    kw=dict(channel=1,code=20,n_fft=1024,profile=fake_profile(i=1.,q=.4),
            end_s=4096/65536,backend="numpy",mode=1,f_range=f_range)
    calibrated=session.spectrum_envelope(**kw)
    storage=session.spectrum_envelope(**kw,input_domain=DOMAIN_ORIGINAL_STORAGE)
    assert calibrated["input_domain"]==DOMAIN_CALIBRATED_BIN
    assert not calibrated["original_storage_read_divided_by_range"]
    assert storage["input_domain"]==DOMAIN_ORIGINAL_STORAGE
    assert storage["original_storage_read_divided_by_range"]
    assert storage["input_source_window"]==calibrated["input_source_window"]
    assert storage["original_archive_position_parity_verified"] is False
    assert storage["original_f_range_verified"] is False
    assert storage["pre_fir_original_ring_start_index_unverified"]
    assert storage["pre_fir_read_float32_sha256"]!=calibrated[
        "pre_fir_read_float32_sha256"]
    assert storage["pre_fft_envelope_float32_sha256"]!=calibrated[
        "pre_fft_envelope_float32_sha256"]
    assert storage["input_source_window"]["source_float32_le_sha256"]==_sha_f32(
        samples[4096-2099:4096])
    assert native.read_bytes()==original_zip_bytes
    assert session.samples(1)[0].tobytes()==original_adc


def test_archive_explicit_original_float_ring_matches_direct_verified_input(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    data,fs,_,_=session.samples(1)
    f_range=4.
    p=fake_profile(i=1.,q=.4)
    archive=session.spectrum_envelope(
        1,20,1024,p,end_s=4096/65536,
        f_range=f_range,input_domain=DOMAIN_ORIGINAL_STORAGE,
        backend="idr_float32",mode=3)
    expected_read=prepare_original_fft_input(
        data[-2099:],f_range=f_range,input_domain=DOMAIN_ORIGINAL_STORAGE
    )["samples_before_dc_removal"]
    direct=envelope_spectrum_idr_candidate(
        expected_read,int(fs),20,p,n_fft=1024,mode=3,backend="idr_float32",
        f_range=f_range,input_domain=DOMAIN_CALIBRATED_BIN)
    assert archive["pre_fir_read_float32_sha256"]==_sha_f32(expected_read)
    assert archive["pre_fft_envelope_float32_sha256"]==direct[
        "pre_fft_envelope_float32_sha256"]
    assert archive["spectrum_summary"]==direct["spectrum_summary"]
    np.testing.assert_array_equal(archive["amplitude"],direct["amplitude"])


def test_original_storage_frange_overflow_is_rejected_before_fir():
    signal=np.asarray(source_signal(),dtype=np.float32)
    with pytest.raises(ValueError,match="FRange"):
        envelope_spectrum_idr_candidate(
            signal,65536,20,fake_profile(),n_fft=1024,
            input_domain=DOMAIN_ORIGINAL_STORAGE,f_range=1e-300,
            backend="numpy")


def test_exact_missing_history_remains_fail_closed_in_both_source_domains(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    p=fake_profile()
    for domain in (DOMAIN_CALIBRATED_BIN,DOMAIN_ORIGINAL_STORAGE):
        with pytest.raises(ValueError,match="Insufficient actual BIN history"):
            session.spectrum_envelope(1,1,1024,p,
                backend="numpy",input_domain=domain)
    assert not session.calculations()["source"].startswith("APP_DERIVED")
