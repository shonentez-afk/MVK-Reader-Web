"""Original MVK AUX4700 source never confused with app-derived spectra."""
import numpy as np
import pytest

from mvk_live_standalone.original_dsp import read_original_dsp_bands


def _status():
    freqs=list(np.geomspace(.63,10000,43))
    return {
        "phase":"RECORDING","aux4700_updates":7,
        "dsp_original_aux4700_channels":[{
            "adc":3,"time_utc":"2026-11-17T12:00:00Z","update":7,
            "third_octave_hz":freqs,
            "third_octave_acceleration_rms":[0.01*i for i in range(43)],
            "status_hex":"0x00000000","nonfinite_fields":0,
        }],
    }


def test_original_dsp_43_bands_are_only_read_from_native_aux():
    status=_status()
    assert read_original_dsp_bands(status,1) is None
    original=read_original_dsp_bands(status,3)
    assert original.source=="MVK_DSP_ORIGINAL_AUX4700"
    assert original.update==7
    assert original.frequency_hz.size==43
    assert original.acceleration_rms[10]==pytest.approx(.1)
    assert original.status_hex=="0x00000000"


def test_original_dsp_rejects_fabricated_or_incomplete_dsp():
    status=_status()
    status["aux4700_updates"]=0
    with pytest.raises(ValueError,match="tick"):
        read_original_dsp_bands(status,3)
    status=_status()
    status["dsp_original_aux4700_channels"][0]["third_octave_acceleration_rms"]=[0.1]
    with pytest.raises(ValueError,match="shape"):
        read_original_dsp_bands(status,3)
    status=_status()
    status["dsp_original_aux4700_channels"][0]["third_octave_acceleration_rms"][4]=None
    status["dsp_original_aux4700_channels"][0]["nonfinite_fields"]=1
    view=read_original_dsp_bands(status,3)
    assert np.isnan(view.acceleration_rms[4])
    status["dsp_original_aux4700_channels"][0]["nonfinite_fields"]=0
    with pytest.raises(ValueError,match="nonfinite"):
        read_original_dsp_bands(status,3)
