"""Stage111Z31N: source-accurate ordinary spectrum min/max columns.

Synthetic numerical arrays only. All N/2 bins, peak and summary must
remain unchanged even though only TRUNC((N/2)/1.28) are plotted.
"""
import numpy as np
import pytest
from mvk_compatible.core.spectrum_archive_plot_projection import (
    SOURCE,spectrum_archive_plot_projection,
)


def _make(mode=0,n=262144,fs=65536):
    y=np.full(n//2, -90. if mode==0 else 1.0,dtype="<f4")
    data_size=int((n//2)/1.28)
    peak_at=data_size//2+31
    y[peak_at]= -8. if mode==0 else 16.
    # Hidden original N/2 tail MUST NOT enter plot, but does enter
    # original numeric FFT and summary (kept elsewhere, no mutation).
    y[data_size+3]= 99. if mode==0 else 1e7
    lo,hi=(-100.,0.) if mode==0 else (0.,20.)
    return y,peak_at,dict(
        n_fft=n,sample_rate_hz=fs,
        view_x=(0.,fs/2/1.28),view_y=(lo,hi),
        pixel_width=800,pixel_height=420)


@pytest.mark.parametrize("mode",[0,1,2,3])
def test_all_four_modes_show_single_narrow_peak_without_trimming_bins(mode):
    y,peak_at,params=_make(mode)
    original_bits=y.view("<u4").copy()
    result=spectrum_archive_plot_projection(y,**params)
    assert result["source"]==SOURCE
    assert result["draw_mode"]=="original_pixel_column_minmax"
    assert result["full_fft_bins"]==131072
    assert result["source_series_bins"]==102400
    assert result["visible_bin_count"]>=102399
    assert result["source_column_count"]>500
    assert result["segments_count"]>500
    assert result["pairs_x_hz"].shape==(2*result["segments_count"],)
    assert result["pairs_y"].shape==result["pairs_x_hz"].shape
    peak_frequency=peak_at*(params["sample_rate_hz"]/params["n_fft"])
    peak_idx=int(np.argmax(result["pairs_y"]))
    # The source draws minmax at the containing pixel column, not
    # necessarily at an exact bin frequency when 100+ bins per px.
    assert abs(result["pairs_x_hz"][peak_idx]-peak_frequency)<(
        (params["view_x"][1]-params["view_x"][0])/params["pixel_width"]*3)
    assert float(result["pairs_y"][peak_idx])>=(
        -9. if mode==0 else 15.)
    assert float(np.max(result["pairs_y"]))<=(
        0. if mode==0 else 20.)
    assert not result["original_delphi_pixel_runtime_verified"]
    np.testing.assert_array_equal(y.view("<u4"),original_bits)


def test_zoomed_in_sparse_view_preserves_original_unsimplified_points():
    y,_,kwargs=_make()
    kwargs["view_x"]=(1800.,1820.)
    result=spectrum_archive_plot_projection(y,**kwargs)
    assert result["draw_mode"]=="original_samples_when_sparse"
    assert result["segments_count"]==0
    assert result["visible_bin_count"]<=80
    assert result["pairs_x_hz"].size==0
    assert result["pairs_y"].size==0


def test_last_unplotted_bins_never_leak_into_source_plot():
    y,_,kwargs=_make(mode=1)
    y[:102400]=1.
    y[102401]=np.float32(1e8)
    result=spectrum_archive_plot_projection(y,**kwargs)
    assert result["draw_mode"]=="original_pixel_column_minmax"
    assert max(result["pairs_y"])<20.


@pytest.mark.parametrize("wrong",[
    dict(pixel_width=1),dict(pixel_height=True),
    dict(view_x=(30.,30.)),dict(view_y=(-1.,float("nan"))),
    dict(n_fft=4096),dict(min_density=0),
])
def test_fails_closed_on_malformed_spectrum_or_plot(wrong):
    y,_,params=_make()
    params.update(wrong)
    with pytest.raises(ValueError):
        spectrum_archive_plot_projection(y,**params)


def test_proj_chooses_raw_when_spatial_density_is_below_threshold():
    y,_,kwargs=_make(n=1024)
    out=spectrum_archive_plot_projection(y,**kwargs)
    assert out["source_series_bins"]==400
    assert out["full_fft_bins"]==512
    assert out["draw_mode"]=="original_samples_when_sparse"


def test_compressed_plot_is_deterministic_and_dc_or_summary_not_touched():
    y,_,kwargs=_make(mode=2)
    a=spectrum_archive_plot_projection(y,**kwargs)
    b=spectrum_archive_plot_projection(y,**kwargs)
    np.testing.assert_array_equal(a["pairs_x_hz"],b["pairs_x_hz"])
    np.testing.assert_array_equal(a["pairs_y"],b["pairs_y"])
    assert np.all(np.isfinite(a["pairs_x_hz"]))
    assert np.all(np.isfinite(a["pairs_y"]))
