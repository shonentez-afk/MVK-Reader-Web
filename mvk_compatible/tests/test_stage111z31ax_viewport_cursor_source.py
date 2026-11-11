"""Stage111Z31AX source-only geometry and pan invalidation, synthetic data."""
import math
import pytest
from mvk_compatible.core.tqgrapher_canvas_idr_candidate import source_canvas_geometry
from mvk_compatible.core.tqgrapher_viewport_sync_source import (
    bitmap_viewport_signature, bitmap_cursor_geometry,
    bitmap_cursor_overlay_coordinates)


def _canvas():
    return source_canvas_geometry(
        pixel_width=720, pixel_height=480, margin=10,
        zero_text_width=8, six_decimals_text_width=65, zero_text_height=16,
        scr_left=1000., scr_width=5000.,
        scr_bottom=-150., scr_height=150.,
        series_x_start=0., series_x_scale=0.25)


def test_pan_less_than_tick_period_must_invalidate_bitmap():
    opts = dict(view_y=(-150., 0.), width=720, height=480,
                raster=True, composite=True)
    a = bitmap_viewport_signature(view_x=(1100., 6100.), **opts)
    assert a != bitmap_viewport_signature(view_x=(1101., 6101.), **opts)
    assert a == bitmap_viewport_signature(view_x=[1100., 6100.], **opts)
    assert a != bitmap_viewport_signature(
        view_x=(1100., 6100.), **{**opts, 'width':721})
    assert a != bitmap_viewport_signature(
        view_x=(1100., 6100.), **{**opts, 'composite':False})


def test_cursor_uses_source_inset_not_full_qt_canvas():
    canvas = _canvas()
    width = canvas['canvas_width']
    assert bitmap_cursor_geometry(
        canvas=canvas,scene_local_x=canvas['pixel_left']-2,
        scene_width=width) is None
    assert bitmap_cursor_geometry(
        canvas=canvas,scene_local_x=canvas['pixel_right']+2,
        scene_width=width) is None
    target = canvas['pixel_left']+25
    pixel,geom = bitmap_cursor_geometry(
        canvas=canvas,scene_local_x=(target+0.25)*1.5,
        scene_width=width*1.5)
    assert pixel == target
    assert geom.pixel_left == canvas['pixel_left']
    assert geom.stoi_m == canvas['stoi_m']
    assert geom.itos_c == canvas['itos_c']


def test_overlay_uses_same_source_canvas_and_raw_y():
    canvas=_canvas()
    chosen = bitmap_cursor_geometry(
        canvas=canvas,scene_local_x=canvas['pixel_left']+30.25,
        scene_width=canvas['canvas_width'])
    assert chosen is not None
    pixel,geom=chosen
    idx=math.trunc((pixel-geom.pixel_left)*geom.stoi_m+geom.stoi_c)
    result=bitmap_cursor_overlay_coordinates(
        canvas=canvas,bin_index=max(0,idx),raw_y=-77.,
        view_x=(1000.,6000.),view_y=(-150.,0.))
    assert result['source_inset_pixel_rect_used']
    assert result['original_gdi_pixel_parity_verified'] is False
    assert canvas['pixel_left'] <= result['bitmap_pixel_x'] <= canvas['pixel_right']
    assert canvas['pixel_top'] <= result['bitmap_pixel_y'] <= canvas['pixel_bottom']
    assert result['qt_x'] == pytest.approx(
        1000.+result['bitmap_pixel_x']/canvas['canvas_width']*5000.)
    assert -150. <= result['qt_y'] <= 0.


@pytest.mark.parametrize('bad', [
    dict(view_x=(0.,0.)),dict(view_x=(0.,float('nan'))),
    dict(width=0),dict(composite=True,raster=False)])
def test_bad_views_fail_closed(bad):
    args=dict(view_x=(0.,100.),view_y=(-150.,0.),
              width=720,height=480,raster=True,composite=True)
    args.update(bad)
    with pytest.raises(ValueError):bitmap_viewport_signature(**args)


def test_cursor_invalid_values_fail_closed():
    c=_canvas()
    with pytest.raises(ValueError):
        bitmap_cursor_geometry(
            canvas={**c,'source':'wrong'},
            scene_local_x=100.,scene_width=720.)
    with pytest.raises(ValueError):
        bitmap_cursor_geometry(
            canvas=c,scene_local_x=float('inf'),scene_width=720.)
    with pytest.raises(ValueError):
        bitmap_cursor_overlay_coordinates(
            canvas=c,bin_index=-1,raw_y=0.,
            view_x=(0.,100.),view_y=(-150.,0.))
