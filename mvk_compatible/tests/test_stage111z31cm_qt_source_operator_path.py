"""Stage111Z31CM: *ordinary visible* MVKView source-mode operator path.

Uses synthetic Single BIN+TSXML through the genuine DirectBinSession and
the normal PageSpectrum, not a hand-rendered screenshot or injected FFT.
All original EXE/DFM/IDP/Power/Y, hardware and user measurements stay out of
GitHub Actions. This is CI application behavior, NOT 1:1 original parity.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QRawFont
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QToolButton

from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..core.direct_bin_session import DirectBinSession
from ..desktop.main_window import MainWindow
from ..core.original_ui_form_contract import ORIGINAL_SPECTRUM_CONTROLS


def _f32_sha(data) -> str:
    return sha256(np.asarray(data, dtype="<f4").tobytes()).hexdigest()


def _capture_source_screen(win, qt_app, name: str):
    """One actual Qt window grab + a bounded, non-private layout receipt."""
    folder_name = os.environ.get("MVK_SOURCE_OPERATOR_QA_DIR")
    if not folder_name:
        return
    directory = Path(folder_name)
    directory.mkdir(parents=True, exist_ok=True)
    settle(qt_app)
    shot = win.grab()
    assert not shot.isNull() and shot.width() >= 960 and shot.height() >= 580
    target = directory / (name + ".png")
    assert shot.save(str(target), "PNG")
    font = QRawFont.fromFont(win.font())
    try:
        cyrillic_supported = font.isValid() and all(
            font.supportsCharacter(ord(ch)) for ch in "Спектр"
        )
    except (AttributeError, RuntimeError):
        cyrillic_supported = None
    data = win._full_spectrum
    model = win.spec_plot.source_canvas_model
    report = {
        "source": "STAGE111Z31CM_SYNTHETIC_CI_NOT_ORIGINAL_RUNTIME",
        "phase": name,
        "source_1_to_1_pixel_parity_verified": False,
        "operator_private_data_included": False,
        "original_vendor_bitmap_included": False,
        "source_mode": not win.original_visual_skin.technical,
        "root_DFM_pages_mounted": win.original_root_tabs.count(),
        "visible_source_tabs": win.original_visual_skin.snapshot()["visible_source_tabs"],
        "current_source_page": win.original_root_tabs.tabData(
            win.original_root_tabs.currentIndex()),
        "menu_visible": win.menuBar().isVisible(),
        "status_bar_visible": win.statusBar().isVisible(),
        "legacy_tab_strip_visible": win.tabs.tabBar().isVisible(),
        "research_dock_visible": (
            win.wave_inspector.isVisible() or win.spec_inspector.isVisible()),
        "auxiliary_toolbar_visible": win.compat_toolbar.isVisible(),
        "source_tools_logical_width": win.spec_tools.width(),
        "source_pnview_logical_height": win.original_shell.view_panel.height(),
        "qt_font_family": win.font().family(),
        "qt_raw_font_supports_cyrillic_candidate": cyrillic_supported,
        "dpi_scale": win.devicePixelRatioF(),
        "window_logical_size": [win.width(), win.height()],
        "grab_physical_size": [shot.width(), shot.height()],
        "screen_sha256": sha256(target.read_bytes()).hexdigest(),
        "source_graph_layout_candidate": model if model is not None else None,
        "synthetic_fft": (
            {
                "n_fft": data["n_fft"],
                "mode": data["mode"],
                "full_y_count": len(data["amplitude"]),
                "full_y_sha256": _f32_sha(data["amplitude"]),
                "plot_minmax_mode": win._archive_source_projection_model[
                    "draw_mode"] if win._archive_source_projection_model else None,
            } if data is not None else None
        ),
    }
    (directory / (name + ".json")).write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2,
                   default=str) + "\n", encoding="utf-8")


def test_real_visible_operator_path_uses_one_source_shell_graph_and_export(
        tmp_path, qt_app, monkeypatch):
    # This is the main user path, not a screenshot of a technical PageFile.
    bin_path, _, original = _make_pair(tmp_path, adc=4, n=65536, fs=65536)
    original_bits = original.view("<u4").copy()
    win = MainWindow()
    try:
        win.resize(1360, 850)
        win.show()
        settle(qt_app)
        skin = win.original_visual_skin
        assert skin.snapshot()["visible_source_tabs"] == ["PageStart"]
        assert win.original_root_tabs.count() == 7
        assert not win.menuBar().isVisible()
        assert not win.compat_toolbar.isVisible()
        assert not win.tabs.tabBar().isVisible()
        assert not win.task_subpages.tabBar().isVisible()
        _capture_source_screen(win, qt_app, "00_original_start")

        # The BIN/TSXML is REALLY parsed; no session=object() or _full_spectrum
        # fixture injection is permitted in this acceptance route.
        win.open_archive(bin_path)
        settle(qt_app)
        assert isinstance(win.session, DirectBinSession)
        assert win.session.available_channels == (4,)
        assert skin.snapshot()["visible_source_tabs"] == [
            "PageStart", "PageAdc", "PageSpectrum"]
        win.original_root_tabs.setCurrentIndex(4)
        settle(qt_app)
        assert win.original_root_tabs.tabData(
            win.original_root_tabs.currentIndex()) == "PageSpectrum"
        assert not win.original_measure_controls.panel.isVisible()
        assert win.original_shell.view_panel.height() == 48
        assert win.spec_tools.width() == 177
        assert win.spec_source_canvas.isVisible()
        assert win.spec_plot.isVisible()
        assert not win.spec_inspector.isVisible()
        assert not win.menuBar().isVisible()
        assert not win.statusBar().isVisible()
        assert not win.tabs.tabBar().isVisible()

        # Source visual controls are the REAL production widgets, not a
        # second row of buttons or a screenshot overlay.
        widgets = win.spec_source_canvas.findChildren(QToolButton)
        assert win.spec_vscale_button in widgets
        assert win.spec_hscale_button in widgets
        assert win.spec_vscale_button.popupMode() == QToolButton.InstantPopup
        for name, kind, x, y, width, height in ORIGINAL_SPECTRUM_CONTROLS:
            matched = [
                widget for widget in win.spec_source_canvas.findChildren(
                    QToolButton) if widget.property("originalDfmControlName") == name
            ]
            if matched:
                assert len(matched) == 1
                assert matched[0].geometry().getRect() == (x, y, width, height)

        assert win._full_spectrum is not None
        fft = win._full_spectrum
        assert fft["n_fft"] == 65536
        assert fft["channel"] == 4
        assert len(fft["amplitude"]) == 32768
        initial_fft_sha = _f32_sha(fft["amplitude"])
        initial_summary = dict(win._spectrum_summary)
        assert win._archive_source_projection_model[
            "draw_mode"] == "original_pixel_column_minmax"
        _capture_source_screen(win, qt_app, "01_original_spectrum")

        # Source split-button actions change the visual viewport, NEVER
        # cycle the GetSpectrum data or replace an FFT line.
        selected = win._spec_vscale_actions[2]
        selected.trigger()
        settle(qt_app)
        assert win._spec_original_vscale_tag == 2
        assert _f32_sha(win._full_spectrum["amplitude"]) == initial_fft_sha
        _capture_source_screen(win, qt_app, "02_original_y_scale")

        vb = win.spec_plot.getViewBox()
        vb.setXRange(120., 140., padding=0)
        settle(qt_app)
        assert win._archive_source_projection_model[
            "draw_mode"] == "original_samples_when_sparse"
        assert win._archive_raw_line.isVisible()
        point = vb.mapViewToScene(QPointF(128., -30.))
        win._spec_at_scene_pos(point, force=True)
        assert win._spec_last_cursor is not None
        assert not win._spec_last_cursor["chart_decimation_used"]
        assert abs(win._spec_last_cursor["frequency_hz"] - 128.) <= 2.
        _capture_source_screen(win, qt_app, "03_original_zoom_cursor")

        # Exercise the actual buttons, not only their underlying private
        # methods; uncalibrated BIN is exported with explicit warning.
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        win.spec_copy_button.click()
        clipboard = QApplication.clipboard().text()
        assert "НЕ КАЛИБРОВАНО" in clipboard
        assert len(clipboard.strip().splitlines()[-1].split("\t")) == 3
        destination = tmp_path / "stage111cm_operator_spec.csv"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *args, **kwargs: (str(destination), "CSV (*.csv)"))
        win.spec_save_button.click()
        saved = destination.read_text(encoding="utf-8")
        assert "НЕ КАЛИБРОВАНО" in saved
        assert "sep=|" in saved
        assert len(saved.splitlines()[-1].split("|")) == 3

        vb.setXRange(0., 25600., padding=0)
        settle(qt_app)
        assert win._archive_source_projection_model[
            "draw_mode"] == "original_pixel_column_minmax"
        assert win._archive_source_curve is not None
        assert win._spectrum_summary == initial_summary
        assert _f32_sha(win._full_spectrum["amplitude"]) == initial_fft_sha
        np.testing.assert_array_equal(
            win.session.samples(4)[0].view("<u4"), original_bits)

        # F12 is a reversible technical overlay, not another native form:
        # leaving it must remove any opened diagnostic dock/toolbar/tabs.
        skin.toggle_action.setChecked(True)
        settle(qt_app)
        assert skin.technical
        assert len(skin.snapshot()["visible_source_tabs"]) == 7
        win.spec_inspector.show()
        win.compat_toolbar.show()
        win.research_tabs_action.setChecked(True)
        settle(qt_app)
        assert win.spec_inspector.isVisible()
        skin.toggle_action.setChecked(False)
        settle(qt_app)
        assert not skin.technical
        assert skin.snapshot()["visible_source_tabs"] == [
            "PageStart", "PageAdc", "PageSpectrum"]
        assert not win.spec_inspector.isVisible()
        assert not win.compat_toolbar.isVisible()
        assert not win.task_subpages.tabBar().isVisible()
        assert not win.menuBar().isVisible()
        assert _f32_sha(win._full_spectrum["amplitude"]) == initial_fft_sha
        _capture_source_screen(win, qt_app, "04_original_after_f12")
    finally:
        win.close()
        settle(qt_app)
