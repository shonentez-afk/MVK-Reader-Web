"""Time signal X/Y and explicitly selected local filters, not a second gain."""
import numpy as np
import pytest

from mvk_live_standalone.time_controls import (
    TIME_WINDOWS_S, Y_ABSOLUTE_LIMITS_M_S2, TIME_FILTERS,
    time_filter_waveform, signed_time_limits, display_time_stats,
)


def test_time_x_ranges_span_10ms_to_30s_in_true_seconds():
    assert TIME_WINDOWS_S[0]==.01
    assert .1 in TIME_WINDOWS_S and 1. in TIME_WINDOWS_S
    assert TIME_WINDOWS_S[-1]==30.
    assert list(TIME_WINDOWS_S)==sorted(set(TIME_WINDOWS_S))
    assert Y_ABSOLUTE_LIMITS_M_S2[0]==.01


def test_time_y_is_symmetric_physical_acceleration_m_s2():
    assert signed_time_limits(np.array([-2.,1.]),None)==(-2.3,2.3)
    assert signed_time_limits(np.array([-2.,1.]),10)==(-10.,10.)
    assert signed_time_limits(np.array([]),None)==(-1e-9,1e-9)
    with pytest.raises(ValueError):
        signed_time_limits(np.array([0.]),0)


def test_time_filter_off_does_not_reapply_native_frange():
    original=np.asarray([3.25,-5.,1.],dtype=np.float32)
    np.testing.assert_allclose(
        time_filter_waveform(original,8192,mode="none"),
        original,rtol=0,atol=0)
    assert TIME_FILTERS[0]==("Без фильтра","none")
    assert not any("огибающ" in item[0].lower() for item in TIME_FILTERS)


def test_filtered_time_signal_changes_only_frequency_component_selected():
    fs=8192
    t=np.arange(32768)/fs
    raw=np.sqrt(2)*(np.sin(2*np.pi*50*t)+np.sin(2*np.pi*1000*t))
    def magnitude(arr,f):
        index=int(round(f*len(arr)/fs))
        return 2*np.abs(np.fft.rfft(arr)[index])/len(arr)/np.sqrt(2)
    hp=time_filter_waveform(raw,fs,mode="highpass",low=500)
    assert magnitude(hp,50)<.01 and magnitude(hp,1000)==pytest.approx(1,rel=.02)
    lp=time_filter_waveform(raw,fs,mode="lowpass",high=200)
    assert magnitude(lp,1000)<.01 and magnitude(lp,50)==pytest.approx(1,rel=.02)
    bp=time_filter_waveform(raw,fs,mode="bandpass",low=500,high=1500)
    assert magnitude(bp,50)<.01 and magnitude(bp,1000)==pytest.approx(1,rel=.02)
    notch=time_filter_waveform(raw,fs,mode="notch50")
    assert magnitude(notch,50)<.05 and magnitude(notch,1000)==pytest.approx(1,rel=.02)


def test_time_filter_refuses_above_nyquist_or_bad_order():
    raw=np.arange(256,dtype=np.float32)
    with pytest.raises(ValueError,match="Nyquist"):
        time_filter_waveform(raw,512,mode="lowpass",high=1000)
    with pytest.raises(ValueError,match="Nyquist"):
        time_filter_waveform(raw,512,mode="bandpass",low=200,high=400)
    with pytest.raises(ValueError):
        time_filter_waveform(raw,512,mode="bandpass",low=200,high=100)
    with pytest.raises(ValueError):
        time_filter_waveform(raw,512,mode="malformed")


def test_time_stats_are_local_and_true_peak_to_peak():
    r,p,pp=display_time_stats(np.asarray([2.,-3.,1.,-2.]),8192)
    assert r>0 and p==3 and pp==5
    with pytest.raises(ValueError):
        display_time_stats(np.asarray([1.]),8192)
