"""Mode2 ONE-RUN visual/page routing audit against original _Unit128.

Original source 00846D24..00846E0E shows PageStatus/Adc/Spectrum/File,
opens pnMeasure and selects PageStatus BEFORE TCP. A test suite that only
checks a visible tab name does NOT prove DSP, WriteValues or Delphi parity.

No device connection or vendor private data; synthetic Native evidence only.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z26b_live_preview import make_preview,now
from ..core.native_r6_live_preview import load_live_preview
from ..core.original_runtime_tabs import ORIGINAL_LIVE_VISIBLE


class _LocalOnlyStop:
    _mode="capture"

    def __init__(self):
        self.calls=0

    def stop_capture(self):
        self.calls+=1
        return True


def test_mode2_all_five_original_tabs_one_source_before_during_after_stop(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    window=MainWindow()
    window.show()
    qt_app.processEvents()
    try:
        assert window.enter_measurement_mode()
        qt_app.processEvents()
        assert not window._live_active
        assert window._measurement_mode_selected
        assert window.original_root_tabs.currentIndex()==2
        assert window.original_visual_skin.snapshot()["visible_source_tabs"]==list(
            ORIGINAL_LIVE_VISIBLE)
        assert window.original_shell.measure_controls.panel.isVisible()
        assert not window.original_root_tabs.isTabVisible(1)  # Config is NOT Mode2
        assert not window.original_root_tabs.isTabVisible(6)  # FactoryMode=0
        assert window.original_shell.file_channels.count()==10
        assert window.original_shell.file_spec.count()==43
        assert window.original_shell.file_values.count()==73
        assert window.original_shell.status_tabs.count()==15
        assert window.original_shell.status_table.rowCount()==15
        assert not window.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        assert not window.original_shell.measure_controls.freeze.isEnabled()
        # All five real source tab headers route to their mounted bodies.
        # Tab 0 and tab 2 share legacy task row but select different body.
        for index,stack_index,internal_index in (
                (0,0,0),(2,4,0),(3,0,1),(4,0,2),(5,2,None)):
            window.original_root_tabs.setCurrentIndex(index)
            qt_app.processEvents()
            assert window.original_root_tabs.tabData(index) in ORIGINAL_LIVE_VISIBLE
            assert window.original_shell.stack.currentIndex()==stack_index
            if internal_index is not None:
                assert window.tabs.currentIndex()==internal_index
        # The same bound Native run then drives status, wave, spectrum
        # and PageFile; tab navigation cannot create a second TCP owner.
        window._begin_live_capture()
        root,status,_=make_preview(tmp_path)
        waveform=load_live_preview(root,status,now=now())
        assert waveform is not None
        window._receive_native_live_status(status)
        window._receive_live_preview(waveform)
        qt_app.processEvents()
        assert window._source_mode2_runtime.receipt()["mode2_phase"]=="RECORDING"
        assert window._source_mode2_runtime.receipt()["native_run_bound"]
        window.original_root_tabs.setCurrentIndex(2)
        qt_app.processEvents()
        assert window.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        assert window.original_shell.status_table.rowCount()==15
        window.original_root_tabs.setCurrentIndex(3)
        qt_app.processEvents()
        assert len(window.wave_plot.listDataItems())==1
        window.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        assert len(window.spec_plot.listDataItems())==1
        window.original_root_tabs.setCurrentIndex(5)
        qt_app.processEvents()
        receipt=window.original_shell.file_page.property(
            "sourceLiveFilePlanReceipt")
        assert receipt is not None
        assert window.original_shell.file_channels.count()==10
        assert window.original_shell.file_values.count()==73
        assert window.original_shell.file_spec.count()==43
        # Revisit graphs: the same preview/run, never mixed archive history.
        assert window.session is None
        assert window._offline_flow is None
        window.original_root_tabs.setCurrentIndex(3)
        qt_app.processEvents()
        assert len(window.wave_plot.listDataItems())==1
        stopper=_LocalOnlyStop()
        window._native_dialog=stopper
        assert window.request_measurement_stop()
        assert stopper.calls==1
        assert window._source_mode2_runtime.receipt()["mode2_phase"]=="STOPPING"
        assert not window.wave_plot.listDataItems()
        assert not window.spec_plot.listDataItems()
        assert not window.original_shell.measure_controls.freeze.isEnabled()
        assert not window.original_shell.measure_controls.buttons[
            "bWriteAdc"].isEnabled()
        window._receive_native_live_status(status)
        window._receive_live_preview(waveform)
        assert not window.wave_plot.listDataItems()
        assert not window.spec_plot.listDataItems()
        window._end_live_capture(False)
        qt_app.processEvents()
        assert not window._measurement_mode_selected
        assert not window._live_active
        assert window.original_visual_skin.snapshot()["visible_source_tabs"]==[
            "PageStart"]
        assert window.session is None
    finally:
        window._native_dialog=None
        if window._live_active:
            window._end_live_capture(False)
        window.close()
        qt_app.processEvents()
