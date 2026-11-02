"""Stage111Z.26B: synthetic offline validation of live Float32 preview with no sockets."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

from mvk_compatible.core.native_r6_live_preview import (
    NAME, SCHEMA, DOMAIN, MAX_SAMPLES, load_live_preview,
    provisional_waveform, provisional_spectrum,
)
from .test_stage111z26_native_live_status import fixture_state, now
from mvk_compatible.core.native_r6_live_status import validate_live_status


def make_preview(tmp_path, *, modify=None, tamper_adc=False, extra=False,
                 count=MAX_SAMPLES, source_rate=65536):
    root = tmp_path / "capture"
    state = fixture_state()
    run = root / state["session_id"]
    run.mkdir(parents=True)
    state["run_directory"] = str(run)
    status = validate_live_status(state, expected_run=state["session_id"], now=now())
    status["run_directory"] = str(run)
    meta = dict(
        schema=SCHEMA, session_id=state["session_id"],
        phase="RECORDING", updated_utc=state["updated_utc"],
        input_domain=DOMAIN, calibration_already_applied=True,
        read_only_no_app_payload_sent=True, provisional_not_audited=True,
        raw_bytes=500_000, frames_decoded=900, channels=[],
    )
    raw={}
    for channel in range(1, 9):
        t=np.arange(count,dtype=np.float64)/source_rate
        # Values already carry Native gain. Never apply gain twice!
        samples=np.asarray(channel*np.sin(2*np.pi*1000*t),dtype="<f4")
        data=samples.tobytes()
        name=f"ADC{channel}.f32"
        raw[name]=data
        meta["channels"].append(dict(
            adc=channel, entry=name, samples=len(samples),
            sample_rate_hz=source_rate,
            first_sample_index=4096,
            next_sample_index=4096+len(samples),
            sha256=hashlib.sha256(data).hexdigest(),
        ))
    if modify is not None:
        modify(meta)
    if tamper_adc:
        raw["ADC1.f32"]=bytes([raw["ADC1.f32"][0] ^ 0x01])+raw["ADC1.f32"][1:]
    with zipfile.ZipFile(run/NAME,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for key,value in raw.items():
            z.writestr(key,value)
        z.writestr("MANIFEST.json",json.dumps(meta))
        if extra:
            z.writestr("untrusted.bin",b"123")
    return root,status,run


def test_preview_fft_uses_existing_candidate_and_precalibrated_bits(tmp_path):
    root,status,run=make_preview(tmp_path)
    preview=load_live_preview(root,status,now=now())
    assert preview.session_id==status["session_id"]
    assert set(preview.channels)==set(range(1,9))
    assert preview.channels[0+1].first_index==4096
    assert preview.channels[1].samples.dtype==np.dtype("<f4")
    assert preview.channels[1].samples.size==8192
    signal=provisional_waveform(preview,1,ac=False)
    assert signal["source"]=="LIVE_NATIVE_R6_CALIBRATED_PREVIEW_UNVERIFIED"
    assert signal["provisional_not_audited"]
    assert signal["time_s"][0]==pytest.approx(4096/65536)
    assert signal["rms_m_s2"]>0.5
    spec=provisional_spectrum(preview,1,mode=1)
    assert spec["n_fft"]==8192
    assert spec["df_hz"]==8.
    assert spec["f_range_used"]==1.
    assert spec["input_domain"]=="calibrated_bin"
    assert spec["provisional_not_audited"] is True
    frequencies=np.asarray(spec["frequency_hz"])
    amplitude=np.asarray(spec["amplitude"])
    assert frequencies[int(np.argmax(amplitude))]==pytest.approx(1000.)
    assert amplitude.max()>0
    assert (run/NAME).is_file()
    assert len(list(run.iterdir()))==1  # Qt read-only; no BIN/RAW overwritten


@pytest.mark.parametrize("case",[
    "wrong_session","double_gain_domain","not_precalibrated","not_provisional",
    "future","old","duplicate_adc","bad_sample_count","not_read_only","extra",
    "tamper","wrong_rate","not_recording","bad_status","foreign_root"
])
def test_corrupted_or_mixed_preview_never_reaches_graphs(tmp_path,case):
    def mutate(meta):
        if case=="wrong_session": meta["session_id"]="TEST_2026-11-02_12-01-02.888"
        if case=="double_gain_domain": meta["input_domain"]="original_float_storage"
        if case=="not_precalibrated": meta["calibration_already_applied"]=False
        if case=="not_provisional": meta["provisional_not_audited"]=False
        if case=="future": meta["updated_utc"]="2026-11-02T09:02:50Z"
        if case=="old": meta["updated_utc"]="2026-11-02T09:00:55Z"
        if case=="duplicate_adc": meta["channels"][1]["adc"]=1
        if case=="bad_sample_count": meta["channels"][0]["samples"]=8193
        if case=="not_read_only": meta["read_only_no_app_payload_sent"]=False
        if case=="wrong_rate": meta["channels"][0]["sample_rate_hz"]=12345
    root,status,run=make_preview(tmp_path,
        modify=mutate if case not in ("tamper","extra","not_recording","bad_status","foreign_root") else None,
        tamper_adc=case=="tamper",extra=case=="extra")
    if case=="not_recording": status["phase"]="VERIFYING"
    if case=="bad_status": status["invalid_frames"]=1
    if case=="foreign_root": status["run_directory"]=str(tmp_path)
    if case=="not_recording":
        assert load_live_preview(root,status,now=now()) is None
    else:
        with pytest.raises(ValueError):
            load_live_preview(root,status,now=now())


def test_preview_waits_for_real_stream_and_rejects_stale(tmp_path):
    root=tmp_path/"capture"
    state=fixture_state()
    run=root/state["session_id"]
    run.mkdir(parents=True)
    data=validate_live_status(state,expected_run=state["session_id"],now=now())
    data["run_directory"]=str(run)
    assert load_live_preview(root,data,now=now()) is None


def test_insufficient_original_history_stays_disallowed(tmp_path):
    root,status,_=make_preview(tmp_path,count=512)
    preview=load_live_preview(root,status,now=now())
    assert preview.channels[1].samples.size==512
    with pytest.raises(ValueError,match="insufficient"):
        provisional_spectrum(preview,1)
