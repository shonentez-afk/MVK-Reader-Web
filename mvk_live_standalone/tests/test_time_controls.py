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



def test_scope_render_min_max_keeps_true_times_and_never_invents_an_impulse():
    from mvk_live_standalone.time_controls import time_plot_extrema
    fs=8192
    raw=np.zeros(32768,dtype=np.float64)
    # Max appears BEFORE min in the same decimation bucket.
    raw[1000]=+4.25
    raw[1001]=-3.75
    raw[32767]=+0.125
    x,y=time_plot_extrema(raw,fs,max_points=1002)
    assert len(x)<=1002
    assert np.all(np.diff(x)>0)
    indices=np.rint(x*fs+len(raw)).astype(int)
    np.testing.assert_array_equal(y,raw[indices])
    assert [1000,1001]==[i for i in indices if i in (1000,1001)]
    assert y[np.where(indices==1000)[0][0]]==4.25
    assert y[np.where(indices==1001)[0][0]]==-3.75
    assert indices[0]==0 and indices[-1]==len(raw)-1
    with pytest.raises(ValueError):
        time_plot_extrema(np.array([np.nan]),fs)


def test_scope_healthy_metric_math_separates_dc_and_ac_rms():
    from mvk_live_standalone.time_controls import (
        summarize_time_window,display_time_stats)
    x=np.array([4.,2.,4.,2.])
    m=summarize_time_window(x,8192)
    assert m.samples==4 and m.duration_s==pytest.approx(4/8192)
    assert m.mean_m_s2==pytest.approx(3.)
    assert m.rms_ac_m_s2==pytest.approx(1.)
    assert m.rms_total_m_s2==pytest.approx(np.sqrt(10))
    assert m.maximum_m_s2==4 and m.minimum_m_s2==2
    assert m.absolute_peak_m_s2==4 and m.peak_to_peak_m_s2==2
    assert m.crest_ac==pytest.approx(1.)
    assert display_time_stats(x,8192)==pytest.approx((1.,4.,2.))
    constant=summarize_time_window(np.full(20,5.),8192)
    assert constant.rms_ac_m_s2==0 and constant.rms_total_m_s2==5
    assert constant.crest_ac is None
    with pytest.raises(ValueError):
        summarize_time_window(np.array([1.,np.nan]),8192)
