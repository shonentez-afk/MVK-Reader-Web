"""Synthetic mathematical tests only; no external reference measurement."""
import numpy as np
import pytest

from mvk_live_standalone.advanced import (
    extended_time_features, broadband_rms, select_envelope_band,
    envelope_fault_lines, stft_vibration, cwt_morlet_vibration, real_cepstrum,
)
from mvk_live_standalone.vibration import analyze_vibration


def test_extended_time_features_have_correct_units_and_zero_safety():
    t=np.arange(8192)/8192
    x=2*np.sqrt(2)*np.sin(2*np.pi*128*t)
    f=extended_time_features(x)
    assert f.rms_m_s2==pytest.approx(2,rel=.001)
    assert f.peak_to_peak_m_s2==pytest.approx(4*np.sqrt(2),rel=.001)
    assert f.crest_factor==pytest.approx(np.sqrt(2),rel=.001)
    assert f.kurtosis_pearson==pytest.approx(1.5,rel=.001)
    assert f.shape_factor>1
    quiet=extended_time_features(np.zeros(8192))
    assert quiet.rms_m_s2==0 and quiet.clearance_factor==0


def test_true_band_rms_is_integrated_density_not_max_fft_line():
    fs=8192
    t=np.arange(32768)/fs
    velocity=1.7*np.sqrt(2)*np.sin(2*np.pi*128*t)/1000
    acceleration=np.gradient(velocity,1/fs)
    band=broadband_rms(acceleration,fs,kind="velocity",
                       band_hz=(10,1000),nfft=8192)
    assert band.valid and band.unit=="мм/с"
    assert band.rms==pytest.approx(1.7,rel=.04)
    too_narrow=broadband_rms(acceleration,fs,kind="velocity",
                            band_hz=(10,10.5),nfft=8192)
    assert not too_narrow.valid and np.isnan(too_narrow.rms)
    with pytest.raises(ValueError,match="Nyquist"):
        broadband_rms(acceleration,fs,band_hz=(10,5000))


def test_bounded_kurtogram_like_band_scan_never_needs_tachometer():
    fs=8192
    x=np.zeros(32768,dtype=float)
    duration=np.arange(180)/fs
    pulse=np.sin(2*np.pi*1700*duration)*np.exp(-duration*600)
    for pos in range(400,len(x)-180,fs//52):
        x[pos:pos+180]+=pulse
    band=select_envelope_band(x,fs,max_level=4)
    assert 300<=band.low_hz<band.high_hz<fs/2
    assert band.tested_bands>=3
    assert np.isfinite(band.envelope_kurtosis)
    assert band.method=="KURTOGRAM_LIKE_ENVELOPE_KURTOSIS_FILTER_BANK"
    with pytest.raises(ValueError):
        select_envelope_band(x[:512],fs)


def test_bearing_lines_local_snr_no_external_baseline():
    fs=8192
    t=np.arange(32768)/fs
    # At 1800 RPM, 8 balls, 8/40 diameters: BPFO=96 Hz.
    x=(1+.6*np.sin(2*np.pi*96*t))*np.sin(2*np.pi*2048*t)
    v=analyze_vibration(x,fs,mode="envelope",nfft=8192,
                        envelope_band_hz=(1800,2300))
    lines=envelope_fault_lines(v,1800,balls=8,
                    ball_diameter_mm=8,pitch_diameter_mm=40)
    bpfo=next(d for d in lines if d.label=="BPFO")
    assert bpfo.expected_hz==pytest.approx(96)
    assert bpfo.snr_db>6
    assert bpfo.noteworthy and bpfo.harmonics_found>=1
    assert all(l.label in ("BPFO","BPFI","BSF","FTF") for l in lines)
    with pytest.raises(ValueError,match="envelope"):
        envelope_fault_lines(analyze_vibration(x,fs,nfft=8192),1800,
                            balls=8,ball_diameter_mm=8,pitch_diameter_mm=40)


def test_stft_cwt_and_cepstrum_shapes_are_bounded_and_labeled():
    fs=4096
    t=np.arange(8192)/fs
    x=np.sin(2*np.pi*512*t)+.2*np.sin(2*np.pi*256*t)
    stft=stft_vibration(x,fs,nperseg=1024,max_frequency_hz=1000)
    assert stft.magnitude.shape==(len(stft.frequency_hz),len(stft.time_s))
    assert stft.magnitude.shape[0]<=256 and stft.magnitude.shape[1]<=128
    assert stft.calibrated_amplitude
    cwt=cwt_morlet_vibration(x,fs,min_frequency_hz=150,
                              max_frequency_hz=1000,scales=24)
    assert cwt.magnitude.shape==(24,len(cwt.time_s))
    assert not cwt.calibrated_amplitude
    assert cwt.frequency_hz[0]>=150 and cwt.frequency_hz[-1]<=1000
    cep=real_cepstrum(x,fs,max_quefrency_s=.04)
    assert cep.quefrency_s.shape==cep.magnitude.shape
    assert np.isfinite(cep.magnitude).all()



def test_operator_gear_mesh_harmonics_and_sidebands_without_tach():
    from mvk_live_standalone.advanced import gear_mesh_markers
    m=gear_mesh_markers(1500,32)
    assert m.mesh_hz==800
    assert m.harmonics_hz==(800,1600,2400)
    assert m.sidebands_hz==(725,750,775,825,850,875)
    assert "NO_TACH" in m.source
    with pytest.raises(ValueError,match="teeth"):
        gear_mesh_markers(1500,0)


def test_historical_severity_requires_user_class_and_full_band():
    from mvk_live_standalone.advanced import indicative_iso10816_zone
    z=indicative_iso10816_zone(5.0,machine_class=2,rpm=1500)
    assert z.zone=="B"
    assert "INDICATIVE" in z.source
    with pytest.raises(ValueError,match="class"):
        indicative_iso10816_zone(5.0,machine_class=0,rpm=1500)
    with pytest.raises(ValueError,match="Full measured"):
        indicative_iso10816_zone(5.0,machine_class=2,rpm=1500,
                                measured_band_hz=(10,200))
