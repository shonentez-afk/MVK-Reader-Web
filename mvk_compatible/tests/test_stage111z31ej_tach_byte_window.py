"""Typed source Byte windows, not a Float32 reinterpretation."""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import zipfile

import numpy as np
import pytest

from ..core.original_source_long_window import (
    REQUEST_NAME,RESULT_NAME,RESULT_SCHEMA,submit_source_long_window,
    submit_source_fft_window,submit_source_envelope_window,load_source_long_window)
from ..core.original_source_ring_receipt import TACH_DOMAIN
from ..core.native_r6_live_preview import provisional_waveform,provisional_spectrum
from ..core.original_live_adc_cursor import bind_source_live_wave_cursor,pick_source_live_wave_cursor
from ..core.original_live_spectrum_view import bind_live_spectrum_view
from ..core.original_live_view_gate import gate_live_preview
from ..core.native_r6_live_status import validate_live_status
from .test_stage111z31fj_original_long_window import long_source_status,response_fixture

def tach_status(tmp_path):
    run,status=long_source_status(tmp_path)
    for i in (8,9):
        status["channels"][i].update(samples=512,frames=8,
            sample_rates_hz=[65536],next_sample_index=0x40000000,
            nonfinite_samples=512)
        status["source_original_storage"]["channels"][i].update(
            rx_pos_64=2048,available_elements=2048,last_sample_rate_hz=65536,
            next_device_sample_index=0x40000000,input_domain=TACH_DOMAIN)
    return run,status

def byte_response(run,status,request,override=None):
    data=(np.arange(request.samples,dtype=np.uint32)%256).astype("u1").tobytes()
    end=(request.device_end_index*4)&0xffffffff
    meta=dict(schema=RESULT_SCHEMA,session_id=request.session_id,
        request_id=request.request_id,phase="RECORDING",
        updated_utc=datetime.now(timezone.utc).isoformat(),
        adc=request.adc,source_h_tag=request.h_tag,entry=f"TACH{request.adc-8}.u8",
        samples=request.samples,capture_end=request.capture_end,sample_rate_hz=request.sample_rate_hz,
        first_sample_index=(end-request.samples)&0xffffffff,next_sample_index=end,
        device_end_word_index=request.device_end_index,sample_width_bytes=1,
        input_domain=TACH_DOMAIN,calibration_already_applied=False,provisional_not_audited=True,
        raw_bytes=status["raw_bytes"],frames_decoded=status["frames_decoded"],
        sha256=sha256(data).hexdigest())
    if override: override(meta)
    with zipfile.ZipFile(run/RESULT_NAME,"w",compression=zipfile.ZIP_STORED) as z:
        z.writestr(meta["entry"],data)
        z.writestr("MANIFEST.json",json.dumps(meta))
    return data

def test_tach_getsignal_byte_to_single_exact_and_cursor(tmp_path):
    run,status=tach_status(tmp_path)
    req=submit_source_long_window(run,status,9,9)
    assert req.samples==1310 and req.sample_width_bytes==1
    request_json=json.loads((run/REQUEST_NAME).read_text())
    assert request_json["device_end_index"]==0x40000000
    assert request_json["sample_width_bytes"]==1
    data=byte_response(run,status,req)
    window=load_source_long_window(run,status,req)
    ch=window.preview.channels[9]
    assert ch.samples.dtype==np.uint8 and ch.samples.tobytes()==data
    assert ch.first_index>ch.next_index and ch.sha256==sha256(data).hexdigest()
    wave=provisional_waveform(window.preview,9,ac=True,source_h_tag=9,capture_rxpos=2048)
    want=(np.frombuffer(data,dtype="u1").astype(np.float64)/255.).astype("<f4")
    np.testing.assert_array_equal(wave["cursor_full_reversed_getsignal"],want[::-1])
    assert wave["mode"]=="acdc" and wave["removed_mean_m_s2"]==0
    assert wave["source_live_units"]=="" and wave["source_live_f_range_single"]==1
    cur=bind_source_live_wave_cursor(wave,window.preview,9)
    picked=pick_source_live_wave_cursor(cur,0.)
    assert picked["original_uint64_tach_byte_index"]==2047
    assert picked["full_float32_value"]==float(want[-1])

@pytest.mark.parametrize("mode,units",[(0,"дБ"),(1,""),(2,"~"),(3,"~~")])
def test_tach_spectrum_all_modes_use_normalized_bytes(tmp_path,mode,units):
    run,status=tach_status(tmp_path)
    req=submit_source_fft_window(run,status,10,1024)
    byte_response(run,status,req)
    window=load_source_long_window(run,status,req)
    result=provisional_spectrum(window.preview,10,mode=mode,n_fft=1024,full_bins=True)
    view=bind_live_spectrum_view(window.preview,10,result,selected_n=1024,code=0,mode=mode)
    assert view["unit"]==units and view["source_live_units"]==""
    assert view["source_unit_bound"] and len(view["amplitude"])==512
    assert result["detrended_before_fft"] and result["f_range_used"]==1.
    assert view["live_window_sha256"]==window.preview.channels[10].sha256

@pytest.mark.parametrize("override",[
    lambda m:m.update(sample_width_bytes=4),
    lambda m:m.update(device_end_word_index=0x80000000),
    lambda m:m.update(calibration_already_applied=True),
    lambda m:m.update(next_sample_index=4),
    lambda m:m.update(input_domain="ORIGINAL_LIVE_ADC_FRANGE1_FLOAT32"),
    lambda m:m.update(sha256="0"*64)])
def test_tach_rejects_forged_type_cursor_or_bytes(tmp_path,override):
    run,status=tach_status(tmp_path)
    req=submit_source_long_window(run,status,9,9)
    byte_response(run,status,req,override)
    with pytest.raises(ValueError):
        load_source_long_window(run,status,req)

def test_tach_channel_switch_ignores_previous_adc_result_and_refuses_fir(tmp_path):
    run,status=tach_status(tmp_path)
    old=submit_source_long_window(run,status,1,9)
    response_fixture(run,status,old)
    req=submit_source_long_window(run,status,9,9)
    assert load_source_long_window(run,status,req) is None
    with pytest.raises(ValueError,match="Byte TACH"):
        submit_source_envelope_window(run,status,9,1024,20)
    status["source_original_storage"]["channels"][8]["available_elements"]=20
    assert submit_source_long_window(run,status,9,9) is None

def test_actual_go_tach_window_to_python(tmp_path):
    root=os.getenv("MVK_PREFIX_FIXTURE_DIR")
    if not root: pytest.skip("actual Go fixture generated by isolated CI")
    source=Path(root)/"TEST_2026-11-24_06-00-00.000"
    run=Path(shutil.copytree(source,tmp_path/source.name))
    raw=json.loads((run/"TACH_WINDOW_STATUS.json").read_text())
    now=datetime.now(timezone.utc)
    raw["updated_utc"]=now.isoformat()
    status=validate_live_status(raw,expected_run=run.name,now=now)
    status["run_directory"]=str(run)
    assert not status["quality_alert"]
    for ch,tag,entry,rid in [(9,9,"TACH1.u8","a"*32),(10,-1,"TACH2.u8","b"*32)]:
        req=(submit_source_long_window(run,status,ch,tag,request_id=rid) if tag>=0
            else submit_source_fft_window(run,status,ch,1024,request_id=rid))
        assert req is not None
        # Restore the actual Go ZIP. Only its local timestamp can age
        # while installing CI dependencies; validate at its recorded time.
        shutil.copyfile(run/(entry+".zip"),run/RESULT_NAME)
        with zipfile.ZipFile(run/RESULT_NAME) as z:
            stamp=datetime.fromisoformat(json.loads(z.read("MANIFEST.json"))["updated_utc"].replace("Z","+00:00"))
        window=load_source_long_window(run,status,req,now=stamp)
        assert window is not None and gate_live_preview(status,window.preview).allowed
        assert window.preview.channels[ch].samples.dtype==np.uint8
        if tag>=0:
            wave=provisional_waveform(window.preview,ch,source_h_tag=tag,capture_rxpos=req.capture_end)
            assert wave["source_tach_byte_normalization_divisor"]==255
        else:
            result=provisional_spectrum(window.preview,ch,n_fft=1024,full_bins=True)
            assert bind_live_spectrum_view(window.preview,ch,result,selected_n=1024,code=0,mode=1)["unit"]==""
