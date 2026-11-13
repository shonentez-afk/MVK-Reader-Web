"""CG Core: original TCo2Draw combined software source, no data mutation."""
from hashlib import sha256
import numpy as np
import pytest

from ..core.original_live_plot_composite import (
    SOURCE, prepare_live_source_bitmap, LiveSourceBitmapTask,
)


def _samples(n=1024):
    x=np.arange(n,dtype=np.float64)
    data=np.asarray(np.sin(x*.019)*3. + np.cos(x*.078)*1.5,
                    dtype="<f4")
    data[n//2]=np.float32(48)
    return data


@pytest.mark.parametrize("inverse,view_x,view_y", [
    (False,(0.,255.75),(-10.,55.)),
    (True,(0.,255.75),(-10.,55.)),
    (False,(50.,145.),(-40.,40.)),
    (True,(20.,40.),(-5.,5.)),
])
def test_live_composite_source_grid_series_frame_same_image_and_bounded_steps(
        inverse,view_x,view_y):
    values=_samples()
    old_words=values.view("<u4").copy()
    digest=sha256(values.tobytes()).hexdigest()
    kwargs=dict(values=values,view_x=view_x,view_y=view_y,
                width=172,height=115,x_start=0.,x_scale=.25,
                y_scale=1.,x_inverted=inverse,
                provenance="OFFLINE_BIN_CORE_SHA_TEST",
                expected_series_sha256=digest)
    plan=prepare_live_source_bitmap(**kwargs)
    assert plan.source_series_samples==len(values)
    assert plan.source_screen_x_inverted is inverse
    assert plan.source_series_sha256==digest
    assert len(plan.frame_segments)==4
    assert len(plan.series_segments)>0
    job=LiveSourceBitmapTask(plan)
    with pytest.raises(ValueError):
        job.result()
    assert not job.done
    assert job.step(max_segments=7) is False
    partial=job.slice_count
    assert partial==1
    result=job.finish(max_segments=31)
    assert job.done
    assert job.slice_count>=2
    assert result["source"]==SOURCE
    assert result["source_series_sha256"]==digest
    assert result["source_series_samples"]==len(values)
    assert result["source_draw_order"]==(
        "white","horizontal_grid","vertical_grid",
        "black_minmax_series","black_frame")
    assert result["source_software_grid_and_series_and_frame_one_bitmap"]
    assert not result["source_textout_full_paintbox_implemented"]
    assert not result["original_win32_gdi_pixel_parity_verified"]
    rgb=result["rgba"]
    assert rgb.shape==(115,172,4)
    assert not rgb.flags.writeable
    assert np.all(rgb[:,:,3]==255)
    assert np.any(np.all(rgb[:,:,:3]<[130,130,130],axis=2))
    assert np.any(np.all(
        (rgb[:,:,:3]>=[192,192,192]) &
        (rgb[:,:,:3]<[255,255,255]),axis=2))
    assert result["rgba_sha256"]==sha256(rgb.tobytes()).hexdigest()
    np.testing.assert_array_equal(values.view("<u4"),old_words)

    # An incrementally rendered bitmap must be exactly identical to
    # a single larger-slice drawing for the same original line order.
    big=LiveSourceBitmapTask(plan).finish(max_segments=256)
    np.testing.assert_array_equal(rgb,big["rgba"])


def test_reverse_adc_changes_original_pixel_mapping_not_values():
    source=_samples()
    args=dict(values=source,view_x=(0.,255.75),
              view_y=(-10.,55.),width=200,height=140,
              x_start=0.,x_scale=.25,
              provenance="REVERSE_GETSIGNAL_CORE",
              expected_series_sha256=sha256(source.tobytes()).hexdigest())
    direct=prepare_live_source_bitmap(**args,x_inverted=False)
    inverse=prepare_live_source_bitmap(**args,x_inverted=True)
    assert direct.source_series_sha256==inverse.source_series_sha256
    assert direct.series_segments!=inverse.series_segments
    assert inverse.source_screen_x_inverted
    assert not inverse.original_delphi_runtime_parity_verified


@pytest.mark.parametrize("bad", ["nonfinite","digest","span","scale",
                                  "narrow","oversize","bool"])
def test_incorrect_sources_fail_closed_without_painting(bad):
    samples=_samples()
    kwargs=dict(values=samples,view_x=(0.,255.75),
                view_y=(-10.,55.),width=172,height=115,
                x_start=0.,x_scale=.25,provenance="CORE",
                expected_series_sha256=sha256(samples.tobytes()).hexdigest())
    if bad=="nonfinite":
        samples[2]=np.nan
    if bad=="digest":
        kwargs["expected_series_sha256"]="0"*64
    if bad=="span":
        kwargs["view_x"]=(3.,3.)
    if bad=="scale":
        kwargs["x_scale"]=0.
    if bad=="narrow":
        kwargs["width"]=7
    if bad=="oversize":
        kwargs["height"]=9000
    if bad=="bool":
        kwargs["x_inverted"]=1
    with pytest.raises(ValueError):
        prepare_live_source_bitmap(**kwargs)
