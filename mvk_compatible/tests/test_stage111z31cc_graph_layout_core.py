"""Shared source rectangle contract; no Qt or original process required."""
import pytest
from ..core.original_graph_layout import source_graph_layout


def test_source_rectangle_uses_text_metrics_not_axis_auto_width():
    m=source_graph_layout(width=791,height=740,zero_width=7,
                          six_decimals_width=56,text_height=15)
    assert (m['pixel_left'],m['pixel_right'],m['pixel_top'],m['pixel_bottom'])==(77,777,14,682)
    assert m['pixel_plot_width']==700
    assert m['pixel_plot_height']==668
    assert not m['original_pixel_rectangle_verified']
    assert not m['original_canvas_font_metrics_verified']
    assert 'itos_m' not in m  # layout cannot certify a sample transform


@pytest.mark.parametrize('x_name,y_name,extra',[(False,False,0),(True,False,22),(False,True,22),(True,True,22)])
def test_axis_names_reserve_one_shared_caption_row(x_name,y_name,extra):
    m=source_graph_layout(width=800,height=500,zero_width=7,
                          six_decimals_width=56,text_height=15,
                          x_name=x_name,y_name=y_name)
    assert m['pixel_bottom']==500-15-15-7-extra


@pytest.mark.parametrize('width,height,margin',[(1600,900,30),(800,300,10),(530,1200,10),(1060,1200,20)])
def test_source_page_margin_uses_both_dimensions(width,height,margin):
    m=source_graph_layout(width=width,height=height,zero_width=7,
                          six_decimals_width=56,text_height=15)
    assert m['margin']==margin
    assert m['pixel_top']==margin
    assert m['pixel_right']==width-margin
