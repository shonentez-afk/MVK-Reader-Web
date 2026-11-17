"""Scientific regression against known calibrated mechanical vibration."""
import numpy as np
import pytest

from mvk_live_standalone.vibration import (
    analyze_vibration, bearing_frequency_markers, time_features,
    vibration_y_label, vibration_plot_values,
)


def _sine(rms=2.0, freq=128.0, fs=8192, n=32768):
    t=np.arange(n)/fs
    return rms*np.sqrt(2)*np.sin(2*np.pi*freq*t)


def test_welch_psd_and_octave_are_broadband_rms_integrals_not_fft_line_amplitudes():
    x=_sine()
    w=analyze_vibration(x,8192,mode="welch",nfft=8192)
    assert w.units=="(м/с²)²/Гц"
    assert w.segments>=4
    assert w.peak[0]==pytest.approx(128,abs=.1)
    measured=np.sqrt(np.sum(w.rms)*(8192/8192))
    assert measured==pytest.approx(2.0,rel=.015)
    octave=analyze_vibration(x,8192,mode="third_octave",nfft=8192)
    i=int(np.argmin(abs(octave.hz-125)))
    assert octave.rms[i]==pytest.approx(2.0,rel=.02)
    assert np.isnan(octave.rms[0])
    assert "1/3 октавы" in vibration_y_label(octave,"linear")


def test_velocity_and_displacement_psd_frequency_domain_conversion():
    x=_sine()
    acc=analyze_vibration(x,8192,mode="welch",nfft=8192)
    vs=analyze_vibration(x,8192,kind="velocity",mode="welch",nfft=8192)
    vp=analyze_vibration(x,8192,kind="displacement",mode="welch",nfft=8192)
    i=int(np.argmax(acc.rms))
    assert vs.rms[i]/acc.rms[i] == pytest.approx((1000/(2*np.pi*128))**2, rel=1e-4)
    assert vp.rms[i]/acc.rms[i] == pytest.approx((1e6/(2*np.pi*128)**2)**2, rel=1e-4)
    assert vs.units=="(мм/с)²/Гц"
    assert vp.units=="(мкм)²/Гц"
    assert np.isfinite(vs.rms).all()


def test_hilbert_resonance_envelope_recovers_50_hz_fault_modulation():
    fs=8192
    n=32768
    t=np.arange(n)/fs
    x=(1+0.5*np.sin(2*np.pi*50*t))*np.sin(2*np.pi*2048*t)
    envelope=analyze_vibration(x,fs,mode="envelope",nfft=8192,
                               envelope_band_hz=(1800.0,2300.0))
    assert envelope.peak[0]==pytest.approx(50,abs=1)
    assert envelope.peak[1]==pytest.approx(0.5/np.sqrt(2),rel=.09)
    assert envelope.units=="м/с²"
    with pytest.raises(ValueError,match="VU"):
        analyze_vibration(x,fs,kind="velocity",mode="envelope",nfft=8192)
    with pytest.raises(ValueError,match="Nyquist"):
        analyze_vibration(x,fs,mode="envelope",nfft=8192,
                          envelope_band_hz=(3000,5000))


def test_welch_psd_db_is_10log_not_20log_and_fft_line_db_is_20log():
    x=_sine()
    w=analyze_vibration(x,8192,mode="welch",nfft=8192)
    db=vibration_plot_values(w,"db",reference="unit")
    i=int(np.argmax(w.rms))
    assert db[i]==pytest.approx(10*np.log10(w.rms[i]))
    assert "(1 м/с²)²/Гц" in vibration_y_label(w,"db","unit")
    fft=analyze_vibration(x,8192,mode="fft",nfft=8192)
    log=vibration_plot_values(fft,"log",reference="unit")
    i=int(np.argmax(fft.rms))
    assert log[i]==pytest.approx(20*np.log10(fft.rms[i]))
    np.testing.assert_array_equal(log,vibration_plot_values(fft,"db",reference="unit"))


def test_time_features_crest_factor_kurtosis_and_zero_signal():
    s=_sine()
    features=time_features(s,8192)
    assert features.acceleration_rms==pytest.approx(2.0,rel=.001)
    assert features.acceleration_crest_factor==pytest.approx(np.sqrt(2),rel=.001)
    assert features.acceleration_kurtosis==pytest.approx(1.5,rel=.001)
    quiet=time_features(np.zeros(500),8192)
    assert quiet.acceleration_rms==0.0 and quiet.acceleration_crest_factor==0.0


def test_bearing_markers_do_not_invent_missing_tach_or_geometry():
    marks=bearing_frequency_markers(1800)
    assert marks["1X"]==30 and marks["5X"]==150 and "BPFO" not in marks
    marks=bearing_frequency_markers(1800,balls=8,ball_diameter_mm=8,pitch_diameter_mm=40)
    assert marks["BPFO"]==pytest.approx(96)
    assert marks["BPFI"]==pytest.approx(144)
    assert marks["BSF"]==pytest.approx(72)
    assert marks["FTF"]==pytest.approx(12)
    with pytest.raises(ValueError,match="geometry"):
        bearing_frequency_markers(1800,balls=8)
    with pytest.raises(ValueError,match="RPM"):
        bearing_frequency_markers(0)


def test_reject_false_low_frequency_psd_without_imaginary_data():
    x=_sine()
    v=analyze_vibration(x,8192,kind="velocity",mode="welch",nfft=8192)
    assert v.floor_hz==pytest.approx(2)
    assert v.rms[0]==0 and v.rms[1]==0
    with pytest.raises(ValueError,match="Need real contiguous"):
        analyze_vibration(x[:32],8192,mode="welch",nfft=8192)


def test_optional_notch_is_never_implicit_and_preserves_other_orders():
    fs=8192
    t=np.arange(32768)/fs
    x=np.sin(2*np.pi*50*t)+np.sin(2*np.pi*128*t)
    normal=analyze_vibration(x,fs,nfft=8192,mode="fft")
    filtered=analyze_vibration(x,fs,nfft=8192,mode="fft",notch_hz=50.0)
    i50=int(np.argmin(abs(normal.hz-50)))
    i128=int(np.argmin(abs(normal.hz-128)))
    assert filtered.rms[i50] < normal.rms[i50]*0.05
    assert filtered.rms[i128]==pytest.approx(normal.rms[i128],rel=.01)
    with pytest.raises(ValueError,match="Nyquist"):
        analyze_vibration(x,fs,nfft=8192,notch_hz=5000)
