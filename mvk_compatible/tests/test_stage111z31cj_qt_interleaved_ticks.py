"""Stage111Z31CJ live Qt original interleaved line/TextOut QA, DPR150.

Original Windows binary/process is NOT launched, same-window 1:1 native
GDI glyph and pixel matching remain explicitly unverified.
"""
from hashlib import sha256
import numpy as np
import pytest
pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from .test_stage111z31ci_qt_whole_paintbox import _assert_same_source_paintbox


def test_both_source_pages_interleave_every_grid_label_with_line(qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    original=fixture_zip(tmp_path,sample_count=8192)
    before=sha256(original.read_bytes()).hexdigest()
    window=MainWindow();window.show();settle(qt_app)
    try:
        window.open_archive(original)
        window.wave_hscale_menu.actions()[9].trigger()
        baseline=np.asarray(window._full_spectrum["amplitude"]).copy()
        for idx,plot,inverse in ((3,window.wave_plot,True),
                                 (4,window.spec_plot,False)):
            window.original_root_tabs.setCurrentIndex(idx)
            settle(qt_app)
            source,caption=_assert_same_source_paintbox(plot,inverse)
            assert source["source_interleaved_tick_textout"]
            assert source["source_gdi_textout_per_matching_grid_tick"]
            assert source["source_negative_scrwidth_reverse_x_loop"] is inverse
            assert source["textout_calls"]==source["textout_event_count"]
            trace=source["source_draw_trace"]
            y=[e for e in trace if e[0]=="grid_horizontal"]
            x=[e for e in trace if e[0]=="grid_vertical"]
            assert len(y)>=9 and len(x)>=9
            assert len([e for e in trace if e[0]=="textout"]) == source[
                "textout_event_count"]
            values=[e[2] for e in trace if e[:2]==("textout","x_tick")]
            assert values==sorted(values,reverse=inverse)
            assert caption["source_one_paintbox_shared_buffer"]
            assert caption["source_bitmap_sha256"]==source["rgba_sha256"]
            assert plot.source_composite_overlay.source_composite_render_count>0
        np.testing.assert_array_equal(window._full_spectrum["amplitude"],
                                      baseline)
        assert sha256(original.read_bytes()).hexdigest()==before
    finally:
        window.close();settle(qt_app)
