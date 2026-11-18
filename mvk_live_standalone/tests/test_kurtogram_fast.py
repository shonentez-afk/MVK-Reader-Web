"""Numerical guardrails for VENDORED PySDKit Fast Kurtogram.

The upstream algorithm is run by tests, not a local dyadic approximation.
"""
import numpy as np
import pytest
from mvk_live_standalone.kurtogram import compute_fast_kurtogram
from mvk_live_standalone._pysdkit_kurtogram import (
    fast_kurtogram, find_wav_kurt, analytic_filters, kurt)


def test_vendor_filter_tree_and_no_fake_calibration():
    a,b,c,d,e=analytic_filters()
    assert [len(x) for x in (a,b,c,d,e)]==[17,16,25,25,25]
    assert kurt(np.zeros(32),opt="kurt2")==0.0
    fs=8192
    rng=np.random.default_rng(411)
    t=np.arange(8192)/fs
    x=(0.18*rng.normal(size=8192)+np.sin(2*np.pi*700*t)).astype("<f4")
    result=compute_fast_kurtogram(x,fs,nlevel=4)
    upstream,info=fast_kurtogram(x,4,fs=fs)
    np.testing.assert_array_equal(result.scores,upstream)
    assert result.scores.shape==(8,48)
    assert len(result.levels)==8 and len(result.frequencies_hz)==48
    assert result.fs==fs and result.n_samples==len(x)
    assert result.best_center_hz==pytest.approx(info["fc"])
    assert result.best_bandwidth_hz==pytest.approx(info["bw"])
    lo,hi,fc,bw,score=result.best_band()
    assert 0<lo<hi<fs/2
    assert fc==pytest.approx(result.best_center_hz)
    assert bw==pytest.approx(result.best_bandwidth_hz)
    assert score==pytest.approx(result.best_score)
    assert np.isfinite(result.scores).all()
    # The actual PySDKit packet-path demodulation is available without
    # importing Matplotlib or the full PySDKit package.
    envelope=find_wav_kurt(np.asarray(info["x"]),info["level"],
                           info["fc"]/fs,fs=fs,filters=info["filters"])
    assert len(envelope["c"])>0 and np.isfinite(envelope["c"]).all()


def test_no_silent_invalid_adc_or_impossible_decomposition():
    x=np.random.default_rng(7).normal(size=4096)
    for arr,fs,nlevel in [(x,0,3),(x[:1000],8192,3),
                           (np.zeros_like(x),8192,3),
                           (np.full_like(x,np.nan),8192,3),
                           (x,8192,6),(x,8192,0)]:
        with pytest.raises(ValueError):
            compute_fast_kurtogram(arr,fs,nlevel=nlevel)
    result=compute_fast_kurtogram(x,8192,nlevel=3)
    assert result.scores.shape==(6,24)
    with pytest.raises(ValueError):
        result.cell_band(-1,1)
    with pytest.raises(ValueError):
        result.cell_band(0,999)


def test_auto_envelope_uses_genuine_pysdkit_not_legacy_approximation():
    from mvk_live_standalone.pipeline import analyze_live
    fs=8192
    n=8192
    rng=np.random.default_rng(31)
    x=rng.normal(0.,.02,size=n)
    x[::143]+=4.0
    result=analyze_live(
        x,fs,kind="acceleration",mode="envelope",nfft=n,
        band_hz=(0.,None),smooth_bins=1,envelope_band="auto",
        notch_hz=None)
    assert result.view.mode=="envelope"
    assert result.auto_envelope is not None
    assert result.auto_envelope.method=="PYSDKIT_FAST_KURTOGRAM_ANTONI_2007"
    assert "не доказательство" in result.auto_envelope.confidence
    assert 0<result.auto_envelope.low_hz<result.auto_envelope.high_hz<fs/2


def test_clicking_duplicate_raster_cells_selects_same_real_packet_node():
    rng=np.random.default_rng(59)
    x=rng.normal(size=8192)
    view=compute_fast_kurtogram(x,8192,nlevel=4)
    # 48 heatmap columns but only one wide packet at k=0,
    # two packets at k=1, three at k=log2(3) and so forth.
    for col in (0,1,13,47):
        assert view.cell_band(0,col)[:4]==pytest.approx(view.cell_band(0,0)[:4])
    for col in (0,1,12,23):
        assert view.cell_band(1,col)[:4]==pytest.approx(view.cell_band(1,0)[:4])
    assert view.cell_band(1,24)[2]!=view.cell_band(1,0)[2]
    assert view.cell_band(2,15)[2]==pytest.approx(view.cell_band(2,0)[2])
    assert view.cell_band(2,16)[2]!=view.cell_band(2,0)[2]
