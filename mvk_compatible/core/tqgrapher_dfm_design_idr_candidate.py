"""Stage111Q: small source-derived design-time layout facts, NOT original DFM.

Privately observed original mvkform.dfm inside Projects.7z. DFM itself
is NOT published. Design-time width/height, form font and PixelsPerInch
are NOT proof of actual running TCanvas values: Align=alClient,
resizing, DPI virtualization and font substitution can change them.
"""
from __future__ import annotations
from .tqgrapher_paintbox_registration_idr_candidate import (
    source_paintbox_registration)

SOURCE='APP_DERIVED_DFM_DESIGN_TIME_PAINTBOX_BASELINE'
DFM_DESIGN_FONT_FAMILY='Tahoma'
DFM_DESIGN_FONT_HEIGHT=-13
DFM_DESIGN_PIXELS_PER_INCH=96
DFM_DESIGN_FONT_STYLE='normal'
PAINTBOX_DIMENSIONS={'adc':(791,740),'spectrum':(767,716)}
SPECTRUM_DFM_SCROLL_INITIAL={
    'h_left':24,'h_width':553,'h_height':24,
    'v_top':0,'v_height':400,'v_width':24}


def design_time_paintbox_baseline(tab:str,*,zero_text_width:int,
                                  six_decimals_text_width:int,
                                  zero_text_height:int,
                                  x_name_present:bool=True,
                                  y_name_present:bool=True,
                                  scr_left:float=0.,scr_width:float=1.,
                                  scr_bottom:float=0.,scr_height:float=1.,
                                  series_x_start:float=0.,
                                  series_x_scale:float=1.)->dict:
    """Source Canvas over DFM design dimensions; text metrics remain EXPLICIT.

    Original Draw dynamically overwrites horizontal scrollbar Left/Width
    and vertical scrollbar Top/Height; fixed DFM positions are not runtime.
    """
    if type(tab) is not str or tab not in PAINTBOX_DIMENSIONS:
        raise ValueError('Expected original DFM page adc or spectrum')
    w,h=PAINTBOX_DIMENSIONS[tab]
    g=source_paintbox_registration(
        pixel_width=w,pixel_height=h,
        zero_text_width=zero_text_width,
        six_decimals_text_width=six_decimals_text_width,
        zero_text_height=zero_text_height,
        x_name_present=x_name_present,y_name_present=y_name_present,
        scr_left=scr_left,scr_width=scr_width,
        scr_bottom=scr_bottom,scr_height=scr_height,
        series_x_start=series_x_start,series_x_scale=series_x_scale)
    return {**g,
        'design_time_profile_source':SOURCE,
        'design_time_tab':tab,
        'design_form_font_family':DFM_DESIGN_FONT_FAMILY,
        'design_form_font_height':DFM_DESIGN_FONT_HEIGHT,
        'design_form_font_style':DFM_DESIGN_FONT_STYLE,
        'design_form_pixels_per_inch':DFM_DESIGN_PIXELS_PER_INCH,
        'paintbox_font_inheritance_runtime_verified':False,
        'paintbox_dimensions_at_runtime_verified':False,
        'design_font_substitution_and_dpi_verified':False,
        'original_delphi_canvas_textmetrics_verified':False,
        'dfm_initial_scrollbars_are_runtime_positions':False,
        'design_scrollbar_h_height':(
            SPECTRUM_DFM_SCROLL_INITIAL['h_height'] if tab=='spectrum' else None),
        'design_scrollbar_v_width':(
            SPECTRUM_DFM_SCROLL_INITIAL['v_width'] if tab=='spectrum' else None)}
