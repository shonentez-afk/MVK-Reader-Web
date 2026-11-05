"""Stage111Z31J Qt TextOut placement is drawn into one SOURCE bitmap.

Device-free synthetic source fixtures, measured DPR1.5 in CI.
The fonts are still Qt candidates, not original GDI pixel-verified.
"""
import numpy as np
import pytest
from .test_desktop_qt import qt_app
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture


def test_qt_textout_copy_is_opaque_and_reversible(qt_app):
    from mvk_compatible.desktop.tqgrapher_textout_qt_candidate import (
        qt_source_font_candidate,qt_textout_source_positions_rgba)
    rgba=np.full((100,240,4),255,dtype=np.uint8)
    before=rgba.copy()
    labels=(
        dict(kind='x_tick',text='500',x=80,y=20),
        dict(kind='y_tick',text='-150',x=10,y=48),
        dict(kind='x_name',text='Гц',x=125,y=80),
    )
    rendered=qt_textout_source_positions_rgba(
        rgba,labels,font=qt_source_font_candidate())
    assert rendered.shape==rgba.shape
    assert np.all(rendered[:,:,3]==255)
    assert not np.array_equal(rendered,rgba)
    np.testing.assert_array_equal(rgba,before)
    assert np.count_nonzero(rendered[:,:,0]<255)>10
    np.testing.assert_array_equal(
        rendered,qt_textout_source_positions_rgba(
            rgba,labels,font=qt_source_font_candidate()))


@pytest.mark.parametrize('bad',[
    np.zeros((80,120,4),dtype=np.uint8),
    np.full((80,120,3),255,dtype=np.uint8),
    np.zeros((80,120,4),dtype=np.float32),
])
def test_qt_research_textout_rejects_nonopaque_invalid_input(qt_app,bad):
    from mvk_compatible.desktop.tqgrapher_textout_qt_candidate import (
        qt_source_font_candidate,qt_textout_source_positions_rgba)
    with pytest.raises(ValueError):
        qt_textout_source_positions_rgba(
            bad,[dict(kind='x_tick',text='0',x=20,y=20)],
            font=qt_source_font_candidate())


def test_qt_research_textout_rejects_untrusted_events(qt_app):
    from mvk_compatible.desktop.tqgrapher_textout_qt_candidate import (
        qt_source_font_candidate,qt_textout_source_positions_rgba)
    rgba=np.full((100,240,4),255,dtype=np.uint8)
    with pytest.raises(ValueError):
        qt_textout_source_positions_rgba(
            rgba,[dict(kind='x_tick',text='0',x=True,y=20)],
            font=qt_source_font_candidate())
    with pytest.raises(ValueError):
        qt_textout_source_positions_rgba(
            rgba,[dict(kind='bad',text='0',x=2,y=20)],
            font=qt_source_font_candidate())


def test_original_reference_combined_image_has_source_tick_textout(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/'source',mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    before=np.asarray(win._full_spectrum['amplitude'],
                      dtype='<f4').view('<u4').copy()
    win.spec_source_grid_checkbox.click()
    win.spec_source_raster_checkbox.click()
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    m=win._spec_source_grid_model
    assert m['combined_preview_active']
    assert m['qt_textout_candidate_rendered'] is True
    textout=m['source_textout_placements']
    assert not textout['original_windows_native_font_verified']
    assert not textout['original_native_pixel_parity_verified']
    kinds=[e['kind'] for e in textout['events']]
    assert 'x_tick' in kinds and 'y_tick' in kinds
    assert 'x_name' in kinds
    assert not win.spec_plot.getPlotItem().getAxis('bottom').label.isVisible()
    assert not win.spec_plot.getPlotItem().getAxis('left').label.isVisible()
    np.testing.assert_array_equal(
        np.asarray(win._full_spectrum['amplitude'],
                   dtype='<f4').view('<u4'),before)
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    assert not win._spec_source_grid_model.get('combined_preview_active')
    assert win.spec_plot.getPlotItem().getAxis('bottom').label.isVisible()
    assert win.spec_plot.getPlotItem().getAxis('left').label.isVisible()
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win._spec_source_raster_item is None
    assert not win.spec_source_grid_checkbox.isChecked()
    assert win.spec_plot.getPlotItem().getAxis('bottom').label.isVisible()
    win.close()
    qt_app.processEvents()
