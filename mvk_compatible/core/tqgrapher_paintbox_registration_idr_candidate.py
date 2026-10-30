"""Stage111Q: source-derived TPaintBox margin, Canvas and scrollbar registration.

Private Delphi _Unit128:0084B40F..0084B459 and 0084C840..0084C8F8;
_Unit115:007CA4C8..007CA62F and 007CACE4..007CACF9.
Original font measurements must come from the caller TPaintBox.Canvas.
This is structural parity only: Qt viewport, DPI and Delphi x87 NOT verified.
No original source or protected data are included.
"""
from __future__ import annotations
from .tqgrapher_canvas_idr_candidate import source_canvas_geometry

SOURCE='APP_DERIVED_TQGRAPHER_PAINTBOX_REGISTRATION_IDR_CANDIDATE'
WIN32_INT_MAX=2_147_483_647


def source_paintbox_margin(pixel_width:int,pixel_height:int)->int:
    """Original integer IDIV: min(Width div $35, Height div $1E).

    Original TQGrapher independently clamps Margin to at least 10.
    """
    for name,value in (('pixel_width',pixel_width),('pixel_height',pixel_height)):
        if type(value) is not int or not 0<value<=WIN32_INT_MAX:
            raise ValueError(name+' must be a positive Win32 Integer')
    return min(pixel_width//0x35,pixel_height//0x1E)


def source_paintbox_registration(*,pixel_width:int,pixel_height:int,
                                 zero_text_width:int,six_decimals_text_width:int,
                                 zero_text_height:int,x_name_present:bool=True,
                                 y_name_present:bool=True,scr_left:float=0.,
                                 scr_width:float=1.,scr_bottom:float=0.,
                                 scr_height:float=1.,series_x_start:float=0.,
                                 series_x_scale:float=1.)->dict:
    """Source-derived Canvas and Spectrum scrollbar positions.

    TextWidth('0'), TextWidth('0.000000'), TextHeight('0') must be from
    an identically sized TPaintBox.Canvas with the *original* selected font.
    Qt QFontMetrics remain only a diagnostic approximation.
    """
    margin=source_paintbox_margin(pixel_width,pixel_height)
    g=source_canvas_geometry(
        pixel_width=pixel_width,pixel_height=pixel_height,margin=margin,
        zero_text_width=zero_text_width,
        six_decimals_text_width=six_decimals_text_width,
        zero_text_height=zero_text_height,
        x_name_present=x_name_present,y_name_present=y_name_present,
        scr_left=scr_left,scr_width=scr_width,scr_bottom=scr_bottom,
        scr_height=scr_height,series_x_start=series_x_start,
        series_x_scale=series_x_scale)
    left,right=g['pixel_left'],g['pixel_right']
    top,bottom=g['pixel_top'],g['pixel_bottom']
    return {**g,
        'paintbox_registration_source':SOURCE,
        'paintbox_pixel_width':pixel_width,
        'paintbox_pixel_height':pixel_height,
        'margin_before_tqgrapher_minimum':margin,
        'margin_divisor_width':53,
        'margin_divisor_height':30,
        'effective_source_margin':g['margin'],
        'font_metrics_from_caller_tpaintbox_canvas':True,
        'source_draw_copies_canvas_font_to_offscreen_bitmap':True,
        'spectrum_horizontal_scroll_left':left,
        'spectrum_horizontal_scroll_width':right-left,
        'spectrum_vertical_scroll_top':top,
        'spectrum_vertical_scroll_height':bottom-top,
        'scrollbar_positions_relative_to_original_paintbox':True,
        # Left/Width are changed only for H, Top/Height only for V.
        # Other native scrollbar dimensions/positions come from DFM.
        'scrollbar_other_dimensions_from_original_dfm':False,
        'qt_viewbox_and_paintbox_registration_verified':False,
        'original_font_identity_verified':False,
        'original_dpi_parity_verified':False,
        'original_delphi_x87_parity_verified':False}
