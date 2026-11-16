"""Source 20ms tmInterfaceUpdate: REAL QTimer, active Qt source page only.

Synthetic UI, no industrial socket and no virtual DSP measurements.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
from PySide6.QtTest import QTest

from .test_desktop_qt import qt_app


def test_actual_qt_20ms_interface_timer_follows_only_visible_source_page(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        timer=win._source_interface_qtimer
        core=win._source_interface_clock
        assert timer.interval()==20
        assert not timer.isActive()
        assert not core.running
        assert win.enter_measurement_mode()
        assert not timer.isActive()  # source thread NOT created yet
        win._begin_live_capture()   # simulation, no QProcess/TCP
        assert timer.isActive()
        assert core.running
        QTest.qWait(75)
        assert core.receipt()["ticks_total"]>=1
        initial=core.receipt()["last_tick"]
        assert initial["active_page_name"]=="PageStart"
        assert initial["active_page_handler_address"] is None
        assert initial["pnmeasure_source_handler_address"]=="008486F4"

        # Source 00847248 invokes EXACTLY the active page branch.
        for index, name, handler in (
            (2,"PageStatus","008475BC"),
            (3,"PageAdc","00847EAC"),
            (4,"PageSpectrum","00848148"),
            (5,"PageFile","0084845C"),
        ):
            win.original_visual_skin.reveal_page(index)
            QTest.qWait(55)
            receipt=core.receipt()["last_tick"]
            assert receipt["active_page_name"]==name
            assert receipt["active_page_handler_address"]==handler
            assert receipt["active_page_handler_count"]==1
            assert receipt["pnmeasure_source_handler_address"]=="008486F4"
            selected=win.original_root_tabs.currentWidget()
            assert selected.property(
                "sourceOriginalInterfaceTickReceipt")==receipt
            assert win.original_measure_controls.panel.property(
                "sourceOriginalInterfaceTickReceipt")==receipt

        assert core.receipt()["source_20ms_is_not_900ms_tcp_sample_refresh"]
        assert not win._source_mode2_runtime.receipt()[
            "original_delphi_device_parity_verified"]
        count=core.tick_count
        assert count>3
        win._end_live_capture(False)
        assert not timer.isActive()
        assert not core.running
        QTest.qWait(60)
        assert core.tick_count==count
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_failed_native_retry_renews_20ms_timer_without_reusing_old_ticks(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        first=win._source_interface_clock
        QTest.qWait(60)
        assert first.tick_count>=1
        win._end_live_capture(False)
        assert not first.running
        assert win._measurement_mode_selected
        win._begin_live_capture()
        second=win._source_interface_clock
        assert second is not first
        assert second.running
        assert second.tick_count==0
        assert win._source_interface_qtimer.isActive()
        QTest.qWait(50)
        assert second.tick_count>=1
        win._end_live_capture(False)
        assert not win._source_interface_qtimer.isActive()
        assert not second.running
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
