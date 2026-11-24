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
