"""Original-source LIVE FIR Qt thread smoke: no main-thread DSP.

This test supplies synthetic full source history and a synthetic FIR
profile ONLY; it must not be presented as original MVK01/Delphi parity.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_mode2_source_live_fir_async_core import (
    source_window_and_synthetic_profile,
)


def test_live_fir_worker_computes_real_sha_input_without_qt_block(qt_app,tmp_path):
    from mvk_compatible.desktop.source_live_fir_worker import SourceLiveFIRWorker
    window,profile=source_window_and_synthetic_profile(tmp_path)
    ready=[]
    failed=[]
    worker=SourceLiveFIRWorker(window,profile,9,20)
    worker.ready.connect(ready.append)
    worker.failed.connect(failed.append)
    worker.start()
    try:
        assert worker.wait(15000)
        qt_app.processEvents()
        assert not failed
        assert len(ready)==1
        result=ready[0]
        assert result['output_samples']==655
        assert result['source_request_id']==window.request.request_id
        assert result['plot_points']<=4000
        assert not result['original_delphi_numerical_parity_verified']
    finally:
        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(15000)


def test_live_fir_worker_cancellation_never_emits_fake_result(qt_app,tmp_path):
    from mvk_compatible.desktop.source_live_fir_worker import SourceLiveFIRWorker
    window,profile=source_window_and_synthetic_profile(tmp_path)
    ready=[]
    worker=SourceLiveFIRWorker(window,profile,9,20)
    worker.ready.connect(ready.append)
    worker.cancel()
    worker.start()
    assert worker.wait(15000)
    qt_app.processEvents()
    assert not ready
