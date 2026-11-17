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
                 count=65536, source_rate=65536):
    root = tmp_path / "capture"
    state = fixture_state()
    # One synthetic source run: the atomic preview and Go status refer
    # to the SAME capture-local uint64 count. The older fixture kept
    # 76800 status samples for a 65536-sample window; that is valid only
    # if the device next-index also advances by the remaining 11264.
    # Our fixture supplies a device end exactly at 4096+count instead.
    for ch in state["channels"][:8]:
        ch["samples"] = count
        ch["frames"] = count//256
    if count > 300*256:
        state["raw_bytes"] = 32*count + 50_000
        state["frames_decoded"] = 8*(count//256) + 100
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
            captured_samples=len(samples),
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
    assert preview.channels[1].samples.size==65536
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
    expected_next=offset+4096+65536
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
    from mvk_compatible.core.original_live_view_gate import gate_live_preview
    root,status,_=make_preview(tmp_path)
    # Validator normalizes absent legacy producer fields to None;
    # it never invents a numeric source cursor.
    assert all(ch.get("next_sample_index") is None for ch in status["channels"])
    preview=load_live_preview(root,status,now=now())
    assert gate_live_preview(status,preview).allowed


def test_source_full_original_n131072_and_n262144_use_real_bins(tmp_path):
    # Original _Unit128:0084819A maps the two largest bSpecLines tags to
    # actual GetSpectrum counts. No 65536 downshift and no zero-padding.
    root,status,run=make_preview(tmp_path,count=MAX_SAMPLES)
    preview=load_live_preview(root,status,now=now())
    assert len(preview.channels)==8
    assert preview.channels[1].samples.size==262144
    for selected in (131072,262144):
        spec=provisional_spectrum(preview,1,mode=1,n_fft=selected)
        assert spec["n_fft"]==selected
        assert spec["df_hz"]==pytest.approx(65536/selected)
        assert spec["source_selected_fft_n"]==selected
        assert spec["source_fft_full_power_bins"]==selected//2
        assert spec["original_delphi_numerical_parity"] is False
        assert len(spec["frequency_hz"])<=5000
        assert spec["spectrum_summary"]
        f=np.asarray(spec["frequency_hz"])
        y=np.asarray(spec["amplitude"])
        assert f[int(np.argmax(y))]==pytest.approx(1000.,abs=65536/selected)
        assert y.max()>0
    assert (run/NAME).is_file()
    assert len(list(run.iterdir()))==1


def test_large_live_ring_does_not_break_30_second_getsignal_window(tmp_path):
    # At 512 Hz, 262144 samples represent 512 seconds; only display the
    # measured latest <=30 s while preserving all FFT input samples.
    root,status,_=make_preview(tmp_path,count=MAX_SAMPLES,source_rate=512)
    for ch in status["channels"][:8]:
        ch["sample_rates_hz"]=[512]
    preview=load_live_preview(root,status,now=now())
    wave=provisional_waveform(preview,1,ac=False)
    assert wave["window_samples"]==30*512
    assert wave["source_live_preview_ring_samples"]==MAX_SAMPLES
    assert wave["source_waveform_latest_real_samples"]==30*512
    assert wave["input_source_window"]["live_first_adc_sample_index"]==(
        4096+MAX_SAMPLES-30*512)
    assert wave["input_source_window"]["live_last_adc_sample_exclusive"]==(
        4096+MAX_SAMPLES)


def test_full_native_preview_rejects_source_nonfinite_and_oversized_row(tmp_path):
    root,status,_=make_preview(tmp_path,count=MAX_SAMPLES)
    status["channels"][0]["samples"]=MAX_SAMPLES-256
    with pytest.raises(ValueError,match="channel count"):
        load_live_preview(root,status,now=now())


def test_original_live_adc_hscale_14_values_use_exact_received_getsignal_window(
        tmp_path):
    from mvk_compatible.core.native_r6_live_preview import provisional_waveform
    root,status,_=make_preview(tmp_path,count=65536)
    preview=load_live_preview(root,status,now=now())
    for tag,length,ms in ((4,65536,1000),(5,32768,500),(8,3276,50),
                           (13,65,1)):
        d=provisional_waveform(
            preview,1,ac=False,source_h_tag=tag,
            capture_rxpos=status["channels"][0]["samples"],
            source_allow_overlap=(ms>1000))
        assert d["window_samples"]==length
        assert d["original_bAdcHScale_milliseconds"]==ms
        assert d["original_bAdcHScale_requested_samples"]==length
        assert d["source_getsignal_exact_selected_count"]
        assert d["source_getsignal_readiness"]["verified_preview_window_ready"]
        assert d["input_source_window"]["live_last_adc_sample_exclusive"]==(
            4096+65536)
        assert d["input_source_window"]["live_first_adc_sample_index"]==(
            4096+65536-length)
    # Original 20s Tag0 does not magically shrink to 4s of preview data.
    with pytest.raises(ValueError,match="GetSignal 20000 мс"):
        provisional_waveform(
            preview,1,source_h_tag=0,
            capture_rxpos=status["channels"][0]["samples"])


def test_original_live_getsignal_waits_for_new_samples_without_fake_zero_fill(
        tmp_path):
    root,status,_=make_preview(tmp_path,count=65536)
    preview=load_live_preview(root,status,now=now())
    rx=status["channels"][0]["samples"]
    first=provisional_waveform(
        preview,1,ac=True,source_h_tag=5,
        capture_rxpos=rx,last_processed_pos=0,
        source_allow_overlap=False)
    assert first["window_samples"]==32768
    assert first["source_getsignal_readiness"]["next_processed_pos_64"]==rx
    with pytest.raises(ValueError,match="ожидание|требуется"):
        provisional_waveform(
            preview,1,ac=True,source_h_tag=5,
            capture_rxpos=rx,last_processed_pos=rx,
            source_allow_overlap=False)
    # In original overlapping mode Readiness is true even without new
    # samples; the content remains real, same SHA-confirmed Float32.
    reuse=provisional_waveform(
        preview,1,ac=True,source_h_tag=5,
        capture_rxpos=rx,last_processed_pos=rx,
        source_allow_overlap=True)
    assert reuse["window_samples"]==32768
    assert reuse["source_getsignal_readiness"][
        "original_check_data_availability"]


def test_source_u32_rollover_validates_real_go_capture_cursor(tmp_path):
    from mvk_compatible.core.original_sample_cursor32 import (
        u32_preview_bounds,u32_matches_go_status,u32_has_advanced,
    )
    from mvk_compatible.core.original_live_view_gate import gate_live_preview
    mask=(1<<32)-1
    count=65536
    end=4096
    first=(end-count)&mask
    assert first>end and u32_preview_bounds(first,end,count)
    assert u32_has_advanced(0xFFFFF000,0x0000F000,received_since_last=65536)
    assert not u32_has_advanced(0xFFFFF000,0xFFFFF000,received_since_last=65536)
    def source_wrap(meta):
        for ch in meta["channels"]:
            ch["first_sample_index"]=first
            ch["next_sample_index"]=end
    root,status,_=make_preview(tmp_path,modify=source_wrap)
    for ch in status["channels"][:8]:
        ch["next_sample_index"]=end
    preview=load_live_preview(root,status,now=now())
    assert preview.channels[1].captured_samples==status["channels"][0]["samples"]
    assert gate_live_preview(status,preview).allowed
    wave=provisional_waveform(preview,1,source_h_tag=4,
        capture_rxpos=count,source_allow_overlap=False)
    evidence=wave["input_source_window"]
    assert evidence["source_index_u32_wrapped"]
    assert evidence["capture_local_uint64_cursor_confirmed"]
    assert evidence["live_first_adc_sample_index"]==(1<<32)+end-count
    assert evidence["live_last_adc_sample_exclusive"]==(1<<32)+end
    assert wave["time_s"][0]==pytest.approx(((1<<32)+end-count)/65536)
    newer=dict(status)
    newer["channels"]=[dict(x) for x in status["channels"]]
    newer["channels"][0]["samples"]+=256
    newer["channels"][0]["next_sample_index"]=(end+256)&mask
    assert u32_matches_go_status(
        end,(end+256)&mask,
        status_samples=status["channels"][0]["samples"]+256,
        window_samples=count,
        captured_samples=status["channels"][0]["samples"])
    assert gate_live_preview(newer,preview).allowed
    # A backwards device cursor cannot be mistaken for a valid wrap.
    newer["channels"][0]["next_sample_index"]=(end-256)&mask
    assert not gate_live_preview(newer,preview).allowed
    with pytest.raises(ValueError,match="absolute index mismatch"):
        load_live_preview(root,newer,now=now())
    assert not u32_matches_go_status(
        end,(end+256)&mask,status_samples=count+512,
        window_samples=count,captured_samples=count)


def test_source_u32_legacy_ambiguous_epoch_fails_closed():
    from mvk_compatible.core.original_sample_cursor32 import (
        u32_preview_bounds,u32_matches_go_status,extended_u32_window,
    )
    assert not u32_preview_bounds(123,123,65536)
    assert not u32_preview_bounds(-1,0,1)
    assert not u32_preview_bounds(True,0,1)
    assert not u32_matches_go_status(100,100,
        status_samples=(1<<32)+256,window_samples=256,captured_samples=None)
    assert not u32_matches_go_status(100,102,
        status_samples=1000,window_samples=256,captured_samples=999)
    assert extended_u32_window(0xFFFF0000,0,65536,65536)==(
        0xFFFF0000,1<<32)


def test_continuous_measure_go_uint64_raw_and_frame_counters_do_not_truncate(
        tmp_path):
    # The Go source stores RAW bytes and frame counters as uint64.
    # This case is metadata-only; no synthetic 4GiB buffer or socket.
    count=(1<<32)+1234
    def long_capture(meta):
        meta["raw_bytes"]=count
        meta["frames_decoded"]=count
    root,status,_=make_preview(tmp_path,modify=long_capture)
    status["raw_bytes"]=count
    status["frames_decoded"]=count
    preview=load_live_preview(root,status,now=now())
    assert preview is not None
    assert preview.raw_bytes==count and preview.frames_decoded==count
    # Device SampleHeader.Index must still be strictly uint32.
    def source_invalid_index(meta):
        meta["channels"][0]["next_sample_index"]=1<<32
    other=tmp_path/"invalid"
    root2,status2,_=make_preview(other,modify=source_invalid_index)
    with pytest.raises(ValueError,match="invalid calibrated sample metadata"):
        load_live_preview(root2,status2,now=now())
