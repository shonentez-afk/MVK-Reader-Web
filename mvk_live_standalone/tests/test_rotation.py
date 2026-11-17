"""1× is proposed ONLY from a calibrated velocity FFT; no TACH access."""
import numpy as np
import pytest

from mvk_live_standalone.rotation import estimate_rotation_from_velocity


def test_manual_confirmation_candidate_is_first_velocity_order_not_strongest_2x():
    fs=8192
    t=np.arange(32768)/fs
    # Input is calibrated ACCELERATION; combine physical velocity harmonics.
    v1=2*np.sqrt(2)*np.sin(2*np.pi*25*t)
    v2=4*np.sqrt(2)*np.sin(2*np.pi*50*t)
    v3=.7*np.sqrt(2)*np.sin(2*np.pi*75*t)
    acc=np.gradient((v1+v2+v3)/1000,1/fs)
    candidate=estimate_rotation_from_velocity(acc,fs,nfft=32768)
    assert candidate.hz==pytest.approx(25,abs=.15)
    assert candidate.rpm==pytest.approx(1500,abs=9)
    assert 2 in candidate.harmonic_hits and 3 in candidate.harmonic_hits
    assert candidate.source=="VELOCITY_FFT_PROPOSAL_NO_TACH"
    assert "подтвердите" in candidate.description


def test_pure_velocity_sine_is_only_a_proposal_not_device_rpm():
    fs=8192
    t=np.arange(32768)/fs
    x=np.sqrt(2)*np.sin(2*np.pi*100*t)
    v=estimate_rotation_from_velocity(x,fs,nfft=32768)
    assert v.hz==pytest.approx(100,abs=.3)
    assert v.confidence != ""
    assert "TACH" in v.description


def test_absent_and_unresolved_speed_rejected():
    with pytest.raises(ValueError):
        estimate_rotation_from_velocity(np.zeros(32768),8192)
    with pytest.raises(ValueError):
        estimate_rotation_from_velocity(np.ones(32),8192,nfft=32768)
    with pytest.raises(ValueError,match="RPM"):
        estimate_rotation_from_velocity(np.ones(32768),8192,
                                        min_rpm=18000,max_rpm=300)
