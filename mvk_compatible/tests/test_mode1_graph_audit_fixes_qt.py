"""Operator routes: local BIN, actual graph menu clicks, view-only changes."""
from __future__ import annotations

import hashlib

import pytest
import numpy as np

pytest.importorskip("PySide6")
from PySide6.QtCore import QPoint, QPointF, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton

from .test_desktop_qt import qt_app
from .test_mode1_saved_adc_spectrum_export_qt import _adc
from ..desktop.main_window import MainWindow


def _choose(qt_app, button, menu, action):
    shown = []
    def select():
        shown.append(True)
        QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
    def ready():
        QTimer.singleShot(0, select)
    menu.aboutToShow.connect(ready)
    failsafe = QTimer()
    failsafe.setSingleShot(True)
    failsafe.timeout.connect(menu.hide)
    failsafe.start(250)
    try:
        QTest.mouseClick(button, Qt.LeftButton, pos=QPoint(10, button.height() // 2))
        qt_app.processEvents()
    finally:
        failsafe.stop()
        menu.aboutToShow.disconnect(ready)
    assert shown


def _open(qt_app, window, monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), "BIN"))
    window.original_root_tabs.setCurrentIndex(0)
    launch = window.original_start_launcher.findChild(QPushButton, "bTaskView")
    QTest.mouseClick(launch, Qt.LeftButton)
    qt_app.processEvents()
    assert window.session.path == path


def _page(qt_app, window, index):
    window.original_root_tabs.setCurrentIndex(index)
    qt_app.processEvents()


def _hash(data):
    return hashlib.sha256(np.asarray(data["amplitude"],dtype="<f4").tobytes()).hexdigest()


def test_saved_units_menu_reselect_and_stock_channel_transition(
        qt_app, tmp_path, monkeypatch):
    standard, _ = _adc(tmp_path, 1, "м/с2", 12.25, fs=65536, n=340000)
    custom, _ = _adc(tmp_path, 8, "g", 2.5, fs=65536, n=340000)
    w = MainWindow()
    w.resize(1366, 950)
    w.show()
    qt_app.processEvents()
    try:
        _open(qt_app, w, monkeypatch, custom)
        _page(qt_app, w, 3)
        a = w.wave_type_menu.actions()[0]
        for _ in range(2):
            _choose(qt_app, w.wave_type_button, w.wave_type_menu, a)
            assert [i for i in w.wave_type_menu.actions() if i.isChecked()] == [a]
        assert w.wave_plot.getAxis("left").labelText == "g"
        assert all(a.text().endswith(" g") for a in w.wave_vscale_menu.actions())
        assert w.wave_mean_primary.text().splitlines()[0].endswith(" g")
        wave_box = w.wave_plot.getViewBox()
        w._wave_at_scene_pos(wave_box.sceneBoundingRect().center(), force=True)
        assert w.wave_cursor_primary.text().splitlines()[-1].endswith(" g")

        _page(qt_app, w, 4)
        for i, (axis, summary) in enumerate(zip(("дБ", "g", "~g", "~~g"), ("g", "g", "~g", "~~g"))):
            a = w.spec_type_menu.actions()[i]
            for _ in range(2):
                _choose(qt_app, w.spec_type_button, w.spec_type_menu, a)
                assert [i for i in w.spec_type_menu.actions() if i.isChecked()] == [a]
            assert w.spec_plot.getAxis("left").labelText == axis
            assert all(v.text().endswith(" "+axis) for v in w.spec_vscale_menu.actions())
            assert f" {summary} (условн.)" in w.spec_mean_primary.text().splitlines()[0]
            box = w.spec_plot.getViewBox()
            w._spec_at_scene_pos(box.sceneBoundingRect().center(), force=True)
            assert w.spec_cursor_primary.text().splitlines()[-1].endswith(" "+axis)
        a = next(a for a in w.spec_lines_menu.actions() if a.isChecked())
        spectrum = w._full_spectrum
        _choose(qt_app, w.spec_lines_button, w.spec_lines_menu, a)
        assert [i for i in w.spec_lines_menu.actions() if i.isChecked()] == [a]
        assert w._full_spectrum is spectrum  # Re-select does not rerun FFT.
        _open(qt_app, w, monkeypatch, standard)
        assert w.spec_plot.getAxis("left").labelText == "мкм"
        assert w._spec_last_cursor is None
        assert w.wave_plot.getAxis("left").labelText == "м/с2"
    finally:
        w.close()
        qt_app.processEvents()


def test_offline_cursor_reprojects_without_new_fft_and_empty_time_keeps_x(
        qt_app, tmp_path, monkeypatch):
    path, _ = _adc(tmp_path, 1, "м/с2", 12.25, fs=65536, n=340000)
    w = MainWindow()
    w.resize(1366, 950)
    w.show()
    qt_app.processEvents()
    try:
        _open(qt_app, w, monkeypatch, path)
        _page(qt_app, w, 4)
        box = w.spec_plot.getViewBox()
        rect = box.sceneBoundingRect()
        px = int(rect.width() * .36)
        w._spec_at_scene_pos(QPointF(rect.left()+px+.01,rect.center().y()),force=True)
        old_cursor = w._spec_last_cursor
        original = w._full_spectrum
        digest = _hash(original)
        assert old_cursor is not None

        # Trigger menu actions at the stationary cursor; Qt need not get
        # a subsequent MouseMove to display the new frequency.
        hscale = next(a for a in w.spec_hscale_menu.actions() if a.data() == 6400)
        hscale.trigger()
        qt_app.processEvents()
        new_cursor = w._spec_last_cursor
        assert new_cursor is not None
        assert new_cursor["frequency_hz"] == pytest.approx(old_cursor["frequency_hz"]/4, rel=.025)
        vscale = w.spec_vscale_menu.actions()[1]
        vscale.trigger()
        qt_app.processEvents()
        assert w._spec_last_cursor["frequency_hz"] == pytest.approx(new_cursor["frequency_hz"], rel=.025)
        w.spec_hscroll.setValue(400)
        qt_app.processEvents()
        assert w._spec_last_cursor["frequency_hz"] == pytest.approx(
            new_cursor["frequency_hz"]+400, rel=.025)
        assert w._full_spectrum is original and _hash(original) == digest

        rect = box.sceneBoundingRect()
        w._spec_at_scene_pos(QPointF(rect.right()+5,rect.center().y()),force=True)
        assert w._spec_last_cursor is None
        w.spec_hscroll.setValue(800)
        qt_app.processEvents()
        assert w._spec_last_cursor is None
        assert w.spec_cursor_primary.text() == "Курсор: —"
        w._spec_at_scene_pos(box.sceneBoundingRect().center(),force=True)
        assert w._spec_last_cursor is not None

        slider = w.original_shell.view_slider
        slider.setValue(0)
        qt_app.processEvents()
        assert w._full_spectrum is None and w._spec_last_cursor is None
        assert not w.spec_copy_button.isEnabled() and not w.spec_save_button.isEnabled()
        assert w.spec_hscale_button.text() == "6400 Гц"
        assert box.viewRange()[0] == pytest.approx([800.,7200.])
        QApplication.clipboard().setText("not an FFT")
        w.spec_copy_button.click()
        assert QApplication.clipboard().text() == "not an FFT"
        slider.setValue(slider.maximum())
        qt_app.processEvents()
        assert w._full_spectrum is not None and _hash(w._full_spectrum) == digest
        assert w._spec_last_cursor is None  # Real window change does not inherit a pointer.
        assert w.spec_copy_button.isEnabled() and w.spec_save_button.isEnabled()
        assert hscale.isChecked()
        assert box.viewRange()[0] == pytest.approx([800.,7200.])
    finally:
        w.close()
        qt_app.processEvents()

def test_spectrum_research_exposes_explicit_local_idp_picker_without_selecting_fir(
        qt_app, tmp_path, monkeypatch):
    from .test_envelope_idr_candidate import fake_profile
    from ..core.envelope_idr_candidate import EnvelopeProfile

    path, _ = _adc(tmp_path, 1, "м/с2", 12.25, fs=65536, n=134000)
    w = MainWindow()
    w.show()
    qt_app.processEvents()
    picks = []
    profile = fake_profile()
    try:
        _open(qt_app, w, monkeypatch, path)
        _page(qt_app, w, 4)
        assert len(w.original_envelope_menu.actions()) == 32
        assert not w.original_envelope_menu.actions()[20].isEnabled()
        assert "локальный IDP" in w.spec_envelope_button.toolTip()
        QTest.mouseClick(w.spec_advanced_button, Qt.LeftButton)
        qt_app.processEvents()
        assert w.spec_envelope_load.isVisible()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: ("", ""))
        QTest.mouseClick(w.spec_envelope_load, Qt.LeftButton)
        assert w.envelope_profile is None
        path_idp = tmp_path / "example.idp"
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path_idp), "IDP"))
        def fake_loader(selected):
            picks.append(selected)
            return profile
        monkeypatch.setattr(EnvelopeProfile, "from_original_local_idp", fake_loader)
        QTest.mouseClick(w.spec_envelope_load, Qt.LeftButton)
        qt_app.processEvents()
        assert picks == [str(path_idp)]
        assert w.envelope_profile is profile
        assert w.original_envelope_menu.actions()[20].isEnabled()
        assert w.wave_envelope_code.currentData() == w.spec_envelope_code.currentData() == 0
        assert not w.spec_envelope_button.isChecked()
    finally:
        w.close()
        qt_app.processEvents()
