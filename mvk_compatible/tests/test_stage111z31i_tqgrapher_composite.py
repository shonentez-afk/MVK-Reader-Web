"""Stage111Z31I: original source layer order on ONE 32bpp bitmap.

All tests are synthetic; do not read private original MVKView or device.
"""
import numpy as np
import pytest

from mvk_compatible.core.tco2draw_raster_candidate import source_raster_rgba
from mvk_compatible.core.tqgrapher_composite_source_candidate import (
    SOURCE, build_tqgrapher_composite, source_tqgrapher_composite_contract,
)


def _composite(values=None,**change):
    if values is None:
        values=np.zeros(1024,dtype='<f4')
    defaults=dict(
        canvas_width=480,canvas_height=320,
        zero_text_width=8,six_decimals_text_width=64,
        zero_text_height=14,
        scr_left=0.,scr_width=256.,scr_bottom=-10.,
        scr_height=20.,
        series_x_start=0.,series_x_scale=0.25,
        series_y_scale=1.,x_name_present=True,y_name_present=True)
    defaults.update(change)
    return build_tqgrapher_composite(values,**defaults)


def test_source_contract_orders_all_layers_and_flags_missing_gdi_font():
    d=source_tqgrapher_composite_contract()
    assert d['source']==SOURCE
    assert d['draw_order']==(
        'white_bitmap','gray_grid','canvas_textout_open',
        'black_series','black_frame','canvas_draw')
    assert d['source_software_raster_shared_for_grid_series_frame']
    assert not d['source_canvas_font_labels_rasterized']
    assert not d['original_runtime_pixel_rect_verified']
    assert not d['original_x87_pixel_parity_verified']


def test_composite_contains_gray_grid_black_trace_and_frame_white_background():
    record=_composite()
    image=record['rgba']
    assert image.shape==(320,480,4)
    assert image.dtype==np.uint8
    assert np.all(image[:,:,3]==255)
    assert image[0,0,:3].tolist()==[255,255,255]
    assert np.any(np.all(image[:,:,:3]==[192,192,192],axis=2))
    assert np.any(np.all(image[:,:,:3]==[0,0,0],axis=2))
    assert record['grid_segment_count']==22
    assert record['series_segment_count']>0
    assert record['border_segment_count']==4
    assert record['series_model']['source_pixel_rect']==(
        record['canvas']['pixel_left'],
        record['canvas']['pixel_top'],
        record['canvas']['pixel_right'],
        record['canvas']['pixel_bottom'])
    assert not record['tcanvas_textout_implemented']
    assert not record['font_metrics_are_native_original']
    assert not record['original_runtime_pixel_parity_verified']


def test_single_bin_peak_not_discarded_in_shared_source_bitmap():
    values=np.full(131072,-100.,dtype='<f4')
    values[50001]=-20.
    before=values.view('<u4').copy()
    result=_composite(
        values,scr_width=32768,series_x_scale=0.25,
        scr_bottom=-120.,scr_height=120.)
    np.testing.assert_array_equal(values.view('<u4'),before)
    assert result['series_model']['data_size_original']==131072
    assert any(hi-lo>0 for _,lo,hi,*_ in result['series_model']['columns'])
    assert result['series_segment_count']<=2*(
        result['canvas']['pixel_plot_width']+1)
    assert result['rgba'].shape==(320,480,4)


def test_composite_deterministic_and_do_not_mutate_original_source_bits():
    values=np.linspace(-5,9,800,dtype=np.float32)
    before=values.view('<u4').copy()
    a=_composite(values,scr_width=200.)
    b=_composite(values,scr_width=200.)
    np.testing.assert_array_equal(a['rgba'],b['rgba'])
    np.testing.assert_array_equal(values.view('<u4'),before)
    assert a['layer_order']==b['layer_order']


def test_stage31g_incremental_raster_copies_and_composes_source_order():
    gray=source_raster_rgba(
        width=24,height=24,segments=[(2,12,21,12)])
    gray_bits=gray.copy()
    black=source_raster_rgba(
        width=24,height=24,segments=[(12,2,12,21)],
        ink=(0,0,0),initial_rgba=gray)
    np.testing.assert_array_equal(gray,gray_bits)
    assert gray[12,12,:3].tolist()==[192,192,192]
    assert black[12,12,:3].tolist()==[0,0,0]
    assert black[12,7,:3].tolist()==[192,192,192]
    assert np.all(black[:,:,3]==255)


@pytest.mark.parametrize('bad',[
    np.zeros((5,5,4),dtype=np.uint8),
    np.zeros((24,24,3),dtype=np.uint8),
    np.zeros((24,24,4),dtype=np.float32),
    np.zeros((24,24,4),dtype=np.uint8),
    object(),
])
def test_initial_bitmap_must_be_opaque_uint8_and_expected_shape(bad):
    with pytest.raises(ValueError):
        source_raster_rgba(
            width=24,height=24,segments=[(2,2,12,12)],
            initial_rgba=bad)


@pytest.mark.parametrize('patch',[
    {'canvas_width':3},{'canvas_height':3},
    {'canvas_width':10000,'canvas_height':10000},
    {'canvas_width':True},
    {'scr_width':0},{'scr_height':-1},
])
def test_composite_invalid_frame_and_unsupported_ranges_fail_closed(patch):
    with pytest.raises(ValueError):
        _composite(**patch)


def test_invalid_original_series_data_fail_closed():
    with pytest.raises(ValueError):
        _composite(np.array([1.,np.nan],dtype='<f4'))
    with pytest.raises(ValueError):
        _composite(np.array([],dtype='<f4'))


def test_original_source_canvas_falls_back_to_margin_for_oversized_text():
    # The DELPHI source explicitly returns PixelLeft to Margin when
    # TextWidth('0.000000') exceeds the drawable rectangle; this is
    # supported original behavior, NOT an invalid-input failure.
    a=_composite(zero_text_width=1000)
    b=_composite(six_decimals_text_width=1000)
    assert a['canvas']['x_fallback_to_margin']
    assert b['canvas']['x_fallback_to_margin']
    assert a['canvas']['pixel_left']==a['canvas']['margin']
    assert b['canvas']['pixel_left']==b['canvas']['margin']
