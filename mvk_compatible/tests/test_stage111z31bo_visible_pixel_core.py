"""Stage111Z31BO: synthetic Power/Y + current RGBA + original screenshot.

Strictly local Core contract. Pixel comparison is diagnostic, not original
Win32 runtime provenance or physical calibration; no GDI or PySide6 needed.
"""
from __future__ import annotations

from hashlib import sha256
import numpy as np
import pytest

from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from ..core.original_spectrum_x32dbg_reference import load_original_spectrum_reference
from ..core.original_visible_pixel_compare import (
    compare_current_original_pixel_view, visual_pixel_difference)
from ..core.tqgrapher_canvas_idr_candidate import SOURCE as CANVAS_SOURCE
from ..core.tqgrapher_viewport_sync_source import bitmap_viewport_signature

WIDTH=640
HEIGHT=420
XR=(0.,25600.)
YR=(-150.,0.)


def _case(tmp_path, mode=0):
    manifest,_,_,_=create_reference_fixture(
        tmp_path/f"original_mode{mode}", mode=mode,n=1024,fs=65536)
    ref=load_original_spectrum_reference(manifest)
    spectrum=ref.to_spectrum_record(channel=4)
    frame=np.empty((HEIGHT,WIDTH,4),dtype=np.uint8)
    frame[:]=[255,255,255,255]
    frame[160,61:620]=[0,0,0,255]
    frame[18:400,60]=[192,192,192,255]
    canvas={
        "source":CANVAS_SOURCE,"canvas_width":WIDTH,
        "canvas_height":HEIGHT,"pixel_left":60,"pixel_top":20,
        "pixel_right":620,"pixel_bottom":390,"margin":10}
    model={
        "combined_preview_active":True,
        "combined_canvas":canvas,
        "qt_raster_size":(WIDTH,HEIGHT),
        "bitmap_viewport_signature":bitmap_viewport_signature(
            view_x=XR,view_y=YR,width=WIDTH,height=HEIGHT,
            raster=True,composite=True),
    }
    def compare(original, **changes):
        opts=dict(
            source_bitmap=frame,canvas=canvas,source_model=model,
            view_x=XR,view_y=YR,qt_device_pixel_ratio=1.5,
            original_png_rgba=original,
            operator_declared_same_window=True,
            shift_radius=3)
        opts.update(changes)
        return compare_current_original_pixel_view(ref,spectrum,**opts)
    return ref,spectrum,frame,canvas,model,compare


@pytest.mark.parametrize("mode",[0,1,2,3])
def test_whole_current_canvas_identity_and_original_y_sha_is_diagnostic_only(
        tmp_path, mode):
    ref,spectrum,frame,canvas,model,compare=_case(tmp_path,mode)
    before=sha256(frame.tobytes()).hexdigest()
    y_before=sha256(spectrum["amplitude"].tobytes()).hexdigest()
    report,diff=compare(frame.copy())
    assert report["exact_rgb_equal_without_alignment"]
    assert report["original_full_y_sha256"]==ref.display_y_sha256
    assert report["currently_visible_full_y_sha256"]==ref.display_y_sha256
    assert report["full_canvas"]["pixels_any_rgb_channel_gt_1"]==0
    assert report["plot_pixels"]["pixels_any_rgb_channel_gt_1"]==0
    assert not report["independent_original_capture_authentication"]
    assert not report["original_gdi_canvas_dpi_parity_verified"]
    assert not report["physical_calibration_verified"]
    assert not report["private_original_png_or_bin_in_report"]
    assert diff.shape==frame.shape
    assert bool(np.all(diff==[255,255,255,255]))
    assert sha256(frame.tobytes()).hexdigest()==before
    assert sha256(spectrum["amplitude"].tobytes()).hexdigest()==y_before
    assert str(tmp_path) not in str(report)
    assert "display_y" not in report


def test_difference_mask_separates_series_errors_from_label_errors(tmp_path):
    _,_,frame,_,_,compare=_case(tmp_path)
    original=frame.copy()
    original[160,200,:3]=[255,255,255]  # inside original PixelRect
    original[10,10,:3]=[0,0,0]          # outside ROI (axes/title margin)
    report,diff=compare(original)
    assert report["plot_pixels"]["pixels_any_rgb_channel_gt_1"]==1
    assert report["axes_text_and_margins"]["pixels_any_rgb_channel_gt_1"]==1
    assert not report["exact_rgb_equal_without_alignment"]
    assert diff[160,200].tolist()==[239,65,54,255]
    assert diff[10,10].tolist()==[255,170,51,255]
    assert diff[160,201].tolist()==[255,255,255,255]


@pytest.mark.parametrize("which",[
    "operator_refused","stale_zoom","stale_size","not_combined",
    "different_reference_y","different_mode","altered_original_y",
    "wrong_original_dimensions","transparent_original","invalid_dpr"])
def test_fail_closed_without_original_window_and_current_bitmap_identity(
        tmp_path,which):
    ref,spectrum,frame,canvas,model,compare=_case(tmp_path)
    original=frame.copy()
    options={}
    if which=="operator_refused":
        options["operator_declared_same_window"]=False
    elif which=="stale_zoom":
        options["view_x"]=(100.,20000.)
    elif which=="stale_size":
        model["qt_raster_size"]=(WIDTH+1,HEIGHT)
    elif which=="not_combined":
        model["combined_preview_active"]=False
    elif which=="different_reference_y":
        spectrum["amplitude"]=np.asarray(
            spectrum["amplitude"],dtype="<f4").copy()
        spectrum["amplitude"][11]+=1.
    elif which=="different_mode":
        spectrum["mode"]=1
    elif which=="altered_original_y":
        # Read-only original arrays are not mutated; replace the record
        # with an incompatible built-in reference by selecting mode1.
        m1,_,_,_=create_reference_fixture(
            tmp_path/"different_reference", mode=1,n=1024,fs=65536)
        ref2=load_original_spectrum_reference(m1)
        with pytest.raises(ValueError):
            compare_current_original_pixel_view(
                ref2,spectrum,source_bitmap=frame,canvas=canvas,
                source_model=model,view_x=XR,view_y=YR,
                qt_device_pixel_ratio=1.5,original_png_rgba=original,
                operator_declared_same_window=True)
        return
    elif which=="wrong_original_dimensions":
        original=original[:-1]
    elif which=="transparent_original":
        original[5,5,3]=0
    else:
        options["qt_device_pixel_ratio"]=0.01
    with pytest.raises(ValueError):
        compare(original,**options)


def test_difference_rgba_tolerates_exact_single_rgb_quantum(tmp_path):
    _,_,frame,_,_,compare=_case(tmp_path)
    original=frame.copy()
    original[100,100,0]=254
    report,diff=compare(original)
    assert report["plot_pixels"]["pixels_any_rgb_channel_gt_1"]==0
    assert not report["exact_rgb_equal_without_alignment"]
    assert diff[100,100].tolist()==[224,224,224,255]
