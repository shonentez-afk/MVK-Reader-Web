"""Exercise operator wheel and developer entry points without instrument I/O."""
import sys
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint,QPointF,Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from .test_desktop_qt import qt_app
from .test_mode1_saved_adc_spectrum_export_qt import _adc
from ..desktop.archive_entry import ArchiveEntryWindow


def test_frozen_operator_does_not_expose_developer_controls(monkeypatch,qt_app):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setenv('MVKVIEW_DEVELOPER_UI','1')
    monkeypatch.setenv('MVKVIEW_PRIVATE_SOURCE_DFM','placeholder.dfm')
    win=ArchiveEntryWindow()
    try:
        win.show()
        qt_app.processEvents()
        skin=win.original_visual_skin
        assert skin.packaged_operator and not skin.developer_enabled
        assert skin.toggle_action.shortcut().isEmpty()
        assert win.menuBar().isHidden() and win.wave_inspector.isHidden() and win.spec_inspector.isHidden()
        assert not win.research_tabs_action.isEnabled()
        assert not skin.technical
        assert all(a.shortcut().toString() not in ('Ctrl+D','F12') for a in win.actions())
        for key,mod in ((Qt.Key_F12,Qt.NoModifier),(Qt.Key_D,Qt.ControlModifier)):
            QTest.keyClick(win,key,mod)
        skin.toggle_action.setChecked(True)
        skin._configure_visibility(True)
        assert not skin.technical and win.menuBar().isHidden()
        assert win.task_subpages.tabBar().isHidden()
    finally:
        win.close()


def test_operator_wheel_cannot_bypass_saved_adc_scale(tmp_path,qt_app):
    adc,_=_adc(tmp_path,1,'м/с2',8,fs=65536,n=65536)
    win=ArchiveEntryWindow()
    try:
        win.show()
        win.open_operator_path(str(adc))
        for page,plot in ((3,win.wave_plot),(4,win.spec_plot)):
            win.original_root_tabs.setCurrentIndex(page)
            qt_app.processEvents()
            original=plot.getViewBox().viewRange()
            vp=plot.viewport()
            pt=vp.rect().center()
            assert not plot.getPlotItem().menuEnabled()
            assert not plot.getViewBox().menuEnabled()
            for delta in (120,-120,120):
                event=QWheelEvent(QPointF(pt),QPointF(vp.mapToGlobal(pt)),QPoint(),
                                  QPoint(0,delta),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
                QApplication.sendEvent(vp,event)
                qt_app.processEvents()
                assert event.isAccepted()
                assert plot.getViewBox().viewRange()==original
        # A supported explicit Y-scale change still changes the actual range.
        a=win.spec_plot.getViewBox().viewRange()[1]
        candidate=next(x for x in win._spec_vscale_actions if x.isEnabled() and not x.isChecked())
        candidate.trigger()
        assert win.spec_plot.getViewBox().viewRange()[1]!=a
    finally:
        win.close()


def test_operator_stop_writes_native_marker_once_without_instrument(tmp_path,qt_app):
    from PySide6.QtTest import QSignalSpy
    from ..core.native_r6_bridge import STOP_REQUEST
    from ..desktop.native_capture_dialog import NativeCaptureDialog
    win=ArchiveEntryWindow()
    dlg=NativeCaptureDialog(win)
    signals=QSignalSpy(dlg.captureFinalizing)
    try:
        win.show()
        win.enter_measurement_mode()
        win._begin_live_capture()
        win._native_dialog=dlg
        dlg._mode='capture'
        dlg._capture_root=tmp_path
        win.original_visual_skin.reveal_page(0)
        qt_app.processEvents()
        button=win.original_start_controller.buttons['bTaskConnect']
        QTest.mouseClick(button,Qt.LeftButton)
        marker=tmp_path/STOP_REQUEST
        assert marker.read_text(encoding='ascii')=='STOP\n'
        before=marker.stat().st_mtime_ns
        assert signals.count()==1 and win._measurement_exit_requested
        QTest.mouseClick(button,Qt.LeftButton)
        assert signals.count()==1 and marker.stat().st_mtime_ns==before
        assert win._live_active
        assert win._source_mode2_runtime.receipt()['hardware_commands_sent']==0
        dlg._mode=None
        win._end_live_capture(False)
        assert not win._live_active and not win._measurement_exit_requested
    finally:
        dlg._mode=None
        win._native_dialog=None
        if win._live_active:
            win._end_live_capture(False)
        dlg.close()
        win.close()
