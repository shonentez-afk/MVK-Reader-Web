"""Stage111Q synthetic original TPaintBox margin/scrollbar regression."""
import pytest
from mvk_compatible.core.tqgrapher_paintbox_registration_idr_candidate import (
    source_paintbox_margin,source_paintbox_registration,SOURCE)


def layout(**overrides):
    kwargs=dict(pixel_width=800,pixel_height=500,zero_text_width=8,
                six_decimals_text_width=64,zero_text_height=14,
                x_name_present=True,y_name_present=True,
                scr_left=0.,scr_width=200.,scr_bottom=-1.,
                scr_height=2.,series_x_start=0.,series_x_scale=2.)
    kwargs.update(overrides)
    return source_paintbox_registration(**kwargs)


def test_original_53_by_30_margin_not_hardcoded_ten():
    assert source_paintbox_margin(800,500)==15
    assert source_paintbox_margin(1200,600)==20
    assert source_paintbox_margin(100,100)==1
    assert source_paintbox_margin(300,1000)==5
    assert source_paintbox_margin(53,30)==1
    assert source_paintbox_margin(52,29)==0


def test_source_structure_produces_scrollbars_and_real_pixel_rect():
    g=layout()
    assert g['source']=='APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE'
    assert g['paintbox_registration_source']==SOURCE
    assert g['margin_before_tqgrapher_minimum']==15
    assert g['effective_source_margin']==15
    assert (g['pixel_left'],g['pixel_right'])==(87,785)
    assert (g['pixel_top'],g['pixel_bottom'])==(15,441)
    assert g['spectrum_horizontal_scroll_left']==87
    assert g['spectrum_horizontal_scroll_width']==698
    assert g['spectrum_vertical_scroll_top']==15
    assert g['spectrum_vertical_scroll_height']==426
    assert g['font_metrics_from_caller_tpaintbox_canvas']
    assert g['source_draw_copies_canvas_font_to_offscreen_bitmap']
    assert not g['qt_viewbox_and_paintbox_registration_verified']
    assert not g['original_font_identity_verified']
    assert not g['original_dpi_parity_verified']


def test_minimum_margin_and_original_virtual_canvas_clamp():
    g=layout(pixel_width=16,pixel_height=20)
    assert g['margin_before_tqgrapher_minimum']==0
    assert g['effective_source_margin']==10
    assert g['canvas_width']==g['canvas_height']==30
    assert g['spectrum_horizontal_scroll_width']>0
    assert g['spectrum_vertical_scroll_height']>0


def test_font_size_can_cause_source_fallback_not_dpi_guess():
    g=layout(pixel_width=400,pixel_height=600,
             zero_text_width=15,six_decimals_text_width=10000)
    assert g['margin_before_tqgrapher_minimum']==7
    assert g['pixel_left']==10
    assert g['spectrum_horizontal_scroll_width']==g['pixel_right']-10


def test_scr_reversed_and_metrics_not_part_of_margin_divisors():
    original=layout()
    modified=layout(zero_text_width=30,zero_text_height=30,
                    scr_width=-60.,series_x_scale=4.)
    assert original['margin_before_tqgrapher_minimum']==15
    assert modified['margin_before_tqgrapher_minimum']==15
    assert modified['spectrum_horizontal_scroll_left']==modified['pixel_left']
    assert modified['spectrum_vertical_scroll_top']==modified['pixel_top']
    assert not modified['original_delphi_x87_parity_verified']


@pytest.mark.parametrize('width,height',[(0,100),(-1,100),(100,0),(100,-1),
   (True,100),(100,False),(1.5,100),(100,100.5),
   (2147483648,500),(500,2147483648)])
def test_invalid_native_paintbox_dimensions_fail_closed(width,height):
    with pytest.raises(ValueError,match='Win32 Integer'):
        source_paintbox_margin(width,height)
