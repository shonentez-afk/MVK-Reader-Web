"""Synthetic strict paired Win32 client ROI metrics; no original or PID."""
import numpy as np
import pytest
from mvk_compatible.core.original_parity_regions import compare_source_regions


def opaque(h=96,w=128):
    return np.full((h,w,4),255,dtype=np.uint8)


def test_exact_roi_metrics_and_separate_mismatch():
    a=opaque()
    b=a.copy()
    b[25,36,:3]=[0,0,0]
    spec=[{"name":"toolbar","xywh":[0,0,128,16]},
          {"name":"graph","xywh":[20,20,80,60]}]
    before=a.copy()
    result=compare_source_regions(a,b,spec)
    assert not result["rejected"]
    assert result["region_results"][0]["pixel_identical"]
    row=result["region_results"][1]
    assert row["pixel_count"]==4800
    assert row["exact_rgb_pixels"]==4799
    assert row["changed_pixels_any_channel_gt_1"]==1
    assert result["source_runtime_parity_verified"] is False
    assert not result["all_selected_regions_pixel_identical"]
    np.testing.assert_array_equal(a,before)


def test_mismatched_client_sizes_cannot_create_false_parity():
    result=compare_source_regions(opaque(96,128),opaque(96,127),
        [{"name":"all","xywh":[0,0,100,70]}])
    assert result["rejected"]
    assert result["reason"]=="different client dimensions"
    assert not result["automatic_alignment_performed"]
    assert "region_results" not in result


@pytest.mark.parametrize("regions",[
    [],
    [{"name":"one","xywh":[0,0,128,96]},
     {"name":"one","xywh":[0,0,128,96]}],
    [{"name":"unsafe/name","xywh":[0,0,20,20]}],
    [{"name":"edge","xywh":[127,95,2,2]}],
    [{"name":"negative","xywh":[-1,0,1,1]}],
    [{"name":"zero","xywh":[0,0,0,1]}],
    [{"name":"boolean","xywh":[True,0,1,1]}],
    [{"name":"bad","xywh":[0,0,1]}],
    [{"name":"bad","xywh":(0,0,10,10)}],
    [{"name":"ok","xywh":[0,0,10,10],"extra":True}],
])
def test_bad_or_unbounded_rois_are_rejected(regions):
    with pytest.raises(ValueError):
        compare_source_regions(opaque(),opaque(),regions)


def test_unsafe_or_nonopaque_images_rejected():
    a=opaque()
    alpha=a.copy()
    alpha[0,0,3]=0
    for bad in (alpha,a[:10],a.astype("float32"),a[:,:,:3]):
        with pytest.raises(ValueError):
            compare_source_regions(a,bad,[{"name":"main","xywh":[0,0,10,10]}])
