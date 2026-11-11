"""Stage111Z31BA: no original-app execution, source-code or live HWND in CI."""
import numpy as np
import pytest

from tools.research.compare_running_mvkview_windows import (
    FORMAT, image_comparison_summary, _native,
)


def test_identical_synthetic_images_do_not_prove_complete_original_parity():
    frame=np.full((100,120,4),255,dtype=np.uint8)
    frame[20:35,15:21,:3]=0
    report=image_comparison_summary(frame,frame.copy())
    assert report["format"]==FORMAT
    assert report["identical_client_pixel_dimensions"]
    assert report["unshifted_exact_rgb_pixels"]==120*100
    assert report["unshifted_pixel_identical_this_capture"]
    assert not report["full_window_1to1_verified"]
    assert not report["original_executable_identity_independently_verified"]
    assert not report["automatic_scaling_or_alignment_performed"]


def test_nonidentical_synthetic_clients_fail_closed_without_auto_resize():
    original=np.full((120,180,4),255,dtype=np.uint8)
    candidate=np.full((120,179,4),255,dtype=np.uint8)
    result=image_comparison_summary(original,candidate)
    assert not result["identical_client_pixel_dimensions"]
    assert result["comparison_rejected_reason"]=="different client dimensions"
    assert "unshifted_exact_rgb_pixels" not in result


def test_pixel_mismatch_scored_without_modifying_original():
    original=np.full((80,100,4),255,dtype=np.uint8)
    candidate=original.copy()
    candidate[23,65,:3]=[0,0,0]
    before=original.copy()
    result=image_comparison_summary(original,candidate)
    assert not result["unshifted_pixel_identical_this_capture"]
    assert result["unshifted_pixels_any_channel_gt_1"]==1
    assert result["unshifted_exact_rgb_pixels"]==7999
    np.testing.assert_array_equal(original,before)


def test_untrusted_transparent_or_unbounded_captures_are_rejected():
    opaque=np.full((80,100,4),255,dtype=np.uint8)
    transparent=opaque.copy()
    transparent[0,0,3]=0
    with pytest.raises(ValueError):
        image_comparison_summary(transparent,opaque)
    with pytest.raises(ValueError):
        image_comparison_summary(opaque[:10],opaque)
    with pytest.raises(ValueError):
        image_comparison_summary(opaque.astype(np.float32),opaque)


def test_windows_capture_backend_not_invoked_on_linux():
    import sys
    if sys.platform!="win32":
        with pytest.raises(RuntimeError):
            _native()
