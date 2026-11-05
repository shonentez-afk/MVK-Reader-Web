"""Stage111Z31F: source palette, software blending and TextOut anchors.

Private Delphi unit / screenshot is deliberately NOT needed in CI.
"""
import pytest

from mvk_compatible.core.tco2draw_grid_source import (
    BACKGROUND_HEX,GRID_LINE_HEX,BACKGROUND_RGB,GRID_LINE_RGB,
    source_tco2draw_grid_contract,source_tco2draw_blend_rgb,
    source_textout_tick_anchor,
)


def test_original_tco2draw_grid_is_software_not_gdi_pen():
    model=source_tco2draw_grid_contract()
    assert model['source_background_color_hex']=='#ffffff'
    assert model['source_grid_line_color_hex']=='#c0c0c0'
    assert BACKGROUND_HEX=='#ffffff'
    assert GRID_LINE_HEX=='#c0c0c0'
    assert model['source_original_grid_software_raster'] is True
    assert model['source_original_grid_is_gdi_pen'] is False
    assert model['source_tco2draw_grid_before_series'] is True
    assert model['source_tcanvas_brush_clear_textout'] is True
    assert model['source_tcanvas_font_copied_from_input_canvas'] is True
    assert model['original_native_tcanvas_font_pixels_verified'] is False
    assert model['original_original_vs_qt_software_antialias_pixels_verified'] is False


def test_source_raster_blending_ink_to_white_with_truncation():
    assert source_tco2draw_blend_rgb(
        GRID_LINE_RGB,BACKGROUND_RGB,0.0)==(192,192,192)
    assert source_tco2draw_blend_rgb(
        GRID_LINE_RGB,BACKGROUND_RGB,0.25)==(223,223,223)
    assert source_tco2draw_blend_rgb(
        GRID_LINE_RGB,BACKGROUND_RGB,1.0)==BACKGROUND_RGB
    assert source_tco2draw_blend_rgb(
        GRID_LINE_RGB,BACKGROUND_RGB,100.0)==BACKGROUND_RGB
    assert source_tco2draw_blend_rgb(
        GRID_LINE_RGB,BACKGROUND_RGB,-0.25)==(223,223,223)
    assert source_tco2draw_blend_rgb(
        (25,100,200),(240,0,0),0.25)==(132,50,100)


@pytest.mark.parametrize('bad',[
    float('nan'),float('inf'),True,'0.5',None])
def test_invalid_raster_blend_inputs_fail_closed(bad):
    with pytest.raises(ValueError):
        source_tco2draw_blend_rgb(GRID_LINE_RGB,BACKGROUND_RGB,bad)


@pytest.mark.parametrize('bad',[
    (255,255),(256,0,0),(True,0,0),(1.2,2,3),'white'])
def test_invalid_rgb_inputs_fail_closed(bad):
    with pytest.raises(ValueError):
        source_tco2draw_blend_rgb(bad,BACKGROUND_RGB,0.1)


def test_source_tcanvas_textout_anchors_and_limits():
    assert source_textout_tick_anchor(
        axis='amplitude_y',projected_pixel=135.8,
        text_width=20,pixel_left=50,pixel_bottom=300,text_offset=8)==(22,128)
    assert source_textout_tick_anchor(
        axis='frequency_x',projected_pixel=100.2,
        text_width=20,pixel_left=50,pixel_bottom=300,text_offset=8)==(90,308)
    assert source_textout_tick_anchor(
        axis='frequency_x',projected_pixel=100.,text_width=11,
        pixel_left=0,pixel_bottom=200,text_offset=8)==(95,208)
    with pytest.raises(ValueError):
        source_textout_tick_anchor(
            axis='right',projected_pixel=100,text_width=10,
            pixel_left=0,pixel_bottom=100,text_offset=0)
    with pytest.raises(ValueError):
        source_textout_tick_anchor(
            axis='amplitude_y',projected_pixel=float('nan'),
            text_width=10,pixel_left=0,pixel_bottom=100,text_offset=0)
