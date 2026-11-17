"""Original MVK AUX4700 source never confused with app-derived spectra."""
import numpy as np
import pytest

from mvk_live_standalone.original_dsp import read_original_dsp_bands


def _status():
    from mvk_live_standalone.original_dsp import _THIRD_HZ
    freqs=_THIRD_HZ.tolist()
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



def _complete_status():
    record=_status()
    data=record["dsp_original_aux4700_channels"][0]
    data["band_rms"]=[i*.1 for i in range(24)]
    data["band_peak_equiv"]=[i*.2 for i in range(24)]
    data["band_span_equiv"]=[i*.4 for i in range(24)]
    data["not_ready"]={"fs16":False,"fs64":False,"fs512":False}
    return record


def test_original_dsp_parses_all_115_transmitted_calculated_cells():
    status=_complete_status()
    original=read_original_dsp_bands(status,3)
    assert original.has_extended
    assert original.total_transmitted_cells==115
    assert original.acceleration_rms.size==43
    assert original.band_rms.size==24
    assert original.band_peak_equiv.size==24
    assert original.band_span_equiv.size==24
    assert original.band_rms[5]==pytest.approx(.5)
    assert original.band_peak_equiv[5]==pytest.approx(1.0)
    assert original.band_span_equiv[5]==pytest.approx(2.0)
    assert original.source=="MVK_DSP_ORIGINAL_AUX4700"


def test_original_dsp_never_invents_missing_24_slot_fields():
    old=_status()
    original=read_original_dsp_bands(old,3)
    assert not original.has_extended
    assert original.total_transmitted_cells==43
    assert original.band_rms is None
    partial=_complete_status()
    del partial["dsp_original_aux4700_channels"][0]["band_peak_equiv"]
    with pytest.raises(ValueError,match="Partial"):
        read_original_dsp_bands(partial,3)


def test_original_dsp_extended_null_cells_are_unavailable_not_zero():
    status=_complete_status()
    c=status["dsp_original_aux4700_channels"][0]
    c["band_peak_equiv"][5]=None
    c["band_span_equiv"][7]=None
    c["nonfinite_fields"]=2
    c["not_ready"]["fs64"]=True
    o=read_original_dsp_bands(status,3)
    assert np.isnan(o.band_peak_equiv[5])
    assert np.isnan(o.band_span_equiv[7])
    assert o.not_ready==("fs64",)
    assert o.band_rms[0]==0
    c["nonfinite_fields"]=1
    with pytest.raises(ValueError,match="nonfinite"):
        read_original_dsp_bands(status,3)


def test_original_dsp_refuses_false_third_octave_axis_and_band_cell_types():
    status=_complete_status()
    c=status["dsp_original_aux4700_channels"][0]
    c["third_octave_hz"][10]=60.
    with pytest.raises(ValueError,match="centres"):
        read_original_dsp_bands(status,3)
    status=_complete_status()
    c=status["dsp_original_aux4700_channels"][0]
    c["band_span_equiv"][4]="0"
    with pytest.raises(ValueError,match="bad cell type"):
        read_original_dsp_bands(status,3)
