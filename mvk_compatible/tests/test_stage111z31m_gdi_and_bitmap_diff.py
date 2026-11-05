"""Stage111Z31M source bitmap diff and Win32 GDI smoke tests.

Only fabricated RGBA graphics, no original screenshots or user buffers.
"""
import json
import sys

import numpy as np
import pytest

from mvk_compatible.core.spectrum_bitmap_diff import (
    compare_spectrum_bitmap_crops,
)
from mvk_compatible.desktop.win32_gdi_source_candidate import (
    Win32SourceTextCanvas,native_gdi_supported,
)


def _image():
    img=np.full((90,180,4),255,dtype=np.uint8)
    img[20:23,30:140,:3]=0
    img[35:72,60:62,:3]=192
    return img


def test_same_image_has_zero_diff_and_no_original_claims():
    img=_image()
    before=img.copy()
    result=compare_spectrum_bitmap_crops(img,img,shift_radius=2)
    assert result["best_match"]["candidate_to_original_offset_px"]==[0,0]
    assert result["best_match"][
        "rgb_channel_mean_absolute_error_on_foreground"]==0.
    assert result["best_match"]["foreground_pixels"]>0
    assert not result["complete_mvkview_spectrum_parity_verified"]
    assert not result["original_capture_provenance_independently_authenticated"]
    assert result["source_raw_pixels_or_paths_exported"] is False
    np.testing.assert_array_equal(img,before)
    assert "rgba" not in json.dumps(result).lower()


def test_alignment_finds_2px_shift_without_rewriting_source():
    original=_image()
    shifted=np.full_like(original,255)
    shifted[:,:-2]=original[:,2:]
    result=compare_spectrum_bitmap_crops(original,shifted,shift_radius=3)
    assert result["best_match"]["candidate_to_original_offset_px"]==[2,0]
    assert result["best_match"][
        "rgb_channel_mean_absolute_error_on_foreground"]==0.


def test_no_ink_is_not_pass_or_pixel_parity():
    empty=np.full((80,80,4),255,dtype=np.uint8)
    result=compare_spectrum_bitmap_crops(empty,empty)
    assert result["no_informative_ink"]
    assert result["best_match"] is None
    assert not result["complete_mvkview_spectrum_parity_verified"]


@pytest.mark.parametrize("bad",[
    np.zeros((90,180,4),dtype=np.uint8),
    np.zeros((90,180,3),dtype=np.uint8),
    np.full((90,180,4),255,dtype=np.float32),
])
def test_pixel_diff_fails_closed_on_invalid_original_crop(bad):
    with pytest.raises(ValueError):
        compare_spectrum_bitmap_crops(bad,_image())


@pytest.mark.skipif(sys.platform!="win32",reason="Native GDI requires Windows")
def test_gdi_uses_real_windows_textout_and_does_not_modify_input():
    with Win32SourceTextCanvas(font_face="Tahoma",font_height=-13) as gdi:
        d=gdi.diagnostics()
        assert d["source"].endswith("STAGE111Z31M")
        assert d["gdi_width_zero"]>0
        assert d["gdi_height_zero"]>0
        assert not d["original_font_in_process_verified"]
        assert not d["original_dpi_awareness_verified"]
        image=np.full((110,240,4),255,dtype=np.uint8)
        before=image.copy()
        rendered=gdi.draw_text(image,[
            dict(kind="x_tick",text="3800",x=20,y=16),
            dict(kind="y_tick",text="-150",x=100,y=44),
            dict(kind="x_name",text="Гц",x=160,y=80),
        ])
        assert rendered.shape==image.shape
        assert rendered.dtype==np.uint8
        assert np.all(rendered[:,:,3]==255)
        assert np.count_nonzero(rendered[:,:,:3]<255)>20
        np.testing.assert_array_equal(image,before)
        np.testing.assert_array_equal(rendered,gdi.draw_text(image,[
            dict(kind="x_tick",text="3800",x=20,y=16),
            dict(kind="y_tick",text="-150",x=100,y=44),
            dict(kind="x_name",text="Гц",x=160,y=80),
        ]))
    with pytest.raises(RuntimeError):
        gdi.text_width("0")


@pytest.mark.skipif(sys.platform!="win32",reason="Native GDI requires Windows")
def test_gdi_rejects_invalid_ink_and_bounded_params():
    with pytest.raises(ValueError):
        Win32SourceTextCanvas(font_height=13)
    with Win32SourceTextCanvas() as gdi:
        with pytest.raises(ValueError):
            gdi.draw_text(np.zeros((20,20,4),dtype=np.uint8),[])
        with pytest.raises(ValueError):
            gdi.draw_text(np.full((20,20,4),255,dtype=np.uint8),[
                dict(kind="x_tick",text="0",x=True,y=0)
            ])
        with pytest.raises(ValueError):
            gdi.text_width("x"*257)
