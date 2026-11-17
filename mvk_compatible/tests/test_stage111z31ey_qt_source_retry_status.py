"""Original Task2 disconnected/retrying state through real Qt widgets.

Pure validated offline status: no socket, no device writes or Go process.
"""
from __future__ import annotations
import pytest
pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from .test_stage111z26_native_live_status import fixture_state,now
from ..core.native_r6_live_status import validate_live_status


def test_qt_live_operator_retry_has_status_not_fake_connected(qt_app,monkeypatch,tmp_path):
    from ..desktop import native_capture_dialog as module
    dialog=module.NativeCaptureDialog()
    try:
        state=fixture_state()
        state.update(phase="CONNECTING",
                     source_initial_retry_attempts=2,
                     source_retry_last_error="REMOTE_DISCONNECTED",
                     source_retry_wait_ms=360,
                     source_reconnect_approved=True)
        checked=validate_live_status(
            state,expected_run=state["session_id"],now=now())
        assert checked["source_retry_evidence_verified"]
        monkeypatch.setattr(module,"load_capture_live_status",
                            lambda *args,**kwargs:checked)
        monkeypatch.setattr(module,"load_live_preview",
                            lambda *args,**kwargs:None)
        dialog._capture_root=tmp_path
        dialog._poll_live_status()
        assert "Повторное подключение TCP #2" in dialog.status_label.text()
        assert "360 мс" in dialog.live_quality.text()
        assert "НЕ подтверждено" in dialog.live_quality.text()
        assert not dialog.source_rate_tx.isChecked()
    finally:
        dialog.close()
        qt_app.processEvents()
