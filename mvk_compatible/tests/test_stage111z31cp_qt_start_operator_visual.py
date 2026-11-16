"""Stage111Z31CP: user-supplied original no-measurement Tasks visual
mapped to actual clickable Qt source command buttons + safe Core modes.

This is a behavioral and bounded geometry/colors acceptance, NOT bitmap
pixel parity with MVKView 1.0.47; the original screenshot is kept private.
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
from PySide6.QtWidgets import QLabel,QPushButton,QLineEdit

from .test_desktop_qt import qt_app
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..core.original_start_workbench import (
    START_BUTTONS,START_OPERATOR_CAPTIONS,START_OPERATOR_REFERENCE,
    START_OPERATOR_IP_LABEL,START_OPERATOR_LIBRARY_LABEL,
    START_IP_DEFAULT,START_LIBRARY_DEFAULT,
)
from ..desktop.source_start_command import SourceStartCommandButton
from ..desktop.main_window import MainWindow

OPERATOR_REFERENCE="ORIGINAL_IDLE_TASKS_2026_11_16_REFERENCE_NO_IMAGE_IN_CI"


def _capture(host,win,phase):
    directory=os.environ.get("MVK_SOURCE_OPERATOR_QA_DIR")
    if not directory:
        return
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    png=directory/(phase+".png")
    img=win.grab()
    assert img.save(str(png),"PNG")
    rects={
        name:list(win.original_start_controller.buttons[name].geometry().getRect())
        for name,*_ in START_BUTTONS
    }
    payload={
        "source":OPERATOR_REFERENCE,
        "operator_comparison_image_used":False,
        "vendor_original_assets_embedded":False,
        "original_win32_same_resolution_pixel_parity_verified":False,
        "phase":phase,
        "dpi":win.devicePixelRatioF(),
        "window_logical":[win.width(),win.height()],
        "image_physical":[img.width(),img.height()],
        "visible_root_pages":win.original_visual_skin.snapshot()["visible_source_tabs"],
        "source_button_geometry":rects,
        "source_button_titles":{
            name:win.original_start_controller.buttons[name].text()
            for name,*_ in START_BUTTONS},
        "logo_actual_y":host.logo.y(),
        "logo_source_rect":host.logo.property("originalDfmLogicalRect"),
        "background_procedural_blue_fallback":not host.original_pictures_loaded_privately,
        "device_command_issued":False,
    }
    (directory/(phase+".json")).write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",
        encoding="utf-8")


def test_real_empty_original_start_look_and_clickable_core_modes(
        qt_app,monkeypatch):
    win=MainWindow()
    try:
        win.resize(1280,760)
        win.show()
        settle(qt_app)
        start=win.original_start_controller
        host=start.host
        assert start.workspace.report()["device_io_performed"] is False
        assert start.workspace.report()["network_scan_performed"] is False
        assert win.session is None and not win._live_active
        assert win.original_visual_skin.snapshot()["visible_source_tabs"]==[
            "PageStart"]
        assert host.property("sourceTaskCaptionsReference")==START_OPERATOR_REFERENCE
        assert host.property("sourceBlueReferenceCandidate")
        assert not host.original_pictures_loaded_privately
        assert not host.property("sourceOperatorScreenshotPixelParityVerified")

        for name,x,y,width,height,image,tab,mode in START_BUTTONS:
            b=start.buttons[name]
            assert isinstance(b,QPushButton)
            assert isinstance(b,SourceStartCommandButton)
            assert b.geometry().getRect()==(x,y,width,height)
            assert b.property("originalDfmLogicalRect")==(
                x,y,width,height)
            assert b.property("originalHandlerMode")==mode
            assert b.text()==START_OPERATOR_CAPTIONS[name][0]
            assert b.source_note==START_OPERATOR_CAPTIONS[name][1]
            assert b.property("sourceTaskNoRaisedCardBorder") is True
            assert b.property("sourceOriginalCommandBitmapProvided") is False
            assert b.isFlat()
            assert not b.icon().isNull()
            assert b.isHidden() == (name=="bTaskConfigCalib")
        assert host.findChild(QLabel,"lbStartSourceIP").text()==(
            START_OPERATOR_IP_LABEL)
        assert host.findChild(QLabel,"lbStartLibrary").text()==(
            START_OPERATOR_LIBRARY_LABEL)
        assert host.findChild(QLineEdit,"edIpAddr").text()==START_IP_DEFAULT
        assert host.findChild(QLineEdit,"edLibraryPath").text()==(
            START_LIBRARY_DEFAULT)
        assert start.library_edit.isReadOnly()
        assert not start.workspace.report()["library_explicit"]
        assert host.logo.property("originalDfmLogicalRect")==(
            3,568,432,120)
        assert host.logo.y()==min(568,max(0,host.height()-120))
        assert not host.logo.pixmap().isNull()
        # Confirm that source operator screen is now CYAN rather than
        # amber without assuming exact original screenshot dimensions.
        preview=host.grab().toImage()
        background=preview.pixelColor(
            min(host.width()-2,int(host.width()*.85)),host.height()//2)
        assert background.blue()>background.red()+12, background
        _capture(host,win,"09_cp_idle_operator_blue_command_links")
        # REAL Qt mouse clicks on the original DFM command widgets.
        # Never connect the measurement-device TCP receiver implicitly.
        native_calls=[]
        monkeypatch.setattr(
            win,"open_native_capture",lambda:native_calls.append(
                "consent_only_dialog"))
        QTest.mouseClick(start.buttons["bTaskConfigIP"],Qt.LeftButton)
        settle(qt_app)
        assert win.original_config_panel.source_mode==4
        assert win.original_root_tabs.currentIndex()==1
        win.original_root_tabs.setCurrentIndex(0)
        settle(qt_app)
        QTest.mouseClick(start.buttons["bTaskConfigCh"],Qt.LeftButton)
        settle(qt_app)
        assert win.original_config_panel.source_mode==6
        win.original_root_tabs.setCurrentIndex(0)
        settle(qt_app)
        native_dialogs=[]
        monkeypatch.setattr(
            QFileDialog,"getOpenFileName",
            lambda *args,**kw:(native_dialogs.append(
                args[3]) or ("","")))
        QTest.mouseClick(start.buttons["bTaskView"],Qt.LeftButton)
        settle(qt_app)
        assert len(native_dialogs)==1
        assert native_dialogs[0].startswith(
            "Двоичные файлы временного сигнала")
        assert win.original_root_tabs.currentIndex()==0
        assert win.session is None
        win.original_root_tabs.setCurrentIndex(0)
        settle(qt_app)
        QTest.mouseClick(start.buttons["bTaskConnect"],Qt.LeftButton)
        settle(qt_app)
        assert native_calls==["consent_only_dialog"]
        assert win.session is None
        assert start.workspace.device_ipv4==START_IP_DEFAULT
        assert start.workspace.report()["device_io_performed"] is False
        assert start.workspace.report()["network_scan_performed"] is False
    finally:
        win.close()
        settle(qt_app)


def test_original_start_local_strings_are_exact_but_device_modes_unchanged():
    expected={
        "bTaskConnect":("Измерение","",2),
        "bTaskView":("Загрузка сигнала из файла","",1),
        "bTaskConfigCh":(
            "Настройка параметров измерительных каналов",
            "Коэффициенты передачи датчиков, частотные полосы и др.",6),
        "bTaskConfigIP":(
            "Настройка системных параметров",
            "IP-адрес, маска подсети, настройки Modbus/TCP",4),
        "bTaskConfigCalib":("Калибровка","",5),
    }
    for name,x,y,width,height,image,order,mode in START_BUTTONS:
        title,note,real_mode=expected[name]
        assert START_OPERATOR_CAPTIONS[name]==(title,note)
        assert mode==real_mode
