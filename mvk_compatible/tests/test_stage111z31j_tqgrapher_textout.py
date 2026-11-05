"""Stage111Z31J source TCanvas TextOut tick/name placement tests (no GDI)."""
import copy
import pytest
from mvk_compatible.core.tqgrapher_textout_source_candidate import (
    SOURCE, source_textout_layout,
)


def _width(s):
    return 8*len(s)


def _height(s):
    return 12


def _spec(**canvas_updates):
    canvas=dict(
        pixel_left=80,pixel_right=460,pixel_top=10,pixel_bottom=280,
        canvas_width=480,canvas_height=320,margin=10,
        scr_left=0.,scr_width=100.,scr_bottom=-20.,scr_height=20.,
        ytos_m=-13.5,ytos_c=10.,
        x_fallback_to_margin=False,y_fallback_to_margin=False)
    canvas.update(canvas_updates)
    grid=dict(x_grid_ticks=(0.,50.,100.),y_grid_ticks=(-20.,-10.,0.),
              x_tick_labels_candidate=("0","50","100"),
              y_tick_labels_candidate=("-20","-10","0"))
    return canvas,grid


def _layout(*,canvas=None,grid=None,**options):
    source_canvas,source_grid=_spec()
    return source_textout_layout(canvas=source_canvas if canvas is None else canvas,
        grid=source_grid if grid is None else grid,
        text_width=_width,text_height=_height,x_name="Гц",y_name="дБ",**options)


def test_source_textout_six_ticks_plus_both_axis_names():
    report=_layout()
    assert report['source']==SOURCE
    assert [e['kind'] for e in report['events']]==[
        'y_tick','y_tick','y_tick','x_tick','x_tick','x_tick',
        'y_name','x_name']
    assert report['canvas_text_offset_px']==8
    assert report['source_xtos_coefficients_single'][0]==pytest.approx(3.8,abs=1e-6)
    assert report['source_xtos_coefficients_single'][1]==80.0
    assert not report['original_windows_native_font_verified']
    assert not report['original_native_pixel_parity_verified']
    assert report['font_metrics_provenance']=="qt_approximation"


def test_source_y_labels_007cade_x_and_y_coordinates():
    rows=_layout()['events']
    assert [(r['text'],r['x'],r['y']) for r in rows[:3]]==[
        ('-20',48,272),('-10',48,137),('0',64,2)]


def test_source_x_labels_007caf_signed_half_and_bottom_offset():
    rows=_layout()['events']
    assert [(r['text'],r['x'],r['y']) for r in rows[3:6]]==[
        ('0',76,288),('50',262,288),('100',448,288)]


def test_source_axis_names_007cb0f0_and_centered_text():
    rows=_layout()['events']
    assert (rows[6]['kind'],rows[6]['text'],rows[6]['x'],rows[6]['y'])==(
        'y_name','дБ',56,298)
    assert (rows[7]['kind'],rows[7]['text'],rows[7]['x'],rows[7]['y'])==(
        'x_name','Гц',262,298)


def test_source_window_fallback_suppresses_respective_axis_text():
    canvas,grid=_spec(x_fallback_to_margin=True)
    out=_layout(canvas=canvas,grid=grid)
    assert [e['kind'] for e in out['events']]==[
        'x_tick','x_tick','x_tick','x_name']
    canvas,grid=_spec(y_fallback_to_margin=True)
    out=_layout(canvas=canvas,grid=grid)
    assert [e['kind'] for e in out['events']]==[
        'y_tick','y_tick','y_tick','y_name']


def test_source_label_coordinates_are_independent_of_private_data():
    a,g=_spec()
    a0=copy.deepcopy(a)
    g0=copy.deepcopy(g)
    x=_layout(canvas=a,grid=g)
    y=_layout(canvas=a,grid=g)
    assert x==y
    assert a==a0 and g==g0


@pytest.mark.parametrize('patch',[
    dict(pixel_left=-3),dict(pixel_right=0),dict(pixel_right=520),
    dict(ytos_m=float('nan')),dict(scr_width=0),
    dict(pixel_left=True),dict(pixel_top=280),
])
def test_invalid_canvas_fails_closed(patch):
    c,g=_spec(**patch)
    with pytest.raises(ValueError):
        _layout(canvas=c,grid=g)


def test_tick_labels_number_must_match_original_count():
    c,g=_spec()
    g['x_tick_labels_candidate']=("0",)
    with pytest.raises(ValueError):
        _layout(canvas=c,grid=g)


@pytest.mark.parametrize('bad',["\x00bad","x"*257,None])
def test_bad_axis_names_fail_closed(bad):
    c,g=_spec()
    with pytest.raises(ValueError):
        source_textout_layout(canvas=c,grid=g,text_width=_width,
                              text_height=_height,x_name=bad,y_name="дБ")


def test_untrustworthy_font_width_must_fail_closed():
    c,g=_spec()
    with pytest.raises(ValueError):
        source_textout_layout(canvas=c,grid=g,
             text_width=lambda _: -1,text_height=_height)
    with pytest.raises(ValueError):
        source_textout_layout(canvas=c,grid=g,
             text_width=lambda _: True,text_height=_height)
    with pytest.raises(ValueError):
        source_textout_layout(canvas=c,grid=g,
             text_width=_width,text_height=lambda _: 0,x_name="Гц")


def test_native_font_parity_is_not_inferred_from_metrics_provenance():
    c,g=_spec()
    result=source_textout_layout(
        canvas=c,grid=g,text_width=_width,text_height=_height,
        x_name="Гц",y_name="дБ",
        font_provenance="unverified_native_capture")
    assert result['font_metrics_provenance']=="unverified_native_capture"
    assert result['original_windows_native_font_verified'] is False
    assert result['original_native_dpi_verified'] is False
