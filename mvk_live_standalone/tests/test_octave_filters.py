"""Local octave menu: nominal selection, real passbands, no native DSP."""
import numpy as np
import pytest

from mvk_live_standalone.octave_filters import (
    FAMILIES, nominal_centres, preset_band, preset_description,
)
from mvk_live_standalone.spectrum_controls import FILTER_CHOICES
from mvk_live_standalone.time_controls import TIME_FILTERS, time_filter_waveform


def test_explicit_octave_families_and_nominal_band_lists():
    assert {key for _,key in FILTER_CHOICES}.issuperset(FAMILIES)
    assert {key for _,key in TIME_FILTERS}.issuperset(FAMILIES)
    assert len(nominal_centres("third_octave"))==43
    assert 100. in nominal_centres("octave") or 125. in nominal_centres("octave")
    assert 1000. in nominal_centres("third_octave")
    assert 1000. in nominal_centres("octave")
    a,b=preset_band("third_octave",1000.)
    assert a==pytest.approx(1000/10**.05,rel=.01)
    assert b==pytest.approx(1000*10**.05,rel=.01)
    a,b=preset_band("octave",1000.)
    assert a<750 and b>1300
    assert "локальный фильтр" in preset_description("octave",1000.)
    assert "1/3" in preset_description("third_octave",1000.)


def test_preset_filter_is_physically_selective_and_independent_of_frange():
    fs=8192
    t=np.arange(16384)/fs
    x=(np.sqrt(2)*np.sin(2*np.pi*125*t)
       +np.sqrt(2)*np.sin(2*np.pi*1000*t))
    narrow=time_filter_waveform(x,fs,mode="third_octave",center=125.)
    high=time_filter_waveform(x,fs,mode="octave",center=1000.)
    assert np.std(narrow)<np.std(x)*.8
    assert np.std(high)<np.std(x)*.8
    assert np.dot(narrow,np.sin(2*np.pi*125*t))/len(t) > .5
    assert np.dot(high,np.sin(2*np.pi*1000*t))/len(t) > .5
    np.testing.assert_allclose(time_filter_waveform(x,fs,mode="none"),x)


def test_invalid_band_or_nyquist_is_rejected_not_silently_clamped():
    with pytest.raises(ValueError,match="списка"):
        preset_band("third_octave",123.456)
    with pytest.raises(ValueError,match="Nyquist"):
        preset_band("octave",4000.,fs=8192)
    with pytest.raises(ValueError,match="Nyquist"):
        time_filter_waveform(np.ones(8192),8192,mode="octave",center=4000.)
    with pytest.raises(ValueError,match="трёх периодов"):
        time_filter_waveform(np.ones(64),8192,mode="third_octave",center=1.)

def test_octave_rss_from_original_thirds_provenance_and_missing_values():
    import numpy as np
    from mvk_live_standalone.octave_filters import octave_rss_from_thirds
    from mvk_live_standalone.original_dsp import _THIRD_HZ
    v=np.ones(43)
    centers,sums=octave_rss_from_thirds(_THIRD_HZ,v)
    assert len(centers)==14
    assert np.allclose(sums,np.sqrt(3))
    v[2]=np.nan
    _,sums=octave_rss_from_thirds(_THIRD_HZ,v)
    assert np.isnan(sums[0])
    assert np.isfinite(sums[1])
