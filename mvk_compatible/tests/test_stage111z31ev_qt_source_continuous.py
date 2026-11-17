"""The original Task2 can run to operator Stop; no fake percent or TCP."""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from .test_stage111z26_native_live_status import fixture_state, now
from ..core.native_r6_live_status import validate_live_status


def test_native_capture_dialog_original_unbounded_mode_is_first_choice(
        qt_app,monkeypatch,tmp_path):
    from ..desktop import native_capture_dialog as native_ui
    dialog=native_ui.NativeCaptureDialog()
    try:
        assert dialog.seconds.minimum()==0
        assert dialog.seconds.maximum()==300
        assert dialog.seconds.value()==0
        assert "До отключения" in dialog.seconds.text()
        assert not dialog.source_rate_tx.isChecked()
        # Feed an independently verified-style local JSON snapshot ONLY:
        # no Go subprocess, socket, or hardware is started.
        # The real dialog receives a validated Core projection, not a
        # raw producer JSON fixture; the latter has no quality/staleness
        # attributes and must never bypass validation in production.
        state=fixture_state()
        state["target_seconds"]=0
        snapshot=validate_live_status(
            state,expected_run=state["session_id"],now=now())
        monkeypatch.setattr(
            native_ui,"load_capture_live_status",
            lambda *args,**kwargs:snapshot)
        monkeypatch.setattr(native_ui,"load_live_preview",
                            lambda *args,**kwargs:None)
        dialog._capture_root=tmp_path
        dialog._poll_live_status()
        assert dialog.progress.minimum()==0
        assert dialog.progress.maximum()==0
        assert "до отключения" in dialog.status_label.text()
        assert "900" not in dialog.status_label.text()
        snapshot["target_seconds"]=30
        dialog._poll_live_status()
        assert dialog.progress.maximum()==100
        assert dialog.progress.value()>0
    finally:
        dialog.close()
        qt_app.processEvents()
