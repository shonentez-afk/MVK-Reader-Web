"""Stage111Z31Q: GUI edge matrix on actual synthetic BIN/TSXML files.

Source-derived spectrum, cursor and min/max chart share the same full N/2
Float32. No original screenshot or device is used or asserted here.
"""
import math

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair
from ..core.tqgrapher_display_idr_candidate import spectrum_display_contract


@pytest.mark.parametrize("n_fft,fs,mode", [
    (8192,16384,0),
    (8192,65536,1),
    (65536,65536,2),
    (262144,65536,3),
])
def test_real_archive_qt_n_fs_zoom_cursor_precision_and_full_fft_preserved(
        tmp_path,qt_app,n_fft,fs,mode):
    from PySide6.QtCore import QPointF
    from mvk_compatible.desktop.main_window import MainWindow

    p,_,original=_make_pair(tmp_path,adc=4,n=n_fft,fs=fs)
    original_bits=original.view("<u4").copy()
    win=MainWindow()
    try:
        win.show()
        qt_app.processEvents()
        win.open_archive(p)
        win.tabs.setCurrentIndex(2)
        qt_app.processEvents()
        win.spec_n.setCurrentText(str(n_fft))
        win.spec_mode.setCurrentIndex(mode)
        win.refresh_spec()
        qt_app.processEvents()

        d=win._full_spectrum
        assert d is not None
        assert d["channel"]==4
        assert d["n_fft"]==n_fft
        assert d["mode"]==mode
        assert d["df_hz"]==pytest.approx(fs/n_fft)
        assert len(d["amplitude"])==n_fft//2
        assert len(d["frequency_hz"])==n_fft//2
        contract=spectrum_display_contract(n_fft,fs)
        count=contract["grapher_series_bins"]
        assert d["grapher_series_bins"]==count
        assert count<n_fft//2
        assert contract["grapher_axis_end_frequency_hz"]==pytest.approx(
            count*fs/n_fft)
        assert win._spec_visible_max_hz<=contract[
            "grapher_axis_end_frequency_hz"]
        assert len(win.spec_plot.listDataItems())==1
        full_y=np.asarray(d["amplitude"],dtype="<f4").view("<u4").copy()
        initial_summary=dict(win._spectrum_summary)
        first_mode=win._archive_source_projection_model["draw_mode"]
        assert first_mode=="original_pixel_column_minmax"

        vb=win.spec_plot.getViewBox()
        vb.setXRange(120,140,padding=0)
        qt_app.processEvents()
        assert win._archive_source_projection_model["draw_mode"]==(
            "original_samples_when_sparse")
        assert win._archive_raw_line.isVisible()
        assert win._archive_source_curve is None
        # Cursor source is the FULL source Y and is never selected
        # from a decimated curve or from hidden Nyquist-tail bins.
        cursor_scene=vb.mapViewToScene(QPointF(128.,0.))
        win.spec_precise.setChecked(True)
        win.spec_avg.setCurrentIndex(0)
        win._spec_at_scene_pos(cursor_scene,force=True)
        chosen=win._spec_last_cursor
        assert chosen is not None
        assert chosen["full_bin_count"]==n_fft//2
        assert chosen["grapher_series_bins"]==count
        assert not chosen["chart_decimation_used"]
        assert abs(chosen["frequency_hz"]-128.)<=2.*fs/n_fft
        assert chosen["selected_bin"]<count
        assert chosen["averaging"]==1

        win.spec_avg.setCurrentIndex(1)
        win._spec_at_scene_pos(cursor_scene,force=True)
        averaged=win._spec_last_cursor
        assert averaged is not None
        assert averaged["averaging"]==3
        values=np.asarray(d["amplitude"],dtype="<f4")
        index=averaged["selected_bin"]
        lo=max(0,index-1)
        hi=min(len(values),index+2)
        expected=np.float32(0.)
        for value in values[lo:hi]:
            expected=np.float32(float(expected)+float(value)*float(value))
        expected=np.float32(math.sqrt(float(expected)))
        assert averaged["display_y"]==float(expected)

        # Fully leave the chart: original clears both cursor traces.
        rect=vb.sceneBoundingRect()
        win._spec_at_scene_pos(
            QPointF(rect.left()-2.,rect.center().y()),force=True)
        assert win._spec_last_cursor is None
        assert win.spec_cursor_primary.text()=="Курсор: —"

        vb.setXRange(0.,count*fs/n_fft,padding=0)
        qt_app.processEvents()
        assert win._archive_source_projection_model["draw_mode"]==(
            "original_pixel_column_minmax")
        assert win._archive_source_curve is not None
        assert not win._archive_raw_line.isVisible()
        assert len(win.spec_plot.listDataItems())==1
        assert win._spectrum_summary==initial_summary
        np.testing.assert_array_equal(
            np.asarray(d["amplitude"],dtype="<f4").view("<u4"),full_y)
        np.testing.assert_array_equal(
            win.session.samples(4)[0].view("<u4"),original_bits)
    finally:
        win.close()
        qt_app.processEvents()
