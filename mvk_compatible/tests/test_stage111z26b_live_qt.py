"""Stage111Z.26B Qt: original three tabs show provisional from local ZIP only."""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app


def _preview(tmp_path):
    from .test_stage111z26b_live_preview import make_preview,now
    from mvk_compatible.core.native_r6_live_preview import load_live_preview
    root,status,_=make_preview(tmp_path)
    return load_live_preview(root,status,now=now())


def test_live_preview_uses_same_existing_wave_spectrum_tabs_without_archive(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    window=MainWindow()
    assert not window._live_active
    assert window.session is None
    assert window.tabs.count()==3
    assert not window.tabs.isTabEnabled(1)
    window._begin_live_capture()
    assert window._live_active
    assert window.tabs.count()==3
    assert window.tabs.isTabEnabled(1)
    assert window.tabs.isTabEnabled(2)
    assert not window.tick.isEnabled()
    assert not window.task_metrics_button.isEnabled()
    assert "LIVE" in window.note.text()
    preview=_preview(tmp_path)
    window._receive_live_preview(preview)
    assert len(window.wave_plot.listDataItems())==1
    assert len(window.spec_plot.listDataItems())==1
    assert "LIVE PREVIEW" in window.wave_hint.text()
    assert "FRange повторно НЕ применялся" in window.spec_hint.text()
    assert not window.spec_copy_button.isEnabled()
    assert not window.spec_save_button.isEnabled()
    assert window._spectrum_summary is None
    assert window._full_spectrum is None
    assert window.wave_line is None
    assert window.session is None
    window.adc.setCurrentIndex(6)
    qt_app.processEvents()
    assert "АЦП7" in window.wave_mean_primary.text()
    window.spec_mode.setCurrentIndex(1)
    qt_app.processEvents()
    assert len(window.spec_plot.listDataItems())==1
    window._invalidate_live_preview("некорректный SHA")
    assert not window.wave_plot.listDataItems()
    assert not window.spec_plot.listDataItems()
    window._end_live_capture(False)
    assert not window._live_active
    assert not window.tabs.isTabEnabled(1)
    assert window.session is None
    window.close()
    qt_app.processEvents()


def test_original_archive_restored_on_failed_capture(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    window=MainWindow()
    path=fixture_zip(tmp_path)
    window.open_archive(path)
    assert window.session is not None
    serial=window.session.serial
    window._begin_live_capture()
    assert window.session is None
    window.open_archive(path)  # forbidden during live, no replacement
    assert window.session is None
    window._end_live_capture(False)
    assert window.session is not None and window.session.serial==serial
    assert len(window.wave_plot.listDataItems())==1
    window.close()
    qt_app.processEvents()


def test_live_completion_disables_preview_until_verified_archive(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    window=MainWindow()
    window._begin_live_capture()
    window._receive_live_preview(_preview(tmp_path))
    window._end_live_capture(True)
    assert window.session is None
    assert not window._live_active
    assert not window.wave_plot.listDataItems()
    verified=fixture_zip(tmp_path)
    window.open_archive(verified)
    assert window.session is not None
    assert not window._live_active
    assert len(window.wave_plot.listDataItems())==1
    window.close()
    qt_app.processEvents()
