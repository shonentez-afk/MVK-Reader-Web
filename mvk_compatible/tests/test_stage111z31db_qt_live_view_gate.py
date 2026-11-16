"""Actual Qt Mode2 live preview/connection lifecycle under offline synthetic Go data."""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z26b_live_preview import make_preview,now
from ..core.native_r6_live_preview import load_live_preview


def _pair(tmp_path):
    root,status,_=make_preview(tmp_path)
    return status,load_live_preview(root,status,now=now())


def test_qt_live_graphs_require_current_transport_and_clear_on_silence(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        status,preview=_pair(tmp_path)
        win._receive_live_preview(preview)
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert len(win.wave_plot.listDataItems()) == 1
        assert len(win.spec_plot.listDataItems()) == 1
        assert win.measurement_connection_display().transport_verified
        # The next status reports old packets: immediately clear both plots.
        win._receive_native_live_status(
            status | {"seconds_since_last_packet":5.1})
        qt_app.processEvents()
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        assert not win.measurement_connection_display().transport_verified
        win._receive_live_preview(preview)
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        assert win.session is None
    finally:
        win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_qt_invalid_transport_and_stop_prevent_queued_preview(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow

    class FakeStopOwner:
        _mode="capture"
        def __init__(self):self.calls=0
        def stop_capture(self):
            self.calls+=1
            return True
        def is_busy(self):return False

    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        status,preview=_pair(tmp_path)
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert win.wave_plot.listDataItems()
        win._invalidate_native_live_status("Native status source rejected")
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        win._receive_live_preview(preview)
        assert not win.wave_plot.listDataItems()
        # Reacquire healthy transport, then request graceful Stop.
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert win.wave_plot.listDataItems()
        owner=FakeStopOwner()
        win._native_dialog=owner
        assert win.request_measurement_stop()
        assert owner.calls==1
        assert win._measurement_exit_requested
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        # Late positive Go statuses and previews must remain disallowed.
        win._receive_native_live_status(status)
        win._receive_live_preview(preview)
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        assert not win.request_measurement_stop()
    finally:
        win._native_dialog=None
        win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
