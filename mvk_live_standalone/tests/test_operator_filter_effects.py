"""Real vibration filter behavior: selected bounds change FFT, not only text."""
import numpy as np
import pytest

from mvk_live_standalone.vibration import analyze_vibration


def test_lowpass_highpass_bandpass_change_real_spectral_components():
    fs=8192
    nfft=8192
    t=np.arange(nfft,dtype=np.float64)/fs
    # Both tones have physically defined amplitude = 1 m/s² RMS.
    x=np.sqrt(2)*(np.sin(2*np.pi*100*t)+np.sin(2*np.pi*1000*t))
    def power(band):
        view=analyze_vibration(
            x,fs,kind="acceleration",mode="fft",nfft=nfft,
            band_hz=band,smooth_bins=1,notch_hz=None)
        lo=view.rms[np.argmin(abs(view.hz-100))]
        hi=view.rms[np.argmin(abs(view.hz-1000))]
        return lo,hi

    none=power((0,None))
    assert none[0]==pytest.approx(1,rel=.002)
    assert none[1]==pytest.approx(1,rel=.002)
    lowpass=power((0,200))
    assert lowpass[0]==pytest.approx(1,rel=.03)
    assert lowpass[1]<.01
    highpass=power((500,None))
    assert highpass[0]<.01
    assert highpass[1]==pytest.approx(1,rel=.03)
    bandpass=power((500,1500))
    assert bandpass[0]<.01
    assert bandpass[1]==pytest.approx(1,rel=.03)


def test_filter_edges_cannot_exceed_actual_adc_nyquist():
    t=np.arange(8192)/512
    x=np.sin(2*np.pi*100*t)
    with pytest.raises(ValueError,match="Nyquist"):
        analyze_vibration(x,512,kind="acceleration",mode="fft",
                          nfft=8192,band_hz=(0,1000))
    with pytest.raises(ValueError,match="Nyquist"):
        analyze_vibration(x,512,kind="acceleration",mode="fft",
                          nfft=8192,band_hz=(256,None))
