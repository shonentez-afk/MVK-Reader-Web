"""Synthetic regression of the source FRange receipt and FFT preparation."""
import struct
import numpy as np
import pytest
from mvk_compatible.core.original_source_ring_receipt import (
    validate_source_range_state,source_live_range_matches,SOURCE_CONFIG_ADC_DOMAIN,
)
from mvk_compatible.core.storage_f_range_idr_candidate import prepare_original_fft_input,DOMAIN_ORIGINAL_STORAGE
from mvk_compatible.core.original_adc_view_controls import source_live_adc_vertical_view

def state(scale=2.5,channel=1):
    return dict(single=scale,origin="REGISTER_FLOAT32",register_word=0x100*channel+0x0e,
        register_raw_le=struct.pack("<f",scale).hex(),units_raw_le="",
        latched_frame=4,socket_attempt=1,usable=True)

def test_config_single_and_epoch():
    s=state()
    assert validate_source_range_state(s,1)==s
    row=dict(input_domain=SOURCE_CONFIG_ADC_DOMAIN,original_live_f_range_single=2.5,source_range_state=s)
    assert source_live_range_matches(row,SOURCE_CONFIG_ADC_DOMAIN,2.5,s)
    assert not source_live_range_matches(row,SOURCE_CONFIG_ADC_DOMAIN,2.5,dict(s,latched_frame=5))
    with pytest.raises(ValueError):validate_source_range_state(dict(s,single=1.0),1)
    with pytest.raises(ValueError):validate_source_range_state(s,2)

def test_original_storage_normalized_once_and_vertical_uses_factor():
    raw=np.array([1.,-2.,0.5,0.],dtype=np.float32)
    ring=(raw.astype(np.float64)*2.5).astype(np.float32)
    out=prepare_original_fft_input(ring,f_range=2.5,input_domain=DOMAIN_ORIGINAL_STORAGE)
    np.testing.assert_array_equal(out["samples_before_dc_removal"],raw)
    model=source_live_adc_vertical_view(full_peak=5.,tag=0,source_frange1=False,source_f_range=2.5)
    assert model["source_f_range_verified"]
    assert not model["source_f_range1_verified"]

def test_close_config_reads_latest_not_live_latch_and_respects_freeze_caller():
    from mvk_compatible.core.original_mode2_close_metadata import CloseConfigReplay
    c=CloseConfigReplay()
    raw=struct.pack("<f",2.5)+b"m/s2".ljust(32,b"\x00")
    c.put([(0x10e,18,raw)])
    first=c.snapshot(1,5)
    assert first["gain"]==2.5 and first["units"]=="m/s2"
    c.put([(0x10e,2,struct.pack("<f",4.0))])
    second=c.snapshot(1,10)
    assert second["gain"]==4 and first["gain"]==2.5
    assert second["units"]=="m/s2"
    assert c.snapshot(2,10)["gain"] is None
    assert c.snapshot(9,10)["units"]=="Count"
    c.put([(0x10e,2,struct.pack("<f",0))])
    assert c.snapshot(1,11)["gain_origin"]=="REGISTER_ZERO_FALLBACK_ONE"

def test_close_sidecar_uses_verified_values_not_one(tmp_path):
    from hashlib import sha256
    from mvk_compatible.core.original_mode2_close_metadata import CloseConfigReplay
    from mvk_compatible.core.original_mode2_source_files import write_verified_source_tsxml_sidecars
    from mvk_compatible.core.original_tsxml_contract import inspect_original_tsxml
    name="SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin"
    raw=struct.pack("<f",0.125)*8
    (tmp_path/name).write_bytes(raw)
    c=CloseConfigReplay()
    c.put([(0x10e,18,struct.pack("<f",3.25)+b"m/s2".ljust(32,b"\x00"))])
    proof=dict(source_raw_sha256="a"*64,verified_channel_files=[dict(
        name=name,bytes=len(raw),channel=1,window=1,
        sha256=sha256(raw).hexdigest(),verified_packet_rates_hz=[65536],
        source_close_config=c.snapshot(1,20))])
    result=write_verified_source_tsxml_sidecars(tmp_path,live_proof=proof,
        source_run_end_utc="2026-11-24T10:00:00Z")[0]
    assert result["close_register_values_verified"]
    xml=inspect_original_tsxml((tmp_path/(name+".tsxml")).read_bytes(),
        actual_bin_filename=name)
    assert xml.internal_gain_single==3.25 and xml.channel_units_text=="m/s2"
    assert (tmp_path/name).read_bytes()==raw

def test_units_are_channel_scoped_not_fixed_acceleration():
    from mvk_compatible.core.original_source_ring_receipt import source_live_units_text
    from mvk_compatible.core.original_adc_view_controls import original_adc_vertical_physical_caption
    s=state()
    s["units_raw_le"]=b"V".ljust(32,b"\x00").hex()
    assert source_live_units_text(s)=="V"
    assert original_adc_vertical_physical_caption(0,10,units="V")=="10 V"
    s["units_raw_le"]=bytes([0xCC,0x00]+[0]*30).hex()
    assert source_live_units_text(s) is None
