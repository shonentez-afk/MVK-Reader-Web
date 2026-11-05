"""Stage111Z31N Windows Qt: ordinary archive plot uses source minmax.

This test injects a synthetic completed archive spectrum into the
existing normal chart, without reading device/old private captures.
No change of FFT, original power, three-value summary or cursor arrays.
"""
import numpy as np
import pytest

from .test_desktop_qt import qt_app
from mvk_compatible.core.tqgrapher_display_idr_candidate import (
    spectrum_display_contract,
)


@pytest.mark.parametrize("mode",[0,1,2,3])
def test_normal_archive_graph_preserves_spike_at_high_fft_density(
        qt_app,mode):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    n=262144
    fs=65536.
    df=fs/n
    bins=n//2
    count=spectrum_display_contract(n,fs)["grapher_series_bins"]
    data=np.full(bins, -90. if mode==0 else 1.,dtype="<f4")
    data[count//2+100]=np.float32(-5. if mode==0 else 16.)
    original=data.view("<u4").copy()
    summary={"output_peak_frequency_hz":float((count//2+100)*df)}
    win.session=object()  # only a non-null synthetic completed archive guard
    win._spectrum_reference=None
    win._spectrum_summary=summary
    win._full_spectrum={
        "amplitude":data,"df_hz":df,
        "frequency_hz":np.arange(bins,dtype=np.float64)*df,
        "unit":"дБ" if mode==0 else "м/с²",
    }
    win._spec_display_contract=spectrum_display_contract(n,fs)
    win._spec_visible_max_hz=float(count*df)
    win._spec_data_ymin=-100. if mode==0 else 0.
    win._spec_data_ymax=0. if mode==0 else 20.
    win.spec_plot.clear()
    win._archive_raw_line=win.spec_plot.plot(
        win._full_spectrum["frequency_hz"][:count],
        data[:count],pen="#000000")
    vb=win.spec_plot.getViewBox()
    vb.setXRange(0.,count*df,padding=0)
    vb.setYRange(*((-100.,0.) if mode==0 else (0.,20.)),padding=0)
    qt_app.processEvents()
    win._sync_archive_source_projection()
    model=win._archive_source_projection_model
    assert model["draw_mode"]=="original_pixel_column_minmax"
    assert model["full_fft_bins"]==bins
    assert model["source_series_bins"]==count
    assert model["segments_count"]>0
    assert win._archive_source_curve is not None
    assert win._archive_source_curve.scene() is not None
    assert not win._archive_raw_line.isVisible()
    assert win._spectrum_summary is summary
    np.testing.assert_array_equal(data.view("<u4"),original)

    # At sparse zoom show all original points instead of skipping bins.
    vb.setXRange(1000.,1020.,padding=0)
    qt_app.processEvents()
    assert win._archive_source_projection_model[
        "draw_mode"]=="original_samples_when_sparse"
    assert win._archive_source_curve is None
    assert win._archive_raw_line.isVisible()
    np.testing.assert_array_equal(data.view("<u4"),original)

    # Zoom back, no duplicated lines; projection has new viewport bounds.
    vb.setXRange(0.,count*df,padding=0)
    qt_app.processEvents()
    assert win._archive_source_projection_model[
        "draw_mode"]=="original_pixel_column_minmax"
    assert win._archive_source_curve is not None
    assert win._archive_source_curve.scene() is not None
    np.testing.assert_array_equal(data.view("<u4"),original)
    win._clear_archive_source_projection()
    assert win._archive_source_curve is None
    assert win._archive_raw_line.isVisible()
    win._archive_raw_line=None
    win._full_spectrum=None
    win.session=None
    win.close()
    qt_app.processEvents()


def test_archive_projection_does_not_run_on_original_reference_or_live(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    count=102400
    n=262144
    win.session=object()
    win._full_spectrum={"amplitude":np.ones(n//2,dtype="<f4"),"df_hz":.25}
    win._spec_display_contract=spectrum_display_contract(n,65536)
    win._archive_raw_line=win.spec_plot.plot(
        np.arange(count,dtype=np.float64)*.25,
        np.ones(count),pen="#000000")
    win._spectrum_reference=object()
    win._sync_archive_source_projection()
    assert win._archive_source_curve is None
    win._spectrum_reference=None
    win._live_active=True
    win._sync_archive_source_projection()
    assert win._archive_source_curve is None
    win._live_active=False
    win._archive_raw_line=None
    win._full_spectrum=None
    win.session=None
    win.close()
