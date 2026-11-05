"""Stage111Z31Q: synthetic-only same-RAW-window original Y pairing gate.

The tests create their own BIN/TSXML, Power, Y and operator-provenance
records. Synthetic references MUST NEVER be labelled real MVKView captures.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import numpy as np
import pytest

from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_envelope_idr_candidate import fake_profile
from ..core.direct_bin_session import DirectBinSession
from ..core.envelope_idr_candidate import (
    EnvelopeProfile, process_original_envelope_candidate,
)
from ..core.envelope_spectrum_idr_candidate import (
    required_original_history, _delphi_integration_power,
)
from ..core.fft_idr_candidate import idr_power_spectrum
from ..core.original_spectrum_x32dbg_reference import SCHEMA as REFERENCE_SCHEMA
from ..core.spectrum_display_source import source_derived_mode_display
from ..core.spectrum_metrics_idr_candidate import original_spectrum_summary
from ..private_same_window_spectrum_compare import (
    SCHEMA, PROVENANCE, compare_original_same_window_spectrum,
)

SOURCE_N = 1024
SOURCE_FS = 65536


def _manifest(folder: Path, raw: np.ndarray, *, mode: int, code: int,
              profile=None, offset=0):
    folder.mkdir(parents=True, exist_ok=True)
    if code:
        prepared=process_original_envelope_candidate(
            np.asarray(raw, dtype="<f4"), SOURCE_FS, code, profile, f_range=1.)
        before=np.asarray(prepared["chronological"], dtype="<f4")
        fs_out=int(prepared["output_sample_rate_hz"])
        power,_=idr_power_spectrum(before,backend="idr_float32",remove_dc=False)
    else:
        fs_out=SOURCE_FS
        power,_=idr_power_spectrum(raw,backend="idr_float32")
    power=np.asarray(power,dtype="<f4").copy()
    power[:max(2,round(SOURCE_N/fs_out*.5))]=0.
    if mode in (2,3):
        power=_delphi_integration_power(power,SOURCE_N,fs_out,mode-1)
    y=source_derived_mode_display(power,n_fft=SOURCE_N,
                                  mode=mode,f_range=1.)
    assert power.size==SOURCE_N//2 and np.isfinite(y).all()
    (folder/"power.bin").write_bytes(power.tobytes())
    (folder/"y.bin").write_bytes(y.tobytes())
    summary=original_spectrum_summary(
        power,n_fft=SOURCE_N,fs_out=fs_out,f_range=1.,spectrum_mode=mode)
    def hexword(value):
        return f"{struct.unpack('<I',struct.pack('<f',float(np.float32(value))))[0]:08X}"
    reference={
        "schema":REFERENCE_SCHEMA,"fft_n":SOURCE_N,
        "sample_rate_hz":fs_out,"spectrum_mode":mode,
        "f_range_bits":"3F800000","stop_va":"007D17E7",
        "power_file":"power.bin","display_y_file":"y.bin",
        "power_sha256":hashlib.sha256(power.tobytes()).hexdigest(),
        "display_y_sha256":hashlib.sha256(y.tobytes()).hexdigest(),
        "summary_hex":[hexword(summary[k]) for k in (
            "output_mean","output_peak_x_bin","output_peak_y")],
    }
    manifest=folder/"reference.json"
    manifest.write_text(json.dumps(reference),encoding="utf-8")
    evidence={
        "schema":SCHEMA,"original_window_provenance":PROVENANCE,
        "channel":4,"fft_n":SOURCE_N,
        "raw_sample_rate_hz":SOURCE_FS,"spectrum_mode":mode,
        "envelope_code":code,"first_archive_sample_index":offset,
        "last_archive_sample_exclusive":offset+len(raw),
        "original_raw_window_float32_sha256":hashlib.sha256(
            np.asarray(raw,dtype="<f4").tobytes()).hexdigest(),
        "input_domain":"calibrated_bin",
    }
    window=folder/"operator_claim.json"
    window.write_text(json.dumps(evidence),encoding="utf-8")
    return manifest,window,evidence


@pytest.mark.parametrize("mode",[0,1,2,3])
def test_real_qt_independent_plain_bin_full_y_pair_synthetic(
        tmp_path,mode):
    p,sidecar,samples=_make_pair(tmp_path,adc=4,n=SOURCE_N*3)
    start=SOURCE_N
    raw=samples[start:start+SOURCE_N]
    reference,window,_=_manifest(
        tmp_path/f"tag{mode}",raw,mode=mode,code=0,offset=start)
    result=compare_original_same_window_spectrum(p,reference,window)
    assert result["full_y_all_bitwise_equal"] is True
    assert result["full_y_bitwise_equal_bins"]==512
    assert result["maximum_float32_ulp_difference"]==0
    assert result["source_window_float32_sha256"]==hashlib.sha256(
        raw.tobytes()).hexdigest()
    assert result["first_archive_sample_index"]==start
    assert result["last_archive_sample_exclusive"]==start+SOURCE_N
    assert not result["original_runtime_same_thread_window_independently_authenticated"]
    assert not result["original_arbitrary_Fs_N_ADC_universally_verified"]
    assert "bin" not in result and "file" not in result


def test_refuses_wrong_claimed_window_even_if_original_power_y_is_valid(tmp_path):
    p,_,samples=_make_pair(tmp_path,adc=4,n=SOURCE_N*2)
    ref,window,meta=_manifest(
        tmp_path/"proof",samples[:SOURCE_N],mode=1,code=0)
    meta["first_archive_sample_index"]=1
    meta["last_archive_sample_exclusive"]=SOURCE_N+1
    window.write_text(json.dumps(meta),encoding="utf-8")
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        compare_original_same_window_spectrum(p,ref,window)


@pytest.mark.parametrize("bad",[
    ("channel",True),("channel",9),("fft_n",4096),
    ("spectrum_mode",3),("raw_sample_rate_hz",32768),
    ("input_domain","guessed_auto"),("envelope_code",31),
    ("original_raw_window_float32_sha256","0"*64),
    ("original_window_provenance","SYNTHETIC_NOT_ORIGINAL"),
])
def test_original_window_metadata_gate_rejects_drift(tmp_path,bad):
    p,_,samples=_make_pair(tmp_path,adc=4,n=SOURCE_N*3)
    ref,window,meta=_manifest(
        tmp_path/"operator",samples[:SOURCE_N],mode=0,code=0)
    meta[bad[0]]=bad[1]
    window.write_text(json.dumps(meta),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_same_window_spectrum(p,ref,window)


def test_valid_power_y_mismatch_reports_full_bin_error_not_false_parity(tmp_path):
    p,_,samples=_make_pair(tmp_path,adc=4,n=SOURCE_N*2)
    raw=samples[:SOURCE_N].copy()
    # Valid internally consistent synthetic 'original' reference derived
    # from a DIFFERENT signal while matching the raw operator-claimed SHA.
    other=(raw + np.sin(np.arange(SOURCE_N)*.34)).astype("<f4")
    ref,window,meta=_manifest(
        tmp_path/"other",other,mode=0,code=0)
    meta["original_raw_window_float32_sha256"]=hashlib.sha256(
        raw.tobytes()).hexdigest()
    window.write_text(json.dumps(meta),encoding="utf-8")
    result=compare_original_same_window_spectrum(p,ref,window)
    assert result["full_y_all_bitwise_equal"] is False
    assert 0 <= result["full_y_bitwise_equal_bins"] < SOURCE_N//2
    assert result["first_differing_bin"] is not None
    assert result["maximum_absolute_y_difference"] > 0


def test_envelope_same_window_uses_real_fir_history_and_all_bins(
        tmp_path,monkeypatch):
    code=20
    plan=required_original_history(SOURCE_N,SOURCE_FS,code)
    length=plan["input_samples"]
    p,_,samples=_make_pair(tmp_path,adc=4,n=length+32)
    first=32
    raw=samples[first:first+length]
    profile=fake_profile()
    ref,window,_=_manifest(
        tmp_path/"envelope",raw,mode=1,code=code,
        profile=profile,offset=first)
    monkeypatch.setattr(
        EnvelopeProfile,"from_original_local_idp",
        classmethod(lambda cls, path: profile))
    result=compare_original_same_window_spectrum(
        p,ref,window,original_idp=tmp_path/"local_only.idp")
    assert result["envelope_code"]==20
    assert result["input_window_sample_count"]==length
    assert result["full_y_all_bitwise_equal"]
    assert not result["original_envelope_prefft_runtime_verified_by_this_tool"]
    with pytest.raises(ValueError,match="original local IDP"):
        compare_original_same_window_spectrum(p,ref,window)
