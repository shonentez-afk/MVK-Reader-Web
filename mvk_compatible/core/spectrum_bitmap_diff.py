"""Stage111Z31M offline pixel comparison of original/candidate spectrum crops.

Both RGBA arrays must already contain the SAME plot and same pixel scale.
This does not independently authenticate an original Windows capture.
No files, paths, raw pixels, or private data appear in returned report.
"""
from __future__ import annotations
import numpy as np

SOURCE="OFFLINE_SPECTRUM_SOURCE_BITMAP_DIFF_STAGE111Z31M"


def compare_spectrum_bitmap_crops(original,candidate,*,shift_radius=0):
    if type(shift_radius) is not int or not 0<=shift_radius<=5:
        raise ValueError("pixel shift search must be 0..5")
    if (not isinstance(original,np.ndarray) or
            not isinstance(candidate,np.ndarray) or
            original.dtype!=np.uint8 or candidate.dtype!=np.uint8 or
            original.ndim!=3 or candidate.ndim!=3 or
            original.shape!=candidate.shape or original.shape[2]!=4 or
            min(original.shape[:2])<64 or
            original.shape[0]*original.shape[1]>6_000_000 or
            not np.all(original[:,:,3]==255) or
            not np.all(candidate[:,:,3]==255)):
        raise ValueError("same-sized opaque RGBA crop must be provided")
    h,w=original.shape[:2]
    if shift_radius*2>=min(h,w):
        raise ValueError("shift exceeds plot dimensions")
    best=None
    for dy in range(-shift_radius,shift_radius+1):
        for dx in range(-shift_radius,shift_radius+1):
            # Compare candidate source at (x,y) against original at
            # (x+dx,y+dy), with strictly bounded overlapping view.
            ox=max(0,dx)
            cx=max(0,-dx)
            oy=max(0,dy)
            cy=max(0,-dy)
            width=w-abs(dx)
            height=h-abs(dy)
            a=original[oy:oy+height,ox:ox+width,:3]
            b=candidate[cy:cy+height,cx:cx+width,:3]
            fg=np.any(a!=255,axis=2)|np.any(b!=255,axis=2)
            pixels=int(fg.sum())
            if pixels==0:
                continue
            diff=np.abs(a.astype(np.int16)-b.astype(np.int16))
            score=float(diff[fg].mean())
            # Penalize shifts that trivially crop away hard mismatches.
            score+=float(h*w-width*height)/(h*w)*2.0
            row={
                "candidate_to_original_offset_px":[dx,dy],
                "overlap_pixels":width*height,
                "foreground_pixels":pixels,
                "exact_rgb_pixels_on_foreground":int(
                    np.count_nonzero(np.all(diff==0,axis=2)&fg)),
                "rgb_channel_mean_absolute_error_on_foreground":
                    float(diff[fg].mean()),
                "foreground_pixels_with_any_channel_error_gt_1":int(
                    np.count_nonzero(np.any(diff>1,axis=2)&fg)),
                "foreground_pixels_with_any_channel_error_gt_8":int(
                    np.count_nonzero(np.any(diff>8,axis=2)&fg)),
                "exact_rgb_pixels_on_overlap":int(
                    np.count_nonzero(np.all(diff==0,axis=2))),
                "score":score,
            }
            if best is None or (score,abs(dx)+abs(dy))<(
                    best["score"],sum(map(abs,best["candidate_to_original_offset_px"]))):
                best=row
    return {
        "source":SOURCE,
        "candidate_image_shape_wh":[w,h],
        "best_match":best,
        "no_informative_ink":best is None,
        "original_capture_provenance_independently_authenticated":False,
        "original_gdi_runtime_font_proven":False,
        "original_dpi_awareness_proven":False,
        "source_raw_pixels_or_paths_exported":False,
        "one_screen_crop_only":True,
        "complete_mvkview_spectrum_parity_verified":False,
    }
