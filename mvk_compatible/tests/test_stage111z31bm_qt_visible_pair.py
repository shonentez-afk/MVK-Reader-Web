"""BM: only synthetic Qt, actual PageSpectrum Y and no false stale PASS."""
import hashlib
import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QFileDialog
from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31q_same_window_spectrum import _manifest, SOURCE_N
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested,
)


def test_visible_same_window_original_button_and_stale_reset(
        qt_app, tmp_path, monkeypatch):
    from ..desktop.main_window import MainWindow
    path, _, samples = _make_pair(tmp_path, adc=4, n=SOURCE_N * 3)
    ref, evidence, _ = _manifest(
        tmp_path / "ref", samples[-SOURCE_N:],
        mode=1, code=0, offset=len(samples) - SOURCE_N)
    win = MainWindow()
    win.show()
    try:
        win.open_archive(path)
        win.spec_n.setCurrentText(str(SOURCE_N))
        win.spec_mode.setCurrentIndex(1)
        win.refresh_spec()
        qt_app.processEvents()
        assert win.spec_pair_button.isEnabled()
        before = hashlib.sha256(np.asarray(
            win._full_spectrum["amplitude"], dtype="<f4").tobytes()).hexdigest()
        paths = iter((str(ref), str(evidence)))
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
            staticmethod(lambda *a, **k: (next(paths), "json")))
        report = win.compare_visible_original_same_window()
        assert report["paired_numeric_pass"]
        assert win._visible_original_pair is report
        assert "512/512" in win.spec_pair_status.text()
        assert "0 ULP" in win.spec_pair_status.text()
        assert hashlib.sha256(np.asarray(
            win._full_spectrum["amplitude"], dtype="<f4").tobytes()).hexdigest() == before
        win.spec_inspector.show()
        qt_app.processEvents()
        capture_synthetic_ui_if_requested(win, qt_app, "13_bm_visible_original_y")
        win._select_original_hscale(6400)
        assert win._visible_original_pair is report  # view-only pan
        win.spec_mode.setCurrentIndex(2)
        win.refresh_spec()
        qt_app.processEvents()
        assert win._visible_original_pair is None
        assert "Не проводилась" in win.spec_pair_status.text()
        win._close_session()
        assert not win.spec_pair_button.isEnabled()
    finally:
        win.close()
        qt_app.processEvents()


def test_operator_claim_for_other_window_rejected_without_altering_y(
        qt_app, tmp_path, monkeypatch):
    from ..desktop.main_window import MainWindow
    path, _, samples = _make_pair(tmp_path, adc=4, n=SOURCE_N * 2)
    ref, evidence, _ = _manifest(
        tmp_path / "ref", samples[-SOURCE_N:],
        mode=1, code=0, offset=0)  # incorrect sample indices
    win = MainWindow()
    win.show()
    try:
        win.open_archive(path)
        win.spec_n.setCurrentText(str(SOURCE_N))
        win.spec_mode.setCurrentIndex(1)
        win.refresh_spec()
        qt_app.processEvents()
        before = hashlib.sha256(np.asarray(
            win._full_spectrum["amplitude"], dtype="<f4").tobytes()).hexdigest()
        paths = iter((str(ref), str(evidence)))
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
            staticmethod(lambda *a, **k: (next(paths), "json")))
        assert win.compare_visible_original_same_window() is None
        assert win._visible_original_pair is None
        assert "ОТКАЗ" in win.spec_pair_status.text()
        assert "PASS" not in win.spec_pair_status.text()
        assert hashlib.sha256(np.asarray(
            win._full_spectrum["amplitude"], dtype="<f4").tobytes()).hexdigest() == before
    finally:
        win.close()
        qt_app.processEvents()
