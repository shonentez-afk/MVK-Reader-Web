"""FactoryMode source gate, using only synthetic Qt state; no device IO."""
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QMessageBox
from .test_desktop_qt import qt_app
from ..desktop.main_window import MainWindow


def test_local_factory_confirmation_and_source_mode5(qt_app,monkeypatch):
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        start=win.original_start_controller
        button=start.buttons["bTaskConfigCalib"]
        assert not button.isVisible()
        assert start.open_config_mode(5) is False
        monkeypatch.setattr(QMessageBox,"question",lambda *a,**k:QMessageBox.No)
        assert not start.request_factory_mode()
        assert not button.isVisible()
        monkeypatch.setattr(QMessageBox,"question",lambda *a,**k:QMessageBox.Yes)
        assert start.request_factory_mode()
        assert button.isVisible()
        assert start.open_config_mode(5)==5
        panel=win.original_config_panel
        assert panel.source_mode==5
        assert win.original_root_tabs.tabText(1)=="Калибровочные значения"
        assert panel.basic_table.isVisible()
        assert not panel.page_tabs.isVisible()
        assert not panel.download_button.isEnabled()
        assert not panel.upload_button.isEnabled()
        assert panel.reset_button.isEnabled()
        win.original_visual_skin.reveal_page(0)
        assert win.enter_measurement_mode()
        assert "PageCalib" in win.original_visual_skin.snapshot()["visible_source_tabs"]
        assert start.open_config_mode(6) is False
        assert win.leave_measurement_mode()
        assert not win._live_active
    finally:
        win.close()
        qt_app.processEvents()
