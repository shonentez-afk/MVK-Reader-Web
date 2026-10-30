"""Stage111Q synthetic DFM-sized original baseline, no original assets."""
import sys
import pytest
from mvk_compatible.core.tqgrapher_dfm_design_idr_candidate import (
    SOURCE,DFM_DESIGN_FONT_FAMILY,DFM_DESIGN_FONT_HEIGHT,
    DFM_DESIGN_PIXELS_PER_INCH,PAINTBOX_DIMENSIONS,design_time_paintbox_baseline)


def candidate(page):
    return design_time_paintbox_baseline(
        page,zero_text_width=8,six_decimals_text_width=64,
        zero_text_height=14,scr_left=0.,scr_width=200.,
        scr_bottom=-1.,scr_height=2.,series_x_start=0.,series_x_scale=2.)


def test_two_dfm_paintboxes_and_one_design_font_are_separate_provenance():
    assert PAINTBOX_DIMENSIONS['adc']==(791,740)
    assert PAINTBOX_DIMENSIONS['spectrum']==(767,716)
    assert DFM_DESIGN_FONT_FAMILY=='Tahoma'
    assert DFM_DESIGN_FONT_HEIGHT==-13
    assert DFM_DESIGN_PIXELS_PER_INCH==96
    a=candidate('adc')
    s=candidate('spectrum')
    assert a['design_time_profile_source']==s['design_time_profile_source']==SOURCE
    assert a['margin_before_tqgrapher_minimum']==14
    assert s['margin_before_tqgrapher_minimum']==14
    assert (a['pixel_left'],a['pixel_right'])==(86,777)
    assert (s['pixel_left'],s['pixel_right'])==(86,753)
    assert (a['pixel_top'],a['pixel_bottom'])==(14,682)
    assert (s['pixel_top'],s['pixel_bottom'])==(14,658)
    assert s['spectrum_horizontal_scroll_left']==86
    assert s['spectrum_horizontal_scroll_width']==667
    assert s['spectrum_vertical_scroll_top']==14
    assert s['spectrum_vertical_scroll_height']==644
    assert s['design_scrollbar_h_height']==24
    assert s['design_scrollbar_v_width']==24
    assert a['design_scrollbar_h_height'] is None
    for model in (a,s):
        assert not model['paintbox_font_inheritance_runtime_verified']
        assert not model['paintbox_dimensions_at_runtime_verified']
        assert not model['original_delphi_canvas_textmetrics_verified']
        assert not model['dfm_initial_scrollbars_are_runtime_positions']


@pytest.mark.parametrize('invalid',[None,0,True,'','pbSpectrum','windows','ADC',{}])
def test_wrong_design_page_refused(invalid):
    with pytest.raises(ValueError,match='DFM page'):
        candidate(invalid)


def test_dfm_size_is_not_original_runtime_numeric_acceptance():
    c=candidate('spectrum')
    assert c['original_font_identity_verified'] is False
    assert c['qt_viewbox_and_paintbox_registration_verified'] is False
    assert c['original_delphi_x87_parity_verified'] is False


def test_real_windows_tahoma_design_candidate_without_runtime_parity():
    from mvk_compatible.win32_canvas_font_probe import measure_win32_font_metrics
    if sys.platform!='win32':
        with pytest.raises(RuntimeError):
            measure_win32_font_metrics(DFM_DESIGN_FONT_FAMILY,DFM_DESIGN_FONT_HEIGHT)
        return
    measured=measure_win32_font_metrics(DFM_DESIGN_FONT_FAMILY,DFM_DESIGN_FONT_HEIGHT)
    predicted=design_time_paintbox_baseline(
        'spectrum',zero_text_width=measured['text_width_zero'],
        six_decimals_text_width=measured['text_width_six_decimals'],
        zero_text_height=measured['text_height_zero'])
    assert predicted['paintbox_pixel_width']==767
    assert predicted['spectrum_horizontal_scroll_width']>0
    assert measured['all_three_metrics_same_selected_gdi_font']
    assert not measured['original_delphi_tcanvas_font_verified']
    assert not predicted['original_delphi_canvas_textmetrics_verified']
