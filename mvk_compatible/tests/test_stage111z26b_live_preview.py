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
    assert preview.channels[1].samples.size==MAX_SAMPLES
    signal=provisional_waveform(preview,1,ac=False)
    assert signal["source"]=="LIVE_NATIVE_R6_CALIBRATED_PREVIEW_UNVERIFIED"
    assert signal["provisional_not_audited"]
    assert signal["time_s"][0]==pytest.approx(4096/65536)
    assert signal["rms_m_s2"]>0.5
    spec=provisional_spectrum(preview,1,mode=1)
    assert spec["n_fft"]==65536
    assert spec["df_hz"]==1.
    assert spec["source_fft_n_matches_requested_bSpecLines"]
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
        if case=="bad_sample_count": meta["channels"][0]["samples"]=MAX_SAMPLES+1
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


def test_live_source_spec_lines_recomputes_exact_requested_original_fft_n(tmp_path):
    root,status,_=make_preview(tmp_path)
    preview=load_live_preview(root,status,now=now())
    for selected in (8192,16384,32768,65536):
        spectrum=provisional_spectrum(preview,1,mode=1,n_fft=selected)
        assert spectrum["n_fft"]==selected
        assert spectrum["df_hz"]==pytest.approx(65536/selected)
        assert spectrum["source_selected_fft_n"]==selected
        assert spectrum["source_fft_n_matches_requested_bSpecLines"]
    for not_yet_available in (131072,262144):
        with pytest.raises(ValueError,match="реальных отсчётов"):
            provisional_spectrum(
                preview,1,mode=1,n_fft=not_yet_available)
    with pytest.raises(ValueError,match="Invalid original"):
        provisional_spectrum(preview,1,n_fft=8193)
    with pytest.raises(ValueError,match="Invalid original"):
        provisional_spectrum(preview,1,n_fft=True)


def test_source_prebuffer_does_not_pad_or_downsample_requested_n(tmp_path):
    root,status,_=make_preview(tmp_path,count=8192)
    preview=load_live_preview(root,status,now=now())
    assert provisional_spectrum(preview,1,n_fft=8192)["n_fft"]==8192
    with pytest.raises(ValueError,match="FFT N=65536"):
        provisional_spectrum(preview,1,n_fft=65536)


def test_late_tcp_attach_absolute_instrument_index_still_validates(tmp_path):
    from mvk_compatible.core.original_live_view_gate import gate_live_preview
    offset=1_000_000
    def large_device_cursor(meta):
        for row in meta["channels"]:
            row["first_sample_index"]+=offset
            row["next_sample_index"]+=offset
    root,status,_=make_preview(tmp_path,modify=large_device_cursor)
    expected_next=offset+4096+MAX_SAMPLES
    for channel in status["channels"][:8]:
        channel["next_sample_index"]=expected_next
    preview=load_live_preview(root,status,now=now())
    assert preview.channels[1].first_index==offset+4096
    assert preview.channels[1].next_index==expected_next
    allowed=gate_live_preview(status,preview)
    assert allowed.allowed,allowed.reason
    assert provisional_spectrum(preview,1,mode=1,n_fft=65536)["n_fft"]==65536
    # If Go reports a source end cursor behind this window,
    # the independent local core must reject it before Qt.
    status["channels"][0]["next_sample_index"]=expected_next-256
    with pytest.raises(ValueError,match="absolute index mismatch"):
        load_live_preview(root,status,now=now())
    denied=gate_live_preview(status,preview)
    assert not denied.allowed
    assert denied.phase=="SOURCE_INDEX_MISMATCH"


def test_legacy_status_without_source_device_cursor_is_not_invented(tmp_path):
    root,status,_=make_preview(tmp_path)
    # Validator normalizes absent legacy producer fields to None;
    # it never invents a numeric source cursor.
    assert all(ch.get("next_sample_index") is None for ch in status["channels"])
    preview=load_live_preview(root,status,now=now())
    assert gate_live_preview(status,preview).allowed
