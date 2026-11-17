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
        idle_core=win._source_interface_clock
        assert timer.interval()==20
        assert not timer.isActive()
        assert not idle_core.running
        assert win.enter_measurement_mode()
        core=win._source_interface_clock
        assert core is not idle_core
        assert not timer.isActive()  # source thread NOT created yet
        win._begin_live_capture()   # simulation, no QProcess/TCP
        assert timer.isActive()
        assert core.running
        QTest.qWait(75)
        assert core.receipt()["ticks_total"]>=1
        initial=core.receipt()["last_tick"]
        assert initial["active_page_name"]=="PageStatus"
        assert initial["active_page_handler_address"]=="008475BC"
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
            assert win.original_root_tabs.property(
                "sourceOriginalInterfaceTickReceipt")==receipt
            selected=win.original_shell.stack.currentWidget()
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
        assert second.tick_count>=1  # source 00846EE4 direct dispatch
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


def test_original_same_page_20ms_dispatch_calls_real_status_and_toolbar_each_tick(
        qt_app, monkeypatch):
    """00847248 has no changed-tab early return; source 008475BC freezes body."""
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()  # synthetic UI only, no industrial TCP
        win._source_interface_qtimer.stop()  # deterministic manual ticks
        win.original_visual_skin.reveal_page(2)
        qt_app.processEvents()
        seen=[]
        monkeypatch.setattr(
            win.original_shell,"refresh_status",lambda:seen.append("status"))
        monkeypatch.setattr(
            win.original_shell.measure_controls,"render",
            lambda:seen.append("pnMeasure"))
        win._source_interface_last_page="PageStatus"
        initial=win._source_interface_clock.tick_count
        for _ in range(4):
            win._source_interface_tick()
        assert seen==["status","pnMeasure"]*4
        assert win._source_interface_clock.tick_count==initial+4
        # Original status body is held on FreezeUpdate, while the
        # bottom panel and dispatcher remain active.
        win._source_live_view_frozen=True
        for _ in range(2):
            win._source_interface_tick()
        assert seen==["status","pnMeasure"]*4+["pnMeasure"]*2
        assert win._source_interface_clock.tick_count==initial+6
        win._source_live_view_frozen=False
        win._source_interface_tick()
        assert seen[-2:]==["status","pnMeasure"]
        assert win._source_interface_clock.tick_count==initial+7
        assert win.original_root_tabs.property(
            "sourceOriginalInterfaceTickReceipt")["active_page_handler_address"]=="008475BC"
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
