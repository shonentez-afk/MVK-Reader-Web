"""Original PageConfig Mode4: real bConfigDownloadClick Task0 Qt wiring.

All tests are synthetic QWidget events. They never start a Go process or
contact an industrial device; source JSON is verified separately in Core.
"""
from __future__ import annotations

from pathlib import Path
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QMessageBox
from .test_desktop_qt import qt_app


def test_source_page_config_download_is_a_real_task0_action(qt_app,monkeypatch):
    from ..desktop.main_window import MainWindow
    from ..desktop import original_task0_download_dialog as module
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    invoked=[]
    class SignalMock:
        def connect(self,fn):
            invoked.append(fn)
    class FakeTask0Dialog:
        readCompleted=SignalMock()
        def __init__(self,device_ip,parent):
            self.device_ip=device_ip
            invoked.append(("created",device_ip,parent))
        def isVisible(self):
            return False
        def show(self):
            invoked.append("shown")
    monkeypatch.setattr(module,"OriginalTask0DownloadDialog",FakeTask0Dialog)
    try:
        controller=win.original_start_controller
        assert controller.open_config_mode(4)==4
        panel=win.original_config_panel
        assert panel.source_mode==4
        assert panel.download_button.objectName()=="bConfigDownload"
        assert panel.download_button.isEnabled()
        for danger in (panel.upload_button,panel.reset_button):
            if danger is not None:assert not danger.isEnabled()
        assert panel.download_device_config()
        assert invoked[0][0]=="created"
        assert invoked[0][1]==controller.workspace.device_ipv4
        assert invoked[0][2] is win
        assert callable(invoked[1])
        assert invoked[2]=="shown"
        assert win.session is None
        assert not win._live_active
        assert not win._measurement_mode_selected
    finally:
        win.close()
        qt_app.processEvents()


def test_source_task0_proof_populates_existing_original_basic_grid(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.original_start_controller.open_config_mode(4)
        panel=win.original_config_panel
        current=win.original_start_controller.workspace.device_ipv4
        proof={
            "schema":"MVK_SOURCE_TASK0_CONFIG_IP_READ_V1",
            "source_original_task":0,
            "read_only":True,
            "device_commands_sent":False,
            "original_delphi_byte_parity_verified":False,
            "device_ipv4":current,
            "confirmed_fields":1,
            "fields":{
                "ConfigIP":{
                    "address":"0x0004",
                    "valid":True,
                    "raw_hex_le":"01020304",
                },
                "ConfigNetmask":{
                    "address":"0x0006",
                    "valid":False,
                    "raw_hex_le":None,
                },
            },
        }
        assert panel.apply_device_task0_read(proof)>0
        first=panel.basic_table.item(0,3)
        second=panel.basic_table.item(1,3)
        assert first.text()=="0x01020304"
        assert second.text()=="—"
        assert "Task0" in panel.source_note.text()
        assert panel.save_button.isEnabled() is False
        assert panel.upload_button is None or not panel.upload_button.isEnabled()
        assert panel.reset_button is None or not panel.reset_button.isEnabled()
        assert not win._live_active
        assert win.session is None
    finally:
        win.close()
        qt_app.processEvents()


def test_original_task0_modal_requires_explicit_consent_and_selected_eth(
        qt_app,monkeypatch,tmp_path):
    from ..desktop import original_task0_download_dialog as module
    monkeypatch.setattr(module,"native_executable",lambda:tmp_path/"native.exe")
    dlg=module.OriginalTask0DownloadDialog("192.168.0.30")
    try:
        assert dlg.download.isEnabled() is False
        assert dlg.confirm.isChecked() is False
        dlg.interfaces.addItem("ethernet loopback fixture","192.168.0.31")
        assert dlg.download.isEnabled() is False
        dlg.confirm.setChecked(True)
        assert dlg.download.isEnabled()
        asked=[]
        monkeypatch.setattr(
            QMessageBox,"question",
            lambda *a,**kw:(asked.append(True),QMessageBox.Yes)[1])
        class FakeProcess:
            started=None
            def state(self):return QProcess.NotRunning
            def start(self,path,args):self.started=(path,args)
        fake=FakeProcess()
        dlg._process=fake
        dlg.output_edit.setText(str(tmp_path))
        assert dlg.start_read()
        assert asked==[True]
        assert fake.started is not None
        argv=fake.started[1]
        assert "-source-task0-config-read=true" in argv
        assert "-approve=true" in argv and "-export=false" in argv
        assert not any("setrate" in x.lower() or "reboot" in x.lower()
                       for x in argv)
        assert dlg.confirm.isChecked() is False
        assert dlg.stop_read()
        assert (dlg._root/".mvk_stop_requested").read_text(
            encoding="ascii")=="STOP\n"
        dlg._mode=None
    finally:
        dlg.close()
        qt_app.processEvents()
