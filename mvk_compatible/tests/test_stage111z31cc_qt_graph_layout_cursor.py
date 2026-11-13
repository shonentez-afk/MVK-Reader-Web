"""Real PageAdc/PageSpectrum rectangles and cursor lifecycle, synthetic data."""
from hashlib import sha256
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPointF
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31bj_qt_visible_file_workbench import capture_synthetic_ui_if_requested


def settle(app):
    for _ in range(8):app.processEvents()


def assert_rect(plot):
    plot.sync_source_geometry()
    m=plot.source_canvas_model
    r=plot.getViewBox().sceneBoundingRect()
    # Qt includes a half-pixel pen border; that is not a native GDI claim.
    assert r.left()==pytest.approx(m['pixel_left'],abs=1)
    assert r.right()==pytest.approx(m['pixel_right'],abs=1)
    assert r.top()==pytest.approx(m['pixel_top'],abs=1)
    assert r.bottom()==pytest.approx(m['pixel_bottom'],abs=1)
    assert m['qt_logical_pixels']
    assert not m['original_pixel_rectangle_verified']


def test_both_visible_plots_resize_and_pan_without_stale_cursor_or_fft(qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=8192)
    digest=sha256(src.read_bytes()).hexdigest()
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(src)
        w.wave_hscale_menu.actions()[9].trigger() # real 20ms within fixture
        fft=w._full_spectrum['amplitude'].copy()
        for index,plot,handler,pixel_attr,line_attr in (
            (3,w.wave_plot,w._wave_at_scene_pos,'_wave_mouse_pixel','wave_line'),
            (4,w.spec_plot,w._spec_at_scene_pos,'_spec_mouse_pixel','spec_line')):
            w.original_root_tabs.setCurrentIndex(index);settle(qt_app)
            assert_rect(plot)
            capture_synthetic_ui_if_requested(w,qt_app,f'cc_source_geometry_page_{index}')
            vb=plot.getViewBox()
            xr,yr=vb.viewRange()
            pos=vb.mapViewToScene(QPointF(sum(xr)/2,sum(yr)/2))
            handler(pos,force=True)
            assert getattr(w,pixel_attr) is not None
            assert getattr(w,line_attr).isVisible()
            # Same scene X after pan now selects a different source sample.
            span=xr[1]-xr[0]
            vb.setXRange(xr[0]+span*.05,xr[1]-span*.05,padding=0)
            settle(qt_app)
            assert getattr(w,pixel_attr) is None
            assert not getattr(w,line_attr).isVisible()
            handler(pos)
            assert getattr(w,pixel_attr) is not None
            assert getattr(w,line_attr).isVisible()
            w.resize(w.width()+120,w.height()+40);settle(qt_app)
            assert_rect(plot)
            assert getattr(w,pixel_attr) is None
            assert not getattr(w,line_attr).isVisible()
        import numpy as np
        np.testing.assert_array_equal(w._full_spectrum['amplitude'],fft)
        assert sha256(src.read_bytes()).hexdigest()==digest
    finally:w.close();settle(qt_app)


def test_scroll_hosts_keep_paintbox_size_when_bars_hide(qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(fixture_zip(tmp_path,sample_count=8192))
        w.original_root_tabs.setCurrentIndex(4);settle(qt_app)
        assert_rect(w.spec_plot)
        m=w.spec_plot.source_canvas_model
        assert w.spec_scroll_top.height()==24
        assert w.spec_scroll_right.width()==24
        assert w.spec_hscroll.x()==m['pixel_left']
        assert w.spec_hscroll.width()==m['pixel_plot_width']
        assert w.spec_vscroll.y()==m['pixel_top']
        assert w.spec_vscroll.height()==m['pixel_plot_height']
        size=w.spec_plot.size()
        w.spec_hscroll.show();w.spec_vscroll.show();settle(qt_app)
        assert w.spec_plot.size()==size
        w.spec_hscroll.hide();w.spec_vscroll.hide();settle(qt_app)
        assert w.spec_plot.size()==size
        assert_rect(w.spec_plot)
    finally:w.close();settle(qt_app)
