"""Stage111Z31CO: native operator pointer access after source DFM scrolling.

A real synthetic BIN/TSXML is opened through DirectBinSession. The test
checks that mouse clicks are NOT dispatched into a clipped button; source
TabOrder matches private Delphi DFM, and the full Core FFT is immutable.
No hardware, private original images or user data.
"""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget
from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..core.direct_bin_session import DirectBinSession
from ..core.original_ui_form_contract import (
    ORIGINAL_SPECTRUM_TAB_ORDER, ORIGINAL_WAVE_TAB_ORDER,
    ORIGINAL_SPECTRUM_CONTROLS)
from ..desktop.main_window import MainWindow


def _hash(values):
    return sha256(np.asarray(values,dtype="<f4").tobytes()).hexdigest()


def _visible_pointer(win,button):
    pane=win.spec_tools
    point=button.rect().center()
    mapped=button.mapTo(pane.viewport(),point)
    assert pane.viewport().rect().contains(mapped), (
        button.objectName(),mapped,pane.viewport().rect())
    # The Qt viewport owns clipping. Recursively hit-test its REAL visible
    # child, which detects overlap by a QLabel/another widget and a button
    # outside its QScrollArea even on noninteractive Windows CI desktops.
    target=pane.viewport().childAt(mapped)
    assert target is button or (
        target is not None and button.isAncestorOf(target)), (
        button.objectName(),target.objectName() if target else "no Qt hit")
    if sys.platform=="win32" and os.environ.get("QT_QPA_PLATFORM")=="windows":
        # GitHub-hosted Windows agents have a noninteractive desktop; Win32
        # global QApplication.widgetAt() may report None despite an actually
        # visible, pointer-clickable Qt viewport. If it gives a result,
        # require consistency. A null OS-global hit is not a Qt click fail.
        global_hit=QApplication.widgetAt(button.mapToGlobal(point))
        if global_hit is not None:
            assert global_hit is button or button.isAncestorOf(global_hit)
        win.setProperty("sourceNativeGlobalHitAvailable",global_hit is not None)


def _capture(win,name,digest):
    directory=os.environ.get("MVK_SOURCE_OPERATOR_QA_DIR")
    if not directory:
        return
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    screen=win.grab()
    assert screen.save(str(directory/(name+".png")),"PNG")
    assert _hash(win._full_spectrum["amplitude"])==digest
    scroll=win.spec_tools.verticalScrollBar()
    report={
        "source":"STAGE111Z31CO_SYNTHETIC_COMPACT_POINTER_QA",
        "phase":name,"device_used":False,
        "source_original_win32_1to1_verified":False,
        "logical_size":[win.width(),win.height()],
        "physical_size":[screen.width(),screen.height()],
        "dpi":win.devicePixelRatioF(),
        "sidebar_width":win.spec_tools.width(),
        "scroll_position":scroll.value(),"scroll_maximum":scroll.maximum(),
        "source_tab_order":win.spec_source_canvas.property("originalDfmTabOrder"),
        "full_fft_sha256":digest}
    (directory/(name+".json")).write_text(
        json.dumps(report,ensure_ascii=False,indent=2,default=str)+"\n",
        encoding="utf-8")


def _popup_via_pointer(button,menu,qt_app):
    shown=[]
    def on_show():
        shown.append(True)
        QTimer.singleShot(0,menu.hide)
    menu.aboutToShow.connect(on_show)
    try:
        QTest.mouseClick(button,Qt.LeftButton)
        settle(qt_app)
        assert shown,button.objectName()
    finally:
        menu.aboutToShow.disconnect(on_show)
        menu.hide()


def test_real_compact_operator_viewport_pointers_original_taborder_and_fft(
        tmp_path,qt_app,monkeypatch):
    path,_,original=_make_pair(tmp_path,adc=4,n=65536,fs=65536)
    original_bits=original.view("<u4").copy()
    win=MainWindow()
    try:
        win.resize(960,580)
        win.show()
        settle(qt_app)
        win.open_archive(path)
        win.original_root_tabs.setCurrentIndex(4)
        settle(qt_app)
        assert isinstance(win.session,DirectBinSession)
        assert win.spec_tools.width()==177
        assert tuple(win.spec_source_canvas.property(
            "originalDfmTabOrder"))==ORIGINAL_SPECTRUM_TAB_ORDER
        assert tuple(win.wave_source_canvas.property(
            "originalDfmTabOrder"))==ORIGINAL_WAVE_TAB_ORDER
        for i,name in enumerate(ORIGINAL_SPECTRUM_TAB_ORDER):
            widget=next(widget for widget in
                win.spec_source_canvas.findChildren(QWidget)
                if widget.property("originalDfmControlName")==name)
            assert widget.property("originalDfmTabOrder")==i
        for name,_,x,y,width,height in ORIGINAL_SPECTRUM_CONTROLS:
            widget=next(widget for widget in
                win.spec_source_canvas.findChildren(QWidget)
                if widget.property("originalDfmControlName")==name)
            assert tuple(widget.property("originalDfmLogicalRect"))==(
                x,y,width,height)
        assert win._full_spectrum["n_fft"]==65536
        assert len(win._full_spectrum["amplitude"])==32768
        digest=_hash(win._full_spectrum["amplitude"])
        summary=dict(win._spectrum_summary)
        scroll=win.spec_tools.verticalScrollBar()
        assert scroll.maximum()>0
        _capture(win,"05_compact_top",digest)

        # Genuine wheel input on the operator QScrollArea viewport.
        viewport=win.spec_tools.viewport()
        center=viewport.rect().center()
        for _ in range(10):
            ev=QWheelEvent(QPointF(center),
                QPointF(viewport.mapToGlobal(center)),
                QPoint(0,0),QPoint(0,-120),Qt.NoButton,
                Qt.NoModifier,Qt.ScrollUpdate,False)
            QCoreApplication.sendEvent(viewport,ev)
        settle(qt_app)
        assert scroll.value()>0
        _capture(win,"06_wheel_scrolled",digest)

        # Keyboard TabOrder FocusIn auto-scrolls actual DFM Save into view.
        scroll.setValue(0)
        win.spec_save_button.setFocus(Qt.TabFocusReason)
        settle(qt_app)
        assert scroll.value()>0
        _visible_pointer(win,win.spec_save_button)
        assert win.spec_source_canvas.property(
            "sourceDfmFocusRevealedInViewport") is True
        _capture(win,"07_save_focus_visible",digest)

        monkeypatch.setattr(
            QMessageBox,"question",lambda *a,**kw:QMessageBox.Yes)
        win.spec_copy_button.setFocus(Qt.TabFocusReason)
        settle(qt_app)
        _visible_pointer(win,win.spec_copy_button)
        QTest.mouseClick(win.spec_copy_button,Qt.LeftButton)
        clipboard=QApplication.clipboard().text()
        assert "НЕ КАЛИБРОВАНО" in clipboard
        assert len(clipboard.strip().splitlines()[-1].split("\t"))==3
        target=tmp_path/"co_pointer_uncalibrated.csv"
        monkeypatch.setattr(
            QFileDialog,"getSaveFileName",
            lambda *a,**kw:(str(target),"CSV (*.csv)"))
        win.spec_save_button.setFocus(Qt.TabFocusReason)
        settle(qt_app)
        _visible_pointer(win,win.spec_save_button)
        QTest.mouseClick(win.spec_save_button,Qt.LeftButton)
        saved=target.read_text(encoding="utf-8")
        assert "НЕ КАЛИБРОВАНО" in saved and "sep=|" in saved
        assert len(saved.splitlines()[-1].split("|"))==3

        # Source Delphi focus order: Type→Lines→H→V→Copy→Save→Envelope.
        buttons=[win.spec_type_button,win.spec_lines_button,
            win.spec_hscale_button,win.spec_vscale_button,
            win.spec_copy_button,win.spec_save_button,
            win.spec_envelope_button]
        buttons[0].setFocus(Qt.TabFocusReason)
        settle(qt_app)
        for before,after in zip(buttons,buttons[1:]):
            assert QApplication.focusWidget() is before
            QTest.keyClick(before,Qt.Key_Tab)
            settle(qt_app)
            assert QApplication.focusWidget() is after,(
                before.objectName(),QApplication.focusWidget())
            _visible_pointer(win,after)
        assert scroll.value()==0

        # A physical body-click opens the source popup; it cannot silently
        # cycle scales. Explicit selection changes ONLY the view.
        for button,menu in (
                (win.spec_hscale_button,win.spec_hscale_menu),
                (win.spec_vscale_button,win.spec_vscale_menu)):
            button.setFocus(Qt.TabFocusReason)
            settle(qt_app)
            _visible_pointer(win,button)
            ranges=[tuple(pair) for pair in
                win.spec_plot.getViewBox().viewRange()]
            _popup_via_pointer(button,menu,qt_app)
            assert [tuple(pair) for pair in
                win.spec_plot.getViewBox().viewRange()]==ranges
            assert _hash(win._full_spectrum["amplitude"])==digest
        win._spec_vscale_actions[2].trigger()
        settle(qt_app)
        assert win._spec_original_vscale_tag==2
        vb=win.spec_plot.getViewBox()
        vb.setXRange(120.,140.,padding=0)
        settle(qt_app)
        assert win._archive_source_projection_model[
            "draw_mode"]=="original_samples_when_sparse"
        win._spec_at_scene_pos(
            vb.mapViewToScene(QPointF(128.,-130.)),force=True)
        assert win._spec_last_cursor is not None
        assert abs(win._spec_last_cursor["frequency_hz"]-128.)<=2.
        vb.setXRange(0.,25600.,padding=0)
        settle(qt_app)
        assert win._archive_source_projection_model[
            "draw_mode"]=="original_pixel_column_minmax"
        assert _hash(win._full_spectrum["amplitude"])==digest
        assert win._spectrum_summary==summary
        np.testing.assert_array_equal(
            win.session.samples(4)[0].view("<u4"),original_bits)

        # Leave/reenter the original page: top controls must be visible.
        scroll.setValue(scroll.maximum())
        win.original_root_tabs.setCurrentIndex(3)
        settle(qt_app)
        win.original_root_tabs.setCurrentIndex(4)
        settle(qt_app)
        assert scroll.value()==0
        _visible_pointer(win,win.spec_type_button)
        _capture(win,"08_return_source_top",digest)
    finally:
        win.close()
        settle(qt_app)


def test_original_tab_order_rejects_invalid_duplicate(qt_app):
    from PySide6.QtWidgets import QPushButton,QLabel
    from ..desktop.source_control_canvas import SourceControlCanvas
    owner=QWidget()
    try:
        spec=(("a","TButton",9,9,25,20),("b","TButton",9,35,25,20),
              ("label","TLabel",9,58,25,20))
        bindings={"a":QPushButton(owner),"b":QPushButton(owner),
                  "label":QLabel(owner)}
        with pytest.raises(ValueError,match="TabOrder"):
            SourceControlCanvas(owner,spec,bindings,"invalid",
                tab_order=("a","a"))
    finally:
        owner.close()
