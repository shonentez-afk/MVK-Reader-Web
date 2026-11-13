"""Stage111Z31CJ source micro-order: each grid line immediately followed
by the corresponding original TCanvas.TextOut, including reverse ADC X.
Private Unit115 is NOT distributed; checks are against source-derived
finite instructions on synthetic Float32 samples only.
"""
from hashlib import sha256
import numpy as np
import pytest
from .test_stage111z31ci_core_whole_paintbox import _plan, _fake_text
from ..core.original_live_whole_paintbox import WholePaintboxTask


@pytest.mark.parametrize("reverse",[False,True])
@pytest.mark.parametrize("budget",[1,4,13,256])
def test_grid_tick_text_interleaving_and_exact_raster_for_any_slice(
        reverse,budget):
    plan=_plan(inverse=reverse)
    result=WholePaintboxTask(plan,_fake_text).finish(max_segments=budget)
    trace=result["source_draw_trace"]
    count_h=len(plan.horizontal_grid)
    count_v=len(plan.vertical_grid)
    assert count_h==len(plan.horizontal_tick_events)
    assert count_v==len(plan.vertical_tick_events)
    assert result["source_interleaved_tick_textout"]
    assert result["source_gdi_textout_per_matching_grid_tick"]
    assert result["source_interleaved_tick_count"]==count_h+count_v
    assert result["source_negative_scrwidth_reverse_x_loop"] is reverse
    assert result["textout_calls"]==result["textout_event_count"]
    assert result["textout_calls"]==(
        count_h+count_v+len(plan.axis_name_events))
    # The original horizontal loop is always in Y index order.
    for i in range(count_h):
        assert trace[2*i]==("grid_horizontal",i,None)
        assert trace[2*i+1]==("textout","y_tick",
                              plan.horizontal_tick_events[i]["source_value"])
    base=2*count_h
    for i in range(count_v):
        assert trace[base+2*i]==("grid_vertical",i,None)
        assert trace[base+2*i+1]==("textout","x_tick",
                                  plan.vertical_tick_events[i]["source_value"])
    x_values=[e["source_value"] for e in plan.vertical_tick_events]
    assert x_values==sorted(x_values,reverse=reverse)
    name_begin=base+2*count_v
    for i,event in enumerate(plan.axis_name_events):
        assert trace[name_begin+i]==("textout",event["kind"],None)
    assert [e["kind"] for e in plan.axis_name_events]==["y_name","x_name"]
    positions=[e[0] for e in trace]
    assert positions.index("series") > positions.index("grid_vertical")
    assert positions.index("frame") > positions.index("series")
    assert len(result["rgba_sha256"])==64
    assert result["source_gdi_textout_interposed_before_series"]
    assert not result["original_win32_pixel_parity_verified"]
    # Slice scheduling must not change the source raster pixel values.
    reference=WholePaintboxTask(plan,_fake_text).finish(max_segments=256)
    np.testing.assert_array_equal(result["rgba"],reference["rgba"])


class _CloseableStub:
    def __init__(self):
        self.closes=0
        self.calls=0
    def __call__(self,rgba,events):
        self.calls+=1
        return np.array(rgba,copy=True)
    def close(self):
        self.closes+=1


def test_cancel_during_native_tick_pass_closes_font_dc_once():
    font=_CloseableStub()
    task=WholePaintboxTask(_plan(inverse=True),font)
    assert not task.done
    assert not task.step(max_segments=1)
    assert font.calls==1
    task.close()
    task.close()
    assert font.closes==1
    with pytest.raises(ValueError):
        task.result()


def test_completed_source_closes_native_font_dc_once():
    font=_CloseableStub()
    task=WholePaintboxTask(_plan(),font)
    record=task.finish(max_segments=4)
    assert font.calls==record["textout_calls"]
    assert font.closes==1
    task.close()
    assert font.closes==1
