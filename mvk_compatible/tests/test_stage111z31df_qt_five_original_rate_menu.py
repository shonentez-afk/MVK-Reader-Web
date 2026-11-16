"""Stage111Z31DF actual Qt operator sample-rate menu from source IDP data.

No MVK device, network, ZIP archive or developer-only overlays.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")

from .test_desktop_qt import qt_app
from ..core.original_mode2_rate_menu_source import SOURCE_RATE_MENU_TAGS


def _assert_source_five_disabled_actions(panel):
    actions=panel.rate_menu.actions()
    assert len(actions)==5
    assert [a.text() for a in actions]==[
        "65536 Гц", "32768 Гц", "8192 Гц", "2048 Гц", "512 Гц"]
    assert [a.property("sourceOriginalRateTag") for a in actions]==list(
        SOURCE_RATE_MENU_TAGS)
    assert [a.property("sourceOriginalRateMenuIndex") for a in actions]==list(
        range(5))
    assert all(a.isCheckable() for a in actions)
    assert [a.isChecked() for a in actions]==[
        True, False, False, False, False]
    assert all(not a.isEnabled() for a in actions)
    assert all(a.property("sourceRateChangesDisabledForNative") is True
               for a in actions)
    assert panel.rate_menu.property("sourceSelectedOriginalRateTag")==65536
    receipt=panel.rate_menu.property("sourceOriginalRateMenuProvenance")
    assert receipt["original_menu_count"]==5
    assert receipt["original_initial_source_thread_code_hex"]=="0x309"
    assert not receipt["hardware_command_sender_enabled"]
    return actions


def test_real_qt_five_exact_source_menu_items_exist_before_after_measure(
        qt_app):
    from ..desktop.main_window import MainWindow
    window=MainWindow()
    window.show()
    qt_app.processEvents()
    try:
        controls=window.original_measure_controls
        _assert_source_five_disabled_actions(controls)
        assert window.enter_measurement_mode()
        qt_app.processEvents()
        _assert_source_five_disabled_actions(controls)
        assert controls.rate.text()=="ЧД —"
        # Original selected menu Tag is 65536, but without Go TCP status
        # it MUST NOT pretend a sensor has actually switched to that rate.
        assert not controls.rate.isEnabled()
        assert window._source_mode2_runtime.command_model.pending==()
        window._begin_live_capture()  # synthetic Qt signal; no QProcess/TCP
        qt_app.processEvents()
        _assert_source_five_disabled_actions(controls)
        assert controls.rate.isEnabled()
        assert controls.rate.text()=="ЧД —"
        assert len(window._source_mode2_runtime.command_model.pending)==1
        initial=window._source_mode2_runtime.command_model.pending[0]
        assert (initial.cmd,initial.addr,initial.data)==(1,0x0E,65536)
        assert window._source_mode2_runtime.receipt()[
            "source_initial_device_setrate_sent"] is False
        _assert_source_five_disabled_actions(controls)
        # Repeated start UI signal must not duplicate source initial
        # command in the dry-run queue or generate a device command.
        window._begin_live_capture()
        assert len(window._source_mode2_runtime.command_model.pending)==1
        window._end_live_capture(False)
        qt_app.processEvents()
        _assert_source_five_disabled_actions(controls)
    finally:
        if window._live_active:
            window._end_live_capture(False)
        window.close()
        qt_app.processEvents()
