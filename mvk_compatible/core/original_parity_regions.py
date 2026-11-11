"""Stage111Z31BF: strict offline regions for paired original/candidate captures.

No GUI input, Win32 execution, resize, crop-to-match or OCR. Only compares
unchanged RGBA arrays supplied from the user's private two-PID capture.
"""
from __future__ import annotations

import re
import numpy as np

MAX_ROIS = 32
MAX_PIXEL_COUNT = 10_000_000
ROI_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")


def _verified_rgba(value) -> tuple[int, int]:
    if (not isinstance(value, np.ndarray) or value.dtype != np.uint8
            or value.ndim != 3 or value.shape[-1] != 4):
        raise ValueError("Pair must contain UINT8 RGBA arrays")
    h, w = value.shape[:2]
    if w < 64 or h < 64 or w * h > MAX_PIXEL_COUNT:
        raise ValueError("Pair image dimensions outside source safety limits")
    if not bool(np.all(value[:, :, 3] == 255)):
        raise ValueError("A transparent or invalid RGBA image is not accepted")
    return w, h


def compare_source_regions(original, compatible, rois: list) -> dict:
    """Reject mismatched full-window dimensions without aligning images.

    ROI coordinates refer to the identical native pixel coordinate frame
    of both captured clients. They are NOT auto-derived from scaling/DPI.
    """
    original_wh = _verified_rgba(original)
    compatible_wh = _verified_rgba(compatible)
    if (not isinstance(rois, list) or not 1 <= len(rois) <= MAX_ROIS):
        raise ValueError("1..32 explicit ROI dictionaries required")
    if original_wh != compatible_wh:
        return {
            "rejected": True,
            "reason": "different client dimensions",
            "original_wh": list(original_wh),
            "compatible_wh": list(compatible_wh),
            "automatic_alignment_performed": False,
            "source_runtime_parity_verified": False,
        }
    w, h = original_wh
    seen = set()
    output = []
    for region in rois:
        if not isinstance(region, dict) or set(region) != {"name", "xywh"}:
            raise ValueError("ROI must have only name and xywh")
        name, area = region["name"], region["xywh"]
        if not isinstance(name, str) or not ROI_NAME.fullmatch(name) or name in seen:
            raise ValueError("Unsafe or duplicate ROI name")
        if (not isinstance(area, list) or len(area) != 4
                or any(type(v) is not int for v in area)):
            raise ValueError("ROI geometry must be four integers")
        x, y, width, height = area
        if (x < 0 or y < 0 or width < 1 or height < 1
                or x + width > w or y + height > h):
            raise ValueError("ROI outside original client bounds")
        seen.add(name)
        orig = original[y:y + height, x:x + width, :3]
        comp = compatible[y:y + height, x:x + width, :3]
        diff = np.abs(orig.astype(np.int16) - comp.astype(np.int16))
        equal = np.all(diff == 0, axis=2)
        output.append({
            "name": name,
            "xywh": area[:],
            "pixel_count": width * height,
            "exact_rgb_pixels": int(np.count_nonzero(equal)),
            "changed_pixels_any_channel_gt_1":
                int(np.count_nonzero(np.any(diff > 1, axis=2))),
            "average_abs_rgb_error": float(diff.mean()),
            "pixel_identical": bool(np.all(equal)),
        })
    return {
        "rejected": False,
        "original_wh": [w, h],
        "compatible_wh": [w, h],
        "region_results": output,
        "automatic_alignment_performed": False,
        "all_selected_regions_pixel_identical":
            all(row["pixel_identical"] for row in output),
        "source_runtime_parity_verified": False,
        "original_process_identity_independently_verified": False,
        "device_io_performed": False,
    }
