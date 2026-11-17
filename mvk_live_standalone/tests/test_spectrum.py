import numpy as np
import pytest
from mvk_live_standalone.spectrum import (
    FFT_SIZES, calculate_spectrum, plot_values, y_axis_label,
)


@pytest.mark.parametrize("kind,expected", [
    ("acceleration", 2.0),
    ("velocity", 2.0 / (2*np.pi*128) * 1000.0),
    ("displacement", 2.0 / (2*np.pi*128)**2 * 1_000_000.0),
])
def test_128_hz_calibrated_sine_has_correct_rms_and_units(kind, expected):
    fs=8192
    n=8192
    t=np.arange(n)/fs
    x=2*np.sqrt(2)*np.sin(2*np.pi*128*t)  # 2 m/s² RMS
    spec=calculate_spectrum(x, fs, kind=kind, nfft=n)
    f,peak=spec.peak
    assert f==128
    assert peak==pytest.approx(expected,rel=0.015)


def test_y_axis_log_does_not_change_physical_units_or_values():
    s=calculate_spectrum(np.sin(2*np.pi*128*np.arange(8192)/8192),8192,nfft=8192,kind="velocity")
    assert y_axis_label("velocity","linear")=="ВС · Виброскорость, мм/с СКЗ"
    assert "дБ (отн. 1×10⁻⁶ мм/с СКЗ)" in y_axis_label("velocity","log")
    assert "дБ (отн. 1×10⁻⁶ мм/с" in y_axis_label("velocity","db")
    pos=s.rms>0
    assert np.allclose(plot_values(s,"log")[pos],plot_values(s,"db")[pos])
    p=plot_values(s,"db")
    assert p[np.argmax(s.rms)]==pytest.approx(20*np.log10(s.rms.max()/1e-6))


def test_bandpass_filters_outside_signal_in_real_waveform():
    fs=8192
    t=np.arange(16384)/fs
    x=np.sin(2*np.pi*100*t)+np.sin(2*np.pi*1500*t)
    s=calculate_spectrum(x,fs,nfft=16384,band_hz=(10.0,200.0))
    f=s.hz
    assert s.rms[np.argmin(abs(f-100))]>20*s.rms[np.argmin(abs(f-1500))]


def test_no_padding_untrusted_calibration_or_invalid_fft():
    with pytest.raises(ValueError,match="Need N"):
        calculate_spectrum(np.ones(100), 8192, nfft=8192)
    with pytest.raises(ValueError,match="FFT size"):
        calculate_spectrum(np.ones(8192), 8192, nfft=1024)
    with pytest.raises(ValueError,match="Need N"):
        calculate_spectrum(np.full(8192,np.nan),8192,nfft=8192)


def test_log_zero_floor_and_correct_displacement_label():
    assert "дБ (отн. 1×10⁻⁶ мкм" in y_axis_label("displacement","log")
    s=calculate_spectrum(np.zeros(8192),8192,nfft=8192)
    assert np.all(plot_values(s,"log")==-180.0)
    assert np.all(plot_values(s,"db")==-180.0)


def test_smooth_bins_validation_and_sizes():
    assert 262144 in FFT_SIZES
    with pytest.raises(ValueError,match="Smoothing"):
        calculate_spectrum(np.ones(8192),8192,nfft=8192,smooth_bins=2)

def test_iso1683_db_references_and_custom_unit_option():
    from mvk_live_standalone.spectrum import db_reference, db_reference_text
    for kind in ("acceleration","velocity","displacement"):
        assert db_reference(kind,"iso")==pytest.approx(1e-6)
        assert db_reference(kind,"unit")==pytest.approx(1.0)
        assert "1×10⁻⁶" in db_reference_text(kind,"iso")
    x=2*np.sqrt(2)*np.sin(2*np.pi*128*np.arange(8192)/8192)
    s=calculate_spectrum(x,8192,nfft=8192)
    line=int(np.argmax(s.rms))
    assert plot_values(s,"db")[line]==pytest.approx(20*np.log10(s.rms[line]/1e-6))
    assert plot_values(s,"db",reference="unit")[line]==pytest.approx(20*np.log10(s.rms[line]))
    assert "отн. 1 м/с²" in y_axis_label("acceleration","db","unit")


def test_log_is_db_not_second_graphical_logarithm():
    x=np.sin(2*np.pi*64*np.arange(8192)/8192)
    s=calculate_spectrum(x,8192,nfft=8192,kind="velocity")
    np.testing.assert_allclose(plot_values(s,"log"),plot_values(s,"db"))
    assert np.nanmax(plot_values(s,"db")) > 0
