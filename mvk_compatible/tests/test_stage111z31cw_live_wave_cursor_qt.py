"""LIVE PageAdc original cursor/graph with synthetic Go RX, no socket/EXE."""
from hashlib import sha256
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF
import pyqtgraph as pg

from .test_desktop_qt import qt_app
from .test_stage111z31cw_live_wave_cursor_core import preview
from ..desktop.xor_cursor_overlay import QtSpectrumXorCursor


def test_live_plain_getsignal_reverse_view_xonly_cursor_and_freeze(qt_app):
    from ..desktop.main_window import MainWindow
    source=preview()
    w=MainWindow();w.show();qt_app.processEvents()
    try:
        w._begin_live_capture()  # mode shell only, never a socket
        w.original_root_tabs.setCurrentIndex(3)
        w._wave_hscale_tag=9  # original 20 ms => 1310 samples
        qt_app.processEvents()
        w._native_live_status=dict(
            session_id=source.session_id,
            phase="RECORDING",snapshot_stale=False,
            source_original_storage_verified=False,
            channels=[dict(samples=4096) for _ in range(8)])
        w._live_preview=source
        w._render_live_wave()
        qt_app.processEvents()
        bound=w._source_live_wave_cursor
        assert bound is not None
        assert bound.adc==1 and bound.h_tag==9
        assert bound.full_reversed_getsignal.size==1310
        assert w.wave_plot.getViewBox().state["xInverted"] is True
        assert w.wave_plot.getViewBox().viewRange()[0]==pytest.approx(
            [0.,20.],abs=1e-4)
        assert w.wave_plot.getPlotItem().getAxis("bottom").labelText=="мс"
        assert isinstance(w.wave_xor_crosshair,QtSpectrumXorCursor)
        pos=w.wave_plot.getViewBox().mapViewToScene(QPointF(10.,0.))
        w._wave_at_scene_pos(pos,force=True)
        selected=w._source_live_cursor_last
        assert selected is not None, w.statusBar().currentMessage()
        assert w.wave_line.isVisible()
        assert w.wave_xor_crosshair.cursor is not None
        assert selected["original_uint64_adc_sample_index"]==(
            bound.end_absolute_sample_exclusive-1-selected["output_index"])
        assert selected["full_float32_value"]==float(
            bound.full_reversed_getsignal[selected["output_index"]])
        assert f"GetSignal[{selected['output_index']}]" in w.wave_hint.text()
        assert "полный Float32" in w.wave_hint.text()
        assert "мс" in w.wave_cursor_primary.text()

        # Y alone changes the viewport, not the cached source or its hash.
        original=bound
        w.wave_vscale_menu.actions()[1].trigger()
        qt_app.processEvents()
        assert w._source_live_wave_cursor is original
        # Original X-only UpdateCursor ignores mouse Y; an otherwise
        # identical column can be selected at another Y coordinate.
        w._wave_at_scene_pos(QPointF(pos.x(),pos.y()+50),force=True)
        assert w._source_live_cursor_last is not None
        w._source_live_view_frozen=True
        w._wave_at_scene_pos(pos,force=True)
        assert w._source_live_cursor_last is None
        assert not w.wave_line.isVisible()
        assert w.wave_xor_crosshair.cursor is None
        w._source_live_view_frozen=False
        w._native_live_status["session_id"]="FOREIGN_SYNTHETIC_SESSION"
        w._wave_at_scene_pos(pos,force=True)
        assert w._source_live_cursor_last is None
        assert w.wave_xor_crosshair.cursor is None
    finally:
        # Ensure the source 20ms GUI dispatcher and any pending FIR
        # workers cannot outlive their synthetic Qt test window.
        if w._live_active:
            w._end_live_capture(False)
        w.close();qt_app.processEvents()


def test_live_fir_cursor_clips_only_view_not_full_value(qt_app):
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();qt_app.processEvents()
    try:
        w._begin_live_capture()  # mode shell only, never a socket
        w.original_root_tabs.setCurrentIndex(3)
        w._wave_hscale_tag=9
        qt_app.processEvents()
        w._native_live_status=dict(
            session_id="SYNTHETIC_FIR_CURRENT",
            phase="RECORDING",snapshot_stale=False)
        blocked=w.wave_envelope_code.blockSignals(True)
        w.wave_envelope_code.setCurrentIndex(20)
        w.wave_envelope_code.blockSignals(blocked)
        values=np.asarray([0.,-5.,4.,2.,-2.,0.,1.]*3,dtype="<f4")
        values.setflags(write=False)
        trace=dict(
            adc=w._ch(),source_h_tag=9,source_mode=w.wave_mode.currentIndex(),
            envelope_code=20,source_session_id="SYNTHETIC_FIR_CURRENT",
            source_request_id="SYNTHETIC_FIR_ONLY",
            original_selected_ms=20,output_rate_hz=1000,
            full_reversed_getsignal=values,
            output_float32_sha256=sha256(values.tobytes()).hexdigest(),
            source_float32_sha256="b"*64,
            source_cursor_axis_unit="мс")
        w._source_fir_trace=trace
        w.wave_plot.clear()
        w.wave_plot.getViewBox().invertX(True)
        w.wave_plot.plot(np.arange(21),values,pen=pg.mkPen(None))
        w.wave_plot.setXRange(0.,20.,padding=0)
        w.wave_line=pg.InfiniteLine(angle=90,pen=pg.mkPen(None))
        w.wave_line.setVisible(False)
        w.wave_plot.addItem(w.wave_line,ignoreBounds=True)
        w.wave_xor_crosshair=QtSpectrumXorCursor(
            w.wave_plot.getViewBox())
        w.wave_plot.addItem(w.wave_xor_crosshair,ignoreBounds=True)
        qt_app.processEvents()
        point=w.wave_plot.getViewBox().mapViewToScene(QPointF(2.,0.))
        w._wave_at_scene_pos(point,force=True)
        assert w.wave_line.isVisible()
        assert w.wave_xor_crosshair.cursor is not None
        assert w._source_live_cursor_last is not None
        assert "GetSignal FIR[" in w.wave_hint.text()
        w._native_live_status["snapshot_stale"]=True
        w._wave_at_scene_pos(point,force=True)
        assert w._source_live_cursor_last is None
        assert w.wave_xor_crosshair.cursor is None
    finally:
        # Ensure the source 20ms GUI dispatcher and any pending FIR
        # workers cannot outlive their synthetic Qt test window.
        if w._live_active:
            w._end_live_capture(False)
        w.close();qt_app.processEvents()
