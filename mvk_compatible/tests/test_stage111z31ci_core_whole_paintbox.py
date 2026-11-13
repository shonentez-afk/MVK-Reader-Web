"""CI source full PaintBox: one bitmap, native text before series/frame."""
from hashlib import sha256

import numpy as np
import pytest

from ..core.original_live_paintbox_text import (
    source_live_paintbox_text_plan,
)
from ..core.original_live_whole_paintbox import (
    SOURCE, ORIGINAL_DRAW_ORDER, WholePaintboxTask,
    prepare_whole_paintbox_plan,
)


def _textsize(text):
    return len(text)*7


def _textplan(*, inverse=False, width=320, height=220):
    return source_live_paintbox_text_plan(
        width=width,height=height,view_x=(0.,64.),
        view_y=(-5.,8.),x_inverted=inverse,
        x_name="Гц",y_name="м/с²",
        zero_text_width=7,six_decimals_text_width=56,
        zero_text_height=13,
        text_width=_textsize,text_height=lambda _:13,
        font_provenance="qt_approximation")


def _data():
    x=np.arange(512,dtype=np.float32)
    y=np.asarray(np.sin(x*.021)*3 + np.cos(x*.076)*1.5,dtype="<f4")
    y[200]=np.float32(6.)
    return y


def _plan(*,inverse=False):
    src=_data()
    return prepare_whole_paintbox_plan(
        src,source_text_plan=_textplan(inverse=inverse),
        x_start=0.,x_scale=.125,
        provenance="OFFLINE_ADC_VALIDATED_SHA_BOUNDED_FIXTURE",
        expected_series_sha256=sha256(src.tobytes()).hexdigest())


def _fake_text(rgba, events):
    """Pure source drawing callback; NO Win32 or Qt in the Core tests."""
    out=np.array(rgba,copy=True)
    if events:
        for e in events:
            if 0 <= e["x"] < out.shape[1] and 0 <= e["y"] < out.shape[0]:
                out[e["y"],e["x"],:3]=[17,19,23]
    return out


@pytest.mark.parametrize("invert", [False, True])
def test_whole_source_paintbox_exact_stage_order_and_reverse_adc(invert):
    samples=_data()
    words=samples.view("<u4").copy()
    plan=_plan(inverse=invert)
    assert plan.inverted_x is invert
    assert plan.width==320 and plan.height==220
    assert len(plan.horizontal_grid)>=9
    assert len(plan.vertical_grid)>=9
    assert len(plan.series_segments)>0
    assert len(plan.frame_segments)==4
    task=WholePaintboxTask(plan,_fake_text)
    with pytest.raises(ValueError):
        task.result()
    # Source stages: horizontal grid, vertical grid, GDI TextOut,
    # full per-column minmax black series, black frame.
    assert task._pass==0
    assert not task.step(max_segments=128)
    assert task._pass==1
    assert not task.step(max_segments=128)
    assert task._pass==2
    assert task.textout_calls==0
    assert not task.step(max_segments=128)
    assert task._pass==3
    assert task.textout_calls==1
    result=task.finish(max_segments=13)
    assert task.done
    assert result["textout_calls"]==1
    assert result["source"]==SOURCE
    assert result["source_draw_order"]==ORIGINAL_DRAW_ORDER
    assert result["whole_paintbox_grid_text_series_frame_one_bitmap"]
    assert result["source_gdi_textout_interposed_before_series"]
    assert not result["original_win32_pixel_parity_verified"]
    assert not result["original_dpi_awareness_verified"]
    assert result["textout_event_count"]>=16
    rgba=result["rgba"]
    assert rgba.shape==(220,320,4)
    assert not rgba.flags.writeable
    assert np.all(rgba[:,:,3]==255)
    assert np.any(np.all(rgba[:,:,:3]==[17,19,23],axis=2))
    assert np.any(np.all(rgba[:,:,:3]==[255,255,255],axis=2))
    assert np.any(np.all(rgba[:,:,:3]<[100,100,100],axis=2))
    assert result["rgba_sha256"]==sha256(rgba.tobytes()).hexdigest()
    np.testing.assert_array_equal(samples.view("<u4"),words)
    # The full source binary is independent of per-timer segment size.
    same=WholePaintboxTask(plan,_fake_text).finish(max_segments=256)
    np.testing.assert_array_equal(rgba,same["rgba"])


def test_adc_source_reversed_x_is_not_just_a_qt_axis_label():
    direct=_plan(inverse=False)
    rev=_plan(inverse=True)
    assert direct.source_series_sha256 == rev.source_series_sha256
    assert rev.source_text_plan["canvas"]["scr_width"] < 0.
    assert direct.source_text_plan["canvas"]["scr_width"] > 0.
    assert direct.vertical_grid != rev.vertical_grid
    assert direct.series_segments != rev.series_segments
    assert rev.source_text_plan["events"] != direct.source_text_plan["events"]


def test_textout_failure_never_emits_a_partially_accepted_image():
    plan=_plan()
    def invalid(rgba,events):
        return rgba[:,:,:3]
    task=WholePaintboxTask(plan,invalid)
    task.step(max_segments=128)
    task.step(max_segments=128)
    with pytest.raises(ValueError):
        task.step(max_segments=128)
    assert task.textout_calls==0
    assert not task.done
    with pytest.raises(ValueError):
        task.result()


@pytest.mark.parametrize("bad",["sha","values","source","scale","nan",
                                   "height","invalid_canvas"])
def test_whole_paintbox_rejects_unverified_source(bad):
    data=_data()
    kw=dict(values=data,source_text_plan=_textplan(),
        x_start=0.,x_scale=.125,provenance="OFFLINE_SPECTRUM_VALID",
        expected_series_sha256=sha256(data.tobytes()).hexdigest())
    if bad=="sha":
        kw["expected_series_sha256"]="0"*64
    if bad=="values":
        kw["values"]=data.reshape(2,-1)
    if bad=="source":
        kw["source_text_plan"]={"source":"unknown"}
    if bad=="scale":
        kw["x_scale"]=0.
    if bad=="nan":
        kw["values"]=data.copy()
        kw["values"][0]=np.nan
    if bad=="height":
        kw["source_text_plan"]=_textplan(width=320,height=220)
        kw["source_text_plan"]["canvas"]=dict(
            kw["source_text_plan"]["canvas"],canvas_height=12)
    if bad=="invalid_canvas":
        kw["source_text_plan"]=_textplan()
        kw["source_text_plan"]["canvas"]=dict(
            kw["source_text_plan"]["canvas"],pixel_right=9000)
    with pytest.raises((ValueError,KeyError)):
        prepare_whole_paintbox_plan(**kw)
