"""Stage111Z30B — synthetic only: original GetSpectrum Y Float32 staging."""
from __future__ import annotations

import hashlib
import json
import math
import struct

import numpy as np
import pytest

from mvk_compatible.core.spectrum_display_source import (
    source_derived_mode_display, display_source_provenance)
from mvk_compatible.private_getspectrum_display_y_compare import (
    SOURCE, SCHEMA, compare_original_display_y_pair, main)


def test_original_helper_is_log10_not_natural_log_with_stored_single_offset():
    n = 262144
    p = np.zeros(n//2, dtype="<f4")
    p[100] = 1.
    p[101] = 0.01
    original = p.copy()
    result = source_derived_mode_display(p,n_fft=n,mode=0)
    assert np.array_equal(p,original)
    assert float(result[0]) == -180.
    assert float(result[100]) == -102.3501968383789
    offset = float(np.float32(2.*math.log10(n//2)))
    assert offset == 10.23501968383789
    assert float(result[101]) == pytest.approx(-122.3501968383789, abs=2e-5)
    assert result.dtype == np.dtype("<f4")
    assert display_source_provenance()["original_log10_helper_flDLG2_FYL2X_source_verified"]
    assert display_source_provenance()["original_x87_log10_sqrt_float32_bitwise_parity_verified"] is False


@pytest.mark.parametrize("mode", [1,2,3])
def test_linear_mode_f32_scale_stored_once_before_sqrt(mode):
    n = 1024
    powers = np.zeros(n//2,dtype="<f4")
    powers[47] = np.float32(150.)
    fr = np.float32(2.25)
    calc = source_derived_mode_display(powers,n_fft=n,mode=mode,f_range=float(fr))
    scale = float(np.float32(float(fr)/(n//2)))
    manual = np.float32(math.sqrt(150./2.)*scale)
    assert calc[47].view("<u4") == manual.view("<u4")
    assert calc[0] == 0
    assert np.all(calc >= 0)


def _local_pair(tmp_path, mode=0):
    n=1024
    p=np.full(n//2,np.float32(1.),dtype="<f4")
    p[0]=p[1]=0.
    p[47]=np.float32(150.)
    display=source_derived_mode_display(p,n_fft=n,mode=mode,f_range=2.25)
    pf=tmp_path/"original_post_mode.bin"
    yf=tmp_path/"original_display_y.bin"
    pf.write_bytes(p.tobytes())
    yf.write_bytes(display.tobytes())
    manifest={
        "schema":SCHEMA, "fft_n":n,
        "output_sample_rate_hz":65536, "spectrum_mode":mode,
        "channel_index_zero_based":3, "envelope_code":0,
        "f_range_bits":"0x40100000",
        "power_stop_va":"0x007D17E7", "display_stop_va":"0x007D17E7",
        "power_buffer_role":"EBP-2C", "display_buffer_role":"EBP-30",
        "same_invocation_operator_confirmed":True,
        "post_mode_power_file":pf.name,"display_y_file":yf.name,
        "post_mode_power_sha256":hashlib.sha256(p.tobytes()).hexdigest(),
        "display_y_sha256":hashlib.sha256(display.tobytes()).hexdigest(),
    }
    path=tmp_path/"original_display_pair.json"
    path.write_text(json.dumps(manifest),encoding="utf-8")
    return path, manifest, p, display


@pytest.mark.parametrize("mode", [0,1,2,3])
def test_full_synthetic_capture_matches_source_candidate_and_preserves_privacy(tmp_path,mode):
    path, d, p, y = _local_pair(tmp_path,mode=mode)
    r=compare_original_display_y_pair(path)
    assert r["source"]==SOURCE
    assert r["source_derived_single_staging"]["float32_bitwise_equal_count"]==512
    assert r["source_derived_bitwise_equal_to_operator_capture"] is True
    assert r["original_full_four_mode_runtime_parity_certified"] is False
    assert r["same_original_invocation_independently_authenticated"] is False
    serialized=json.dumps(r)
    assert d["f_range_bits"] not in serialized
    assert d["post_mode_power_file"] not in serialized
    assert d["display_y_file"] not in serialized
    assert str(tmp_path) not in serialized
    assert main([str(path)]) == 0


def test_single_float32_ulp_change_is_detected(tmp_path):
    path, d, p, display = _local_pair(tmp_path,mode=0)
    display[47]=np.nextafter(display[47],np.float32(np.inf))
    yf=tmp_path/d["display_y_file"]
    yf.write_bytes(display.tobytes())
    d["display_y_sha256"]=hashlib.sha256(display.tobytes()).hexdigest()
    path.write_text(json.dumps(d),encoding="utf-8")
    r=compare_original_display_y_pair(path)
    assert not r["source_derived_bitwise_equal_to_operator_capture"]
    assert r["source_derived_single_staging"]["float32_bitwise_unequal_count"]==1
    assert r["source_derived_single_staging"]["within_one_float32_ulp_count"]==512
    assert main([str(path)]) == 1


@pytest.mark.parametrize(("field","value"), [
    ("fft_n",1000),("fft_n",True),("spectrum_mode",4),
    ("output_sample_rate_hz",0),("channel_index_zero_based",8),
    ("envelope_code",100),("f_range_bits","0x7F800000"),
    ("power_stop_va","0x007D154B"),("display_stop_va","0x007D1900"),
    ("power_buffer_role","EBP-30"),("display_buffer_role","EBP-2C"),
    ("same_invocation_operator_confirmed",False),
    ("post_mode_power_file","../private.bin"),("display_y_file","C:\\secret.bin"),
    ("post_mode_power_sha256","BAD"),("display_y_sha256","A"*64),
])
def test_invalid_original_metadata_rejected(tmp_path,field,value):
    path,d,_,_ = _local_pair(tmp_path,mode=1)
    d[field]=value
    path.write_text(json.dumps(d),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_display_y_pair(path)


def test_refuse_zero_negative_nan_bad_hash_and_missing_original(tmp_path):
    path,d,p,display = _local_pair(tmp_path,mode=1)
    d["unknown_data"]="NO"
    path.write_text(json.dumps(d),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_display_y_pair(path)
    path,d,p,display = _local_pair(tmp_path,mode=1)
    p.fill(0)
    raw=p.tobytes()
    (tmp_path/d["post_mode_power_file"]).write_bytes(raw)
    d["post_mode_power_sha256"]=hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(d),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_display_y_pair(path)
    path,d,p,display = _local_pair(tmp_path,mode=1)
    display[50]=np.float32(-1.)
    raw=display.tobytes()
    (tmp_path/d["display_y_file"]).write_bytes(raw)
    d["display_y_sha256"]=hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(d),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_display_y_pair(path)
    path,d,p,display = _local_pair(tmp_path,mode=0)
    display[47]=np.nan
    raw=display.tobytes()
    (tmp_path/d["display_y_file"]).write_bytes(raw)
    d["display_y_sha256"]=hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(d),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_original_display_y_pair(path)


def test_invalid_helper_inputs_never_silently_corrected():
    p=np.ones(512,dtype="<f4")
    for n,mode,fr in [(1000,0,1.),(1024,4,1.),(1024,1,0.),(1024,1,float("inf"))]:
        with pytest.raises(ValueError):
            source_derived_mode_display(p,n_fft=n,mode=mode,f_range=fr)
    p[3]=np.nan
    with pytest.raises(ValueError):
        source_derived_mode_display(p,n_fft=1024,mode=0)


def test_capture_symlink_rejected(tmp_path):
    path,d,_,_= _local_pair(tmp_path)
    p=tmp_path/d["display_y_file"]
    real=tmp_path/"real_display.bin"
    p.rename(real)
    try:
        p.symlink_to(real)
    except (OSError,NotImplementedError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError):
        compare_original_display_y_pair(path)
