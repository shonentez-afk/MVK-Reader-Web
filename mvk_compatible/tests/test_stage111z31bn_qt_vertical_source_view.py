"""BN: original Delphi V/Page/Pos drives the REAL Qt plot and scrollbars.

Only synthetic BIN/TSXML and synthetic same-window Power/Y. No private
original screenshot, instrument, external IDP or device commands.
"""
import hashlib

import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QPointF

from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31q_same_window_spectrum import _manifest, SOURCE_N
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested,
)


def _with_gain(sidecar, gain):
    raw=sidecar.read_text(encoding="utf-8")
    sidecar.write_text(raw.replace(
        "</Channel>", f"<InternalChannelGain>{gain}</InternalChannelGain>"
        "</Channel>"), encoding="utf-8")


@pytest.fixture
def forbid_modal(monkeypatch):
    def unexpected(*a,**kw):
        raise AssertionError("BN Qt tests must never await a modal dialog")
    for name in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(QMessageBox,name,staticmethod(unexpected))


def _digest_spectrum(win):
    return hashlib.sha256(np.asarray(
        win._full_spectrum["amplitude"],dtype="<f4").tobytes()).hexdigest()


def test_original_source_y_axis_uses_tsxml_gain_and_bottom_anchored_mode_switch(
        qt_app,tmp_path,forbid_modal):
    from ..desktop.main_window import MainWindow
    source,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    _with_gain(sidecar,"6.25")
    w=MainWindow()
    w.show()
    try:
        w.open_archive(source)
        qt_app.processEvents()
        assert w._source_spectrum_gain.frange_single==6.25
        assert w._spec_original_vscale_tag==0
        y0=w.spec_plot.getViewBox().viewRange()[1]
        assert y0[0]==pytest.approx(-150.,abs=.1)
        assert y0[1]==pytest.approx(0.,abs=.1)
        w.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        assert w._full_spectrum["mode"]==1
        assert w._spec_original_vscale_tag==3
        # Stage111Z31BZ: original _Unit128:0084B901 builds numerical
        # captions from GraphDefaultVScale/divisor, not the literal divisor.
        assert w.spec_vscale_button.text()=="0.01 усл."
        assert "видимый Y" in w.spec_vscale_button.toolTip()
        assert w.spec_vscroll.value()==99900
        model=w._spec_vscroll_source_candidate
        assert model["source_tsxml_f_range_static_candidate_used"]
        assert not model["qt_y_baseline_from_local_spectrum"]
        assert model["source_bound_vertical_view"]["f_range_single"]==6.25
        assert model["source_bound_vertical_view"]["source_menu_tag"]==3
        assert model["source_bound_vertical_view"][
            "graph_default_vscale_candidate"]==10.
        y=w.spec_plot.getViewBox().viewRange()[1]
        assert y[0]==pytest.approx(0.,abs=.00002)
        assert y[1]-y[0]==pytest.approx(.01,rel=1e-4)
        fft=_digest_spectrum(w)
        w.spec_vscroll.setValue(99800)
        qt_app.processEvents()
        assert w.spec_vscroll.value()==99800
        higher=w.spec_plot.getViewBox().viewRange()[1]
        assert higher[0]>y[0]
        assert higher[1]-higher[0]==pytest.approx(.01,rel=1e-4)
        assert _digest_spectrum(w)==fft
        # The X mouse cursor must still use ORIGINAL un-decimated N/2 FFT
        # values after the source Y viewport and scrollbar both changed.
        vb=w.spec_plot.getViewBox()
        height=vb.viewRange()[1]
        scene=vb.mapViewToScene(QPointF(1250.,(height[0]+height[1])/2))
        w._spec_at_scene_pos(scene,force=True)
        assert w._spec_last_cursor is not None
        picked=w._spec_last_cursor
        assert picked["channel"]==4
        assert picked["chart_decimation_used"] is False
        assert picked["raw_y"]==pytest.approx(
            float(np.asarray(w._full_spectrum["amplitude"])[picked["selected_bin"]]))
        w.original_root_tabs.setCurrentIndex(4)
        capture_synthetic_ui_if_requested(w,qt_app,
            "14_bn_source_frange_y_scroll")
        w.refresh_spec()
        qt_app.processEvents()
        assert _digest_spectrum(w)==fft
        assert w._spec_vertical_model["delphi_position"]==99800
        assert w._spec_vscroll_source_candidate[
            "source_bound_vertical_view"]["source_bin_sha256"]==(
            w._current_offline_flow().source_record()["source_bin_sha256"])
        assert w.spec_cursor_primary.text()=="Курсор: —"
        w.spec_mode.setCurrentIndex(0)
        qt_app.processEvents()
        assert w._spec_vertical_model["delphi_position"]==0
        restored=w.spec_plot.getViewBox().viewRange()[1]
        assert restored[0]==pytest.approx(-150.,abs=.1)
        assert restored[1]==pytest.approx(0.,abs=.1)
        w.spec_mode.setCurrentIndex(2)
        qt_app.processEvents()
        assert w._spec_vertical_model["delphi_position"]==99900
        velocity=w.spec_plot.getViewBox().viewRange()[1]
        assert velocity[0]==pytest.approx(0.,abs=.002)
        assert velocity[1]-velocity[0]==pytest.approx(.1,rel=1e-4)
        capture_synthetic_ui_if_requested(w,qt_app,
            "15_bn_source_mode2_y_view")
    finally:
        w.close()
        qt_app.processEvents()


def test_source_gain_missing_stays_explicit_qt_fallback(
        qt_app,tmp_path,forbid_modal):
    from ..desktop.main_window import MainWindow
    source,_,_=_make_pair(tmp_path,adc=4,n=8192)
    w=MainWindow()
    w.show()
    try:
        w.open_archive(source)
        w.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        assert w._source_spectrum_gain.frange_single is None
        assert w._spec_original_vscale_tag==3
        assert w._spec_vscroll_source_candidate["source_bound_vertical_view"] is None
        assert w._spec_vscroll_source_candidate["qt_y_baseline_from_local_spectrum"]
        assert not w._spec_vscroll_source_candidate["source_tsxml_f_range_static_candidate_used"]
        assert "ручной гипотезы" in w.spec_graph_default_label.text()
    finally:
        w.close()
        qt_app.processEvents()


def test_accepted_same_window_original_y_reanchors_visible_qt_not_fft(
        qt_app,tmp_path,monkeypatch,forbid_modal):
    from ..desktop.main_window import MainWindow
    source,_,samples=_make_pair(tmp_path,adc=4,n=SOURCE_N*3)
    original,claim,_=_manifest(tmp_path/"ref",
        samples[-SOURCE_N:],mode=1,code=0,
        offset=len(samples)-SOURCE_N)
    w=MainWindow()
    w.show()
    try:
        w.open_archive(source)
        w.spec_n.setCurrentText(str(SOURCE_N))
        w.spec_mode.setCurrentIndex(1)
        w.refresh_spec()
        qt_app.processEvents()
        assert w._source_spectrum_gain.frange_single is None
        assert w._spec_vscroll_source_candidate[
            "source_bound_vertical_view"] is None
        old_fft=_digest_spectrum(w)
        paths=iter((str(original),str(claim)))
        monkeypatch.setattr(QFileDialog,"getOpenFileName",
            staticmethod(lambda *a,**kw:(next(paths),"JSON")))
        report=w.compare_visible_original_same_window()
        assert report["paired_numeric_pass"]
        assert _digest_spectrum(w)==old_fft
        binding=w._spec_vscroll_source_candidate["source_bound_vertical_view"]
        assert binding["operator_original_y_pair_matched"]
        assert binding["source_anchored_without_local_y_offset"]
        assert not binding["original_win32_canvas_pixel_parity_verified"]
        assert binding["f_range_single"]==1.
        assert not w._spec_vscroll_source_candidate["qt_y_baseline_from_local_spectrum"]
        assert "совпавший Power/Y" in w.spec_graph_default_label.text()
        assert "PASS" in w.spec_pair_status.text()
        capture_synthetic_ui_if_requested(w,qt_app,
            "16_bn_paired_original_y_source_scale")
        # A new FFT is a new numeric object. Must NOT keep the previous
        # original pairing or keep drawing source-anchored Y as verified.
        w.refresh_spec()
        qt_app.processEvents()
        assert w._visible_original_pair is None
        assert w._spec_vscroll_source_candidate["source_bound_vertical_view"] is None
    finally:
        w.close()
        qt_app.processEvents()
