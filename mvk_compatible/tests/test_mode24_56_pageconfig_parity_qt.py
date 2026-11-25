"""Actual offline buttons on PageStart/PageConfig; no native process or TCP."""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from .test_desktop_qt import qt_app
from ..core.original_config_readonly import inspect_original_local_config


def _dialog(callback):
    # Timer executes inside the real Qt modal. On a failing expectation,
    # reject first so the surrounding test terminates instead of hanging.
    results=[]
    def run():
        dlg=QApplication.activeModalWidget()
        if dlg is None:
            results.append(AssertionError("Expected original modal"))
            return
        try:
            results.append(callback(dlg))
        except BaseException as exc:
            results.append(exc)
            dlg.reject()
    QTimer.singleShot(20,run)
    return results


def _check(results):
    assert len(results)==1
    if isinstance(results[0],BaseException):
        raise results[0]
    return results[0]


def _input(tmp_path):
    p=tmp_path/"candidate.txt"
    p.write_text("0x000A w:502\n0x000C h:00000000\n0x0020 f:2.5\n"
                 "+0x0100\n0x0002 f:0.01019\n0x0060 h:00000000\n"
                 "+0x0900\n0x0008 h:00000000\n",encoding="utf-8")
    return p


def _task(window,button,app):
    window.original_root_tabs.setCurrentIndex(0)
    app.processEvents()
    action=window.original_start_controller.buttons[button]
    assert action.isVisible()
    QTest.mouseClick(action,Qt.LeftButton)
    app.processEvents()
    assert window.original_root_tabs.tabData(
        window.original_root_tabs.currentIndex())=="PageConfig"
    return window.original_config_panel


def _open_file(panel,path,monkeypatch):
    monkeypatch.setattr(QFileDialog,"getOpenFileName",
                        lambda *_:(str(path),"*.txt"))
    QTest.mouseClick(panel.load_button,Qt.LeftButton)
    assert panel.workspace is not None


def _enter(grid,row,col):
    grid.setCurrentCell(row,col)
    grid.setFocus()
    QTest.keyClick(grid,Qt.Key_Return)


def test_start_settings_enter_enum_channel_tach_and_local_reset(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    from ..desktop import original_config_readonly_ui as mod
    w=MainWindow()
    w.resize(1200,830)
    w.show()
    qt_app.processEvents()
    try:
        source=_input(tmp_path)
        before=source.read_bytes()
        panel=_task(w,"bTaskConfigIP",qt_app)
        assert w.original_root_tabs.tabText(1)=="Системные параметры"
        _open_file(panel,source,monkeypatch)

        def choose_endian(dlg):
            assert dlg.objectName()=="mvkeditform"
            assert dlg.cbVal.isVisible() and not dlg.edVal.isVisible()
            assert dlg.cbVal.count()==3 and dlg.cbVal.currentRow()==0
            dlg.cbVal.setCurrentRow(1)
            QTest.mouseClick(dlg.bOk,Qt.LeftButton)
        result=_dialog(choose_endian)
        _enter(panel.basic_table,4,3)
        _check(result)
        assert panel.document.value(0x0C).literal=="0x99999999"
        assert panel.workspace.changed_count==1

        panel=_task(w,"bTaskConfigCh",qt_app)
        assert w.original_root_tabs.tabText(1)=="Параметры измерительных каналов"
        assert panel.channel_table.rowCount()==10
        assert panel.channel_table.item(8,0).text()=="TACH1"
        assert panel.channel_table.item(9,0).text()=="TACH2"

        def convert_sensitivity(dlg):
            assert dlg.bRecalc.isVisible()
            dlg.edVal.setText("100")
            QTest.mouseClick(dlg.bRecalc,Qt.LeftButton)
            assert dlg.source_recalc_receipt is not None
            selected=dlg.edVal.text()
            QTest.mouseClick(dlg.bOk,Qt.LeftButton)
            return selected
        result=_dialog(convert_sensitivity)
        _enter(panel.channel_fields,0,3)
        assert panel.document.value(0x102).literal==_check(result)

        _enter(panel.channel_table,8,0)
        assert panel.channel_fields.rowCount()==3
        assert panel.channel_fields.item(0,1).text()=="0x0908"
        def choose_tach(dlg):
            assert dlg.cbVal.isVisible() and dlg.cbVal.count()==2
            dlg.cbVal.setCurrentRow(1)
            QTest.mouseClick(dlg.bOk,Qt.LeftButton)
        result=_dialog(choose_tach)
        _enter(panel.channel_fields,0,3)
        _check(result)
        assert panel.document.value(0x908).literal=="0x00000001"
        panel.page_tabs.setCurrentIndex(1)
        def choose_alarm(dlg):
            assert dlg.cbVal.isVisible() and dlg.cbVal.count()==119
            dlg.cbVal.setCurrentRow(5)
            QTest.mouseClick(dlg.bOk,Qt.LeftButton)
        result=_dialog(choose_alarm)
        _enter(panel.alarm_table,0,3)
        _check(result)
        assert panel.document.value(0x160).literal=="0x00000032"
        assert source.read_bytes()==before

        defaults=tmp_path/"DefaultConfig.txt"
        defaults.write_text("0x000A w:504\n",encoding="utf-8")
        monkeypatch.setattr(mod,"source_original_default_config_path",lambda:defaults)
        panel=_task(w,"bTaskConfigIP",qt_app)
        result=_dialog(lambda d:QTest.mouseClick(d.bNo,Qt.LeftButton))
        QTest.mouseClick(panel.reset_button,Qt.LeftButton)
        _check(result)
        assert panel.document.value(0x0A).formatted=="w:502"
        result=_dialog(lambda d:QTest.mouseClick(d.bYes,Qt.LeftButton))
        QTest.mouseClick(panel.reset_button,Qt.LeftButton)
        _check(result)
        assert panel.document.value(0x0A).formatted=="w:504"
        assert panel.workspace.changed_count==0
        assert "Прибор не опрашивался" in panel.source_note.text()
        assert source.read_bytes()==before
        assert defaults.read_bytes()==b"0x000A w:504\n"
        assert not panel.upload_button.isEnabled()
        assert not w._live_active and not w._measurement_mode_selected
    finally:
        w.close()
        qt_app.processEvents()


def test_save_scope_releases_only_saved_edit_and_new_ip_clears_task0(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    from ..desktop import original_task0_download_dialog as mod
    w=MainWindow()
    w.resize(1200,830)
    w.show()
    qt_app.processEvents()
    callbacks={}
    class Signal:
        def __init__(self,name):
            self.name=name
        def connect(self,fn):
            callbacks[self.name]=fn
    class Task0:
        readStarted=Signal("start")
        readCompleted=Signal("complete")
        readFailed=Signal("failed")
        _mode=None
        def __init__(self,device_ip,owner):
            self._open=False
        def show(self):
            self._open=True
        def isVisible(self):
            return self._open
        def invalidate_device_ip(self):
            self._open=False
    monkeypatch.setattr(mod,"OriginalTask0DownloadDialog",Task0)
    try:
        source=_input(tmp_path)
        panel=_task(w,"bTaskConfigIP",qt_app)
        start=w.original_start_controller
        _open_file(panel,source,monkeypatch)
        panel.edit_local_field("ip",3,"503")
        target=tmp_path/"mode4_saved.txt"
        monkeypatch.setattr(QFileDialog,"getSaveFileName",
                           lambda *_:(str(target),"*.txt"))
        QTest.mouseClick(panel.save_button,Qt.LeftButton)
        assert set(x.address for x in inspect_original_local_config(target).cells)=={0x0A,0x0C}
        assert not panel.workspace.changed and not panel.discard_button.isEnabled()
        assert target.read_bytes().count(b"\r\n")==4
        QTest.mouseClick(panel.download_button,Qt.LeftButton)
        assert callbacks.keys()=={"start","complete","failed"}
        assert panel._task0_dialog.isVisible()
        # Validated synthetic proof fixture, not a real device operation.
        proof={
            "schema":"MVK_SOURCE_TASK0_CONFIG_IP_READ_V1",
            "source_original_task":0,"read_only":True,"device_commands_sent":False,
            "original_delphi_byte_parity_verified":False,
            "device_ipv4":start.workspace.device_ipv4,"confirmed_fields":1,
            "fields":{"ConfigIP":{"valid":True,"raw_hex_le":"01020304"}},
        }
        callbacks["complete"](proof)
        assert panel.basic_table.item(0,3).text()=="4.3.2.1"
        w.original_root_tabs.setCurrentIndex(0)
        start.ip_edit.setText("192.0.2.88")
        QTest.keyClick(start.ip_edit,Qt.Key_Return)
        assert start.workspace.device_ipv4=="192.0.2.88"
        assert panel._task0_receipt is None
        assert panel.basic_table.item(0,3).text()=="—"
        assert "предыдущего прибора" in panel.source_note.text()
        # A late old callback is ignored even if the operator switches back.
        start.ip_edit.setText(proof["device_ipv4"])
        QTest.keyClick(start.ip_edit,Qt.Key_Return)
        callbacks["complete"](proof)
        assert panel._task0_receipt is None
        assert not panel._task0_dialog.isVisible()
    finally:
        w.close()
        qt_app.processEvents()


def test_reset_cannot_replace_workspace_while_task0_running(
        qt_app,monkeypatch,tmp_path):
    from types import SimpleNamespace
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();qt_app.processEvents()
    try:
        panel=_task(w,"bTaskConfigIP",qt_app)
        _open_file(panel,_input(tmp_path),monkeypatch)
        panel._task0_dialog=SimpleNamespace(_mode="read")
        captured=[]
        monkeypatch.setattr(w.original_window_man,"spawn_error",captured.append)
        workspace=panel.workspace
        QTest.mouseClick(panel.reset_button,Qt.LeftButton)
        assert panel.workspace is workspace
        assert w.original_start_controller.open_config_mode(6) is False
        assert panel.source_mode==4
        assert captured==["Сначала завершите чтение Task0."]
        with pytest.raises(ValueError,match="завершите чтение Task0"):
            panel.load_local_file(tmp_path/"candidate.txt")
        with pytest.raises(ValueError,match="завершите чтение Task0"):
            panel.edit_local_field("ip",3,"503")
        with pytest.raises(ValueError,match="завершите чтение Task0"):
            panel.save_local_file(tmp_path/"invalid_while_busy.txt")
        assert not panel.upload_button.isEnabled()
    finally:
        panel._task0_dialog=None
        w.close()
        qt_app.processEvents()
