"""Stage111Z31O: real Qt archive path, not a synthetic _full_spectrum injection.

A fabricated, self-consistent Single BIN/TSXML is passed through
DirectBinSession.open -> MainWindow.open_archive -> refresh_spec -> original
TQGRSeries dense/sparse presentation -> source cursor -> Copy/Save.
No original instrument recording or vendor file is committed to CI.
This proves E2E application wiring, not original Delphi numerical parity.
"""
from pathlib import Path

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_single_bin_end_to_end_four_modes_dense_sparse_cursor_and_export(
        tmp_path, qt_app, monkeypatch, mode):
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from mvk_compatible.core.direct_bin_session import DirectBinSession
    from mvk_compatible.desktop.main_window import MainWindow

    # N=65536 is an original FFT menu size. The signal has a known
    # 128-Hz narrow peak, no device DSP/AUX, and strictly local data.
    p, tsxml, original = _make_pair(tmp_path, adc=4, n=65536)
    input_bits = original.view("<u4").copy()
    win = MainWindow()
    try:
        win.show()
        qt_app.processEvents()
        win.open_archive(p)
        win.tabs.setCurrentIndex(2)
        qt_app.processEvents()
        assert isinstance(win.session, DirectBinSession)
        assert win.session.available_channels == (4,)
        assert win._ch() == 4
        assert win.spec_n.currentText() == "65536"
        assert not win.tick.isEnabled()
        assert "DSP/VALUES/AUX" in win.calc_source.text()
        assert win._full_spectrum is not None

        win.spec_mode.setCurrentIndex(mode)
        win.refresh_spec()
        qt_app.processEvents()
        actual = win._full_spectrum
        assert actual is not None
        assert actual["n_fft"] == 65536
        assert actual["mode"] == mode
        assert actual["channel"] == 4
        assert actual["df_hz"] == pytest.approx(1.)
        assert len(actual["amplitude"]) == 32768
        assert len(actual["frequency_hz"]) == 32768
        assert actual["physical_units_verified"] is False
        assert win._spectrum_summary is not None
        assert win._spectrum_summary["source"] == (
            "APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE"
        )
        source_bits = np.asarray(actual["amplitude"], dtype="<f4").view("<u4").copy()
        summary = dict(win._spectrum_summary)
        assert len(win.spec_plot.listDataItems()) == 1

        # This must exercise the production source-derived min/max renderer,
        # rather than tests that assign _full_spectrum by hand.
        model = win._archive_source_projection_model
        assert model is not None
        assert model["draw_mode"] == "original_pixel_column_minmax"
        assert model["source_series_bins"] == 25600
        assert model["full_fft_bins"] == 32768
        assert win._archive_source_curve is not None
        assert not win._archive_raw_line.isVisible()

        vb = win.spec_plot.getViewBox()
        vb.setXRange(120., 140., padding=0)
        qt_app.processEvents()
        assert win._archive_source_projection_model["draw_mode"] == (
            "original_samples_when_sparse"
        )
        assert win._archive_source_curve is None
        assert win._archive_raw_line.isVisible()

        # Pixel-based cursor must continue selecting the uncompressed FFT,
        # including after the dense->sparse transition.
        scene_pos = vb.mapViewToScene(QPointF(128., 0.))
        win._spec_at_scene_pos(scene_pos, force=True)
        assert win._spec_last_cursor is not None
        cursor = win._spec_last_cursor
        assert cursor["full_bin_count"] == 32768
        assert cursor["grapher_series_bins"] == 25600
        assert cursor["chart_decimation_used"] is False
        assert abs(cursor["frequency_hz"] - 128.) <= 2.

        vb.setXRange(0., 25600., padding=0)
        qt_app.processEvents()
        assert win._archive_source_projection_model["draw_mode"] == (
            "original_pixel_column_minmax"
        )
        assert win._archive_source_curve is not None
        assert len(win.spec_plot.listDataItems()) == 1
        np.testing.assert_array_equal(
            np.asarray(actual["amplitude"], dtype="<f4").view("<u4"),
            source_bits,
        )
        assert win._spectrum_summary == summary
        np.testing.assert_array_equal(
            win.session.samples(4)[0].view("<u4"), input_bits
        )

        monkeypatch.setattr(
            QMessageBox, "question", lambda *a, **kw: QMessageBox.Yes
        )
        win._copy_spec_summary()
        clip = QApplication.clipboard().text()
        assert "НЕ КАЛИБРОВАНО" in clip
        assert len(clip.strip().splitlines()[-1].split("\t")) == 3
        destination = tmp_path / f"summary_mode{mode}.csv"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *a, **kw: (str(destination), "CSV (*.csv)"),
        )
        win._save_spec_summary()
        csv_text = destination.read_text(encoding="utf-8")
        assert "НЕ КАЛИБРОВАНО" in csv_text
        assert "sep=|" in csv_text
        assert len(csv_text.splitlines()[-1].split("|")) == 3
    finally:
        win.close()
        qt_app.processEvents()


def test_changed_direct_bin_recalculation_never_leaves_stale_spectrum(
        tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from mvk_compatible.desktop.main_window import MainWindow

    p, _, _ = _make_pair(tmp_path, adc=4, n=65536)
    win = MainWindow()
    try:
        win.show()
        qt_app.processEvents()
        win.open_archive(p)
        win.tabs.setCurrentIndex(2)
        qt_app.processEvents()
        assert win._full_spectrum is not None
        assert win._spectrum_summary is not None
        assert len(win.spec_plot.listDataItems()) == 1

        # Same-length mutation: checks SHA on every use (not just open).
        raw = bytearray(p.read_bytes())
        raw[101] ^= 1
        p.write_bytes(raw)
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning",
            lambda _parent, title, message: warnings.append((title, message)),
        )
        win.refresh_spec()
        qt_app.processEvents()
        assert warnings and "изменён" in warnings[-1][1]
        assert win._full_spectrum is None
        assert win._spectrum_summary is None
        assert win._spec_last_cursor is None
        assert win._archive_source_curve is None
        assert win._archive_raw_line is None
        assert len(win.spec_plot.listDataItems()) == 0
        assert not win.spec_copy_button.isEnabled()
        assert not win.spec_save_button.isEnabled()
        assert "Спектр не рассчитан" in win.spec_mean.text()
        assert "Нет действительного спектра" in win.spec_hint.text()
        assert win.spec_cursor_primary.text() == "Курсор: —"
        # Stage BL: no second read of a tampered source from pnView cleanup.
        # Source FRange, absolute time and H pane must not outlive rejected BIN.
        assert win._source_view_time is None
        assert win._source_spectrum_gain is None
        assert win._spec_source_h_view is None
        assert not win.original_shell.view_panel.isVisible()
    finally:
        win.close()
        qt_app.processEvents()
