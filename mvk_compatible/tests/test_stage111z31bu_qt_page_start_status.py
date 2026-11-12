"""Stage111Z31BU original PageStart and PageStatus integrated Qt+Core E2E.

Native R6.1 / Direct BIN synthetic sources only; no network, COM or device.
Strict DFM coordinate checks at Windows 150% DPI and 15 original modes.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import csv
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit,QPushButton,QListWidget,QTableWidget,QWidget,
    QLabel,QFileDialog,QStackedWidget,
)

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested)
from ..core.original_start_workbench import (
    START_BUTTONS,START_IP_RECT,START_LIBRARY_RECT,
)
from ..core.original_status_workbench import (
    ORIGINAL_STATUS_GRIDS,MODE_GRID,source_status_projection,
)
from ..core.direct_bin_session import DirectBinSession


def test_original_start_page_source_5_rectangles_ip_folder_and_real_navigation(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.original_root_tabs.setCurrentIndex(0)
        qt_app.processEvents()
        controller=win.original_start_controller
        host=win.original_start_launcher
        assert controller.host is host
        assert host.objectName()=="SourcePageStartLauncher"
        assert host.isVisible()
        assert controller.workspace.report()["device_io_performed"] is False
        for name,x,y,w,h,image,tab,mode in START_BUTTONS:
            b=host.findChild(QPushButton,name)
            assert b is not None
            assert b.geometry().getRect()==(x,y,w,h)
            assert b.property("originalDfmTabOrder")==tab
            assert b.property("originalHandlerMode")==mode
            assert b.property("originalDfmImageName")==image
            assert b.property("originalDfmLogicalRect")==(x,y,w,h)
        assert not host.findChild(QPushButton,"bTaskConfigCalib").isVisible()
        assert not host.findChild(QPushButton,"bTaskConfigCalib").isEnabled()
        ip=host.findChild(QLineEdit,"edIpAddr")
        folder_edit=host.findChild(QLineEdit,"edLibraryPath")
        assert ip.geometry().getRect()==START_IP_RECT
        assert folder_edit.geometry().getRect()==START_LIBRARY_RECT
        assert folder_edit.isReadOnly()
        assert ip.text()=="192.168.0.30"
        assert folder_edit.text()=="*"
        assert controller.workspace.library_path is None
        assert host.findChild(QListWidget,"localSourceLibraryFiles").count()==0
        capture_synthetic_ui_if_requested(
            win,qt_app,"27_bu_original_start_rects_ip_library")

        # bTaskConfigIP original mode 4 and bTaskConfigCh original mode 6.
        host.findChild(QPushButton,"bTaskConfigIP").click()
        assert win.original_root_tabs.currentIndex()==1
        assert win.original_config_panel.source_mode==4
        win.original_root_tabs.setCurrentIndex(0)
        host.findChild(QPushButton,"bTaskConfigCh").click()
        assert win.original_root_tabs.currentIndex()==1
        win.original_root_tabs.setCurrentIndex(0)
        host.findChild(QPushButton,"bTaskView").click()
        assert win.original_root_tabs.currentIndex()==5

        # No network action is allowed without an explicit operator step.
        win.original_root_tabs.setCurrentIndex(0)
        called=[]
        monkeypatch.setattr(win,"open_native_capture",
                            lambda:called.append("show consent-only dialog"))
        ip.setText("bad.device.name")
        assert not controller.open_capture_dialog()
        assert called==[]
        ip.setText("192.168.1.84")
        assert controller.open_capture_dialog()
        assert called==["show consent-only dialog"]
        assert controller.workspace.device_ipv4=="192.168.1.84"
        assert not controller.workspace.report()["network_scan_performed"]
    finally:
        win.close()
        qt_app.processEvents()


def test_original_start_directory_real_native_open_to_all_connected_pages(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    lib=tmp_path/"operator_library"
    lib.mkdir()
    archive=fixture_zip(lib,sample_count=4096)
    original_hash=sha256(archive.read_bytes()).hexdigest()
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.original_root_tabs.setCurrentIndex(0)
        start=win.original_start_controller
        start.set_library(lib)
        qt_app.processEvents()
        assert start.workspace.directory()==lib
        assert start.library_edit.text()==str(lib)
        items=start.library_files
        choices=[items.item(i).data(Qt.UserRole)
                 for i in range(items.count())]
        assert archive.name in choices
        assert start.open_selected.isEnabled() is False
        items.setCurrentRow(choices.index(archive.name))
        assert start.open_selected.isEnabled()
        assert start.open_selected_file()
        assert win.session is not None
        assert win.session.serial
        assert win.original_root_tabs.currentIndex()==5
        assert win.original_shell.file_channels.count()==10
        assert win.original_shell.status_table.rowCount()>=1
        assert sha256(archive.read_bytes()).hexdigest()==original_hash
        assert "Открыта проверенная" in start.status.text()
    finally:
        win.close()
        qt_app.processEvents()


def test_original_status_four_real_grids_15_tabs_43_source_bars_csv(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    archive=fixture_zip(tmp_path,sample_count=4096)
    original_sha=sha256(archive.read_bytes()).hexdigest()
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(archive)
        win.original_root_tabs.setCurrentIndex(2)
        qt_app.processEvents()
        ui=win.original_shell
        assert ui.status_page.objectName()=="PageStatus"
        assert ui.status_tabs.objectName()=="tcStatus"
        assert ui.status_tabs.count()==15
        assert ui.status_plot.objectName()=="chResult"
        assert ui.status_splitter.objectName()=="splResult"
        assert ui.status_grid_stack.objectName()=="OriginalPageStatusGrids"
        assert ui.status_grid_stack.count()==4
        for name in ORIGINAL_STATUS_GRIDS:
            grid=ui.status_page.findChild(QTableWidget,name)
            assert grid is not None
            assert ui.status_grids[name] is grid
            assert grid.editTriggers()==QTableWidget.NoEditTriggers
        for mode in range(15):
            ui.status_tabs.setCurrentIndex(mode)
            qt_app.processEvents()
            assert win.original_status_mode.currentIndex()==mode
            assert ui.status_table.objectName()==MODE_GRID[mode]
            assert ui.status_grid_stack.currentWidget() is ui.status_table
            assert ui.status_table.rowCount()>0
            assert (ui.status_plot.isVisible() if 5<=mode<=12 else
                    not ui.status_plot.isVisible())
            assert len([g for g in ui.status_grids.values()
                        if g.rowCount()>0])==1
            if mode==5:
                assert ui.status_table.rowCount()==43
                assert ui._source_status_projection.chart_visible
                cursor=ui._source_status_projection.cursor(0)
                assert cursor["adc"]==1
                assert cursor["nominal_hz_float32"]>0
                capture_synthetic_ui_if_requested(
                    win,qt_app,"28_bu_page_status_four_grid_43_band_chart")
            if mode==1:
                assert ui.status_table.rowCount()==24
                capture_synthetic_ui_if_requested(
                    win,qt_app,"29_bu_page_status_alarm_eight_adc_unknown")
        ui.status_tabs.setCurrentIndex(5)
        qt_app.processEvents()
        assert ui.status_export.isEnabled()
        dest=tmp_path/"status-source.csv"
        monkeypatch.setattr(
            QFileDialog,"getSaveFileName",
            staticmethod(lambda *a,**k:(str(dest),"CSV")))
        ui.status_export.click()
        assert dest.exists()
        with dest.open(encoding="utf-8-sig",newline="") as f:
            lines=list(csv.reader(f,delimiter=";"))
        assert len(lines)==44
        assert ui.status_table.rowCount()==43
        assert sha256(archive.read_bytes()).hexdigest()==original_sha
        assert "SHA256" in ui.status_note.text()
        assert ui._source_status_projection.receipt()["device_io_performed"] is False
    finally:
        win.close()
        qt_app.processEvents()


def test_original_status_bin_source_has_unknown_no_fabricated_chart(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    source,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(source)
        assert isinstance(win.session,DirectBinSession)
        win.original_root_tabs.setCurrentIndex(2)
        qt_app.processEvents()
        ui=win.original_shell
        for mode in (0,1,5,13,14):
            ui.status_tabs.setCurrentIndex(mode)
            qt_app.processEvents()
            assert not ui.status_plot.isVisible()
            assert not ui.status_export.isEnabled()
            assert not ui._source_status_projection.chart_visible
            assert ui.status_table.rowCount()>=1
            assert ui.status_table.objectName()==MODE_GRID[mode]
        assert source.is_file() and sidecar.is_file()
        capture_synthetic_ui_if_requested(
            win,qt_app,"30_bu_page_status_direct_bin_no_aux")
    finally:
        win.close()
        qt_app.processEvents()
