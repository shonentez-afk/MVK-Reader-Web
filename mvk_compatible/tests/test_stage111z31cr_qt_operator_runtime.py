"""Stage111Z31CR Qt: original five connected tabs, 15-mode System status,
direct BIN common dialog, readonly live status and invisible research UI.

Synthetic BIN/TSXML and bounded synthetic transport only. NO device I/O.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog,QTableWidget,QLabel

from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from .test_stage111z31cr_connected_core import source_test_transport
from ..desktop.main_window import MainWindow
from ..core.direct_bin_session import DirectBinSession
from ..core.original_connected_status import SYSTEM_STATUS_KEYS,UNKNOWN
from ..core.original_pagestatus_source import ORIGINAL_OPERATOR_STATUS_TABS
from ..core.original_runtime_tabs import (
    ORIGINAL_ARCHIVE_VISIBLE,ORIGINAL_LIVE_VISIBLE,
)


def _snap(win,phase):
    base=os.environ.get("MVK_SOURCE_OPERATOR_QA_DIR")
    if not base:return
    folder=Path(base)
    folder.mkdir(parents=True,exist_ok=True)
    png=folder/(phase+".png")
    img=win.grab()
    assert img.save(str(png),"PNG")
    r=win.original_visual_skin.snapshot()
    payload={
        "source":"STAGE111Z31CR_SYNTHETIC_NATIVE_QT_ORIGINAL",
        "state":phase,"original_user_screenshot_embedded":False,
        "operator_original_pixel_parity_proven":False,
        "device_io":False,
        "size_logical":[win.width(),win.height()],
        "size_physical":[img.width(),img.height()],
        "dpr":win.devicePixelRatioF(),
        "visible_source_pages":r["visible_source_tabs"],
        "system_verification":"unknown if direct BIN/live Go transport",
        "developer_shortcut_installed":r["developer_ui_shortcut_installed"],
    }
    (folder/(phase+".json")).write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")


def test_original_task_bin_dialog_cancel_then_real_direct_bin_to_three_tabs(
        qt_app,monkeypatch,tmp_path):
    source,sidecar,_=_make_pair(tmp_path,adc=4,n=8192,fs=65536)
    before=sha256(source.read_bytes()).hexdigest()
    calls=[]
    win=MainWindow()
    win.show()
    settle(qt_app)
    try:
        assert win.windowTitle()=="ТПО МВК 1.0.47"
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart"]
        assert not win.original_visual_skin.snapshot()[
            "developer_ui_shortcut_installed"]
        assert win.original_visual_skin.toggle_action.shortcut().toString()==""
        assert all(a.shortcut().toString()!="Ctrl+D" for a in win.actions())
        assert all(a.shortcut().toString()!="F12" for a in win.actions())
        def select_file(*args,**kw):
            calls.append(args)
            return ("","") if len(calls)==1 else (str(source),"")
        monkeypatch.setattr(QFileDialog,"getOpenFileName",select_file)
        start=win.original_start_controller
        QTest.mouseClick(start.buttons["bTaskView"],Qt.LeftButton)
        settle(qt_app)
        assert len(calls)==1
        assert "Двоичные файлы временного сигнала" in calls[0][3]
        assert win.session is None
        assert win.original_root_tabs.currentIndex()==0
        QTest.mouseClick(start.buttons["bTaskView"],Qt.LeftButton)
        settle(qt_app)
        assert len(calls)==2
        assert isinstance(win.session,DirectBinSession)
        assert win.adc.currentIndex()==3
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==list(ORIGINAL_ARCHIVE_VISIBLE)
        assert win._full_spectrum is not None
        assert win._spectrum_summary is not None
        assert sha256(source.read_bytes()).hexdigest()==before
        assert sidecar.is_file()
        assert not win.original_measure_controls.panel.isVisible()
        _snap(win,"10_cr_after_real_bin_button")
    finally:
        win.close()
        settle(qt_app)


def test_original_connected_five_pages_system_grid_and_live_status_integrity(
        qt_app):
    win=MainWindow()
    win.resize(1260,755)
    win.show()
    settle(qt_app)
    try:
        win._begin_live_capture()  # programmatic synthetic transition only
        settle(qt_app)
        assert win._live_active
        snap=win.original_visual_skin.snapshot()
        assert snap["visible_source_tabs"]==list(ORIGINAL_LIVE_VISIBLE)
        assert not snap["developer_ui_shortcut_installed"]
        assert not snap["technical"]
        assert not snap["menu_visible"]
        assert not snap["statusbar_visible"]
        assert win.original_measure_controls.panel.isVisible()
        assert win.original_measure_controls.freeze.isEnabled()
        assert win.original_measure_controls.freeze.text()=="Пауза приема"
        assert not win.original_measure_controls.buttons["bWriteTable"].isEnabled()
        assert not win.original_measure_controls.buttons["bWriteAdc"].isEnabled()
        assert not win.original_measure_controls.buttons["bWriteValues"].isEnabled()
        assert win.original_measure_controls.rate.text()=="ЧД —"
        assert win.original_measure_controls.status.text()=="Ожидание данных прибора"
        assert not win.original_shell.status_export.isVisible()
        assert not win.original_shell.status_note.isVisible()
        assert not win.original_shell.file_page.findChild(
            QLabel,"sourceFileSummary").isVisible()
        win.original_root_tabs.setCurrentIndex(2)
        settle(qt_app)
        shell=win.original_shell
        assert shell.status_tabs.count()==15
        assert tuple(shell.status_tabs.tabText(i) for i in range(15))==(
            ORIGINAL_OPERATOR_STATUS_TABS)
        assert shell.status_table.objectName()=="tabStatus"
        assert shell.status_table.horizontalHeaderItem(0).text()==(
            "Наименование параметра")
        assert shell.status_table.horizontalHeaderItem(1).text()=="Значение"
        assert shell.status_table.rowCount()==15
        for i,(_,label) in enumerate(SYSTEM_STATUS_KEYS):
            assert shell.status_table.item(i,0).text()==label
            assert shell.status_table.item(i,1).text()==UNKNOWN
        assert not shell.status_plot.isVisible()
        assert not shell.status_page.property("sourceNativeTransportConnected")
        _snap(win,"11_cr_original_connected_system_unknown")
        proof=source_test_transport(frames=400)
        win._receive_native_live_status(proof)
        settle(qt_app)
        assert shell.status_page.property("sourceNativeTransportConnected")
        assert win.original_measure_controls.status.text()==(
            "Подключен к прибору")
        assert win.original_measure_controls.indicator.text()=="●"
        assert shell.status_table.item(10,1).text()==UNKNOWN
        assert shell.status_table.item(11,1).text()==UNKNOWN
        assert shell.status_table.item(5,1).text()==UNKNOWN
        _snap(win,"12_cr_readonly_connected_15_system_rows")
        # All 15 original operator tabs must be selectable, not a display
        # mock. Without verified per-mode DSP, no synthetic values injected.
        for i in range(15):
            shell.status_tabs.setCurrentIndex(i)
            settle(qt_app)
            assert win.original_status_mode.currentIndex()==i
            assert shell.status_table.rowCount()>0
        shell.status_tabs.setCurrentIndex(0)
        settle(qt_app)
        win._receive_native_live_status(
            source_test_transport(frames=401,stale=True))
        assert win.original_measure_controls.status.text()==(
            "Ожидание данных прибора")
        assert not shell.status_page.property("sourceNativeTransportConnected")
        win._invalidate_native_live_status("synthetic no status")
        assert win._native_live_status is None
        win.original_root_tabs.setCurrentIndex(5)
        settle(qt_app)
        assert win.original_shell.file_page.isVisible()
        assert win.original_shell.file_action_tabs.count()==2
        assert not win.original_shell.file_page.findChild(
            QLabel,"sourceFileEvidence").isVisible()
        win._end_live_capture(False)
        settle(qt_app)
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==list(ORIGINAL_LIVE_VISIBLE)
        assert win._measurement_mode_selected
        assert win.original_measure_controls.state.mode=="idle"
        assert win.original_measure_controls.panel.isVisible()
        assert win.original_measure_controls.bad_indicator.isVisible()
        assert win.leave_measurement_mode()
        settle(qt_app)
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart"]
        assert not win.original_measure_controls.panel.isVisible()
    finally:
        win.close()
        settle(qt_app)
