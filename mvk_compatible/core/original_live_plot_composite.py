"""Stage111Z31CG: one source TCo2Draw bitmap: grid -> real series -> frame.

Source-private Unit115:007CACB3..007CB4AA draws a WHITE 32bpp TCo2Draw
buffer, its horizontal/vertical gray grid, GDI text, series 0/1
per-pixel minmax strokes, then the black frame. TextOut is still rendered
by the adjacent Qt source-tick axes, NOT reproduced here. This module
combines the already audited source grid/series/AA engines into a bounded,
INCREMENTAL same-buffer image for the two ordinary pages.

Strictly read-only: no FIR, FFT, Power/Y, device, network, BIN or ZIP writes.
Original Win32/RTL/GDI/x87 pixel parity is NOT attested.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import numbers
import numpy as np

from .original_live_software_grid import (
    source_live_software_grid_bitmap, MAX_SOURCE_SOFTWARE_PIXELS,
)
from .tqgr_series_source_candidate import (
    source_tqgr_series_columns, MAX_SAMPLES as MAX_SERIES_SAMPLES,
)
from .tco2draw_raster_candidate import source_raster_rgba

SOURCE = "SOURCE_DERIVED_LIVE_TQGRAPHER_GRID_SERIES_FRAME_STAGE111Z31CG"
SERIES_RGB = (0, 0, 0)
FRAME_RGB = (0, 0, 0)
MAX_STEP_SEGMENTS = 256


def _real(value, label):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(label + " requires a finite real scalar")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(label + " cannot be infinite")
    return value


def _range(value, label):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(label + " requires two bounds")
    a, b = (_real(x, label) for x in value)
    if not a < b:
        raise ValueError(label + " requires an increasing view range")
    return (a, b)


@dataclass(frozen=True)
class LiveSourceBitmapPlan:
    """Independent source numerical plan; all arrays are immutable snapshots."""
    background_rgba: np.ndarray
    series_segments: tuple[tuple[float, float, float, float], ...]
    frame_segments: tuple[tuple[int, int, int, int], ...]
    width: int
    height: int
    source_series_sha256: str
    source_series_samples: int
    source_screen_x_inverted: bool
    view_x: tuple[float, float]
    view_y: tuple[float, float]
    provenance: str
    grid_source: str
    grid_sha256: str
    original_delphi_runtime_parity_verified: bool = False


def prepare_live_source_bitmap(
        values, *, view_x, view_y, width, height,
        x_start, x_scale, y_scale=1.0, x_inverted=False,
        provenance, expected_series_sha256):
    """Audit the source series *before* painting into the original grid.

    For inverted ADC X, source ScrLeft=Xmax, ScrWidth=-(Xmax-Xmin),
    as Unit128:0084B2F8. Qt inverts its own ViewBox transform, so its
    presentation adapter must reverse bitmap columns once again.
    """
    if (type(width) is not int or type(height) is not int
            or not 8 <= width <= 8192 or not 8 <= height <= 8192
            or width * height > MAX_SOURCE_SOFTWARE_PIXELS):
        raise ValueError("Bounded source bitmap logical dimensions required")
    if type(x_inverted) is not bool:
        raise ValueError("Native inverse X flag must be boolean")
    if (not isinstance(provenance, str) or not provenance
            or len(provenance) > 256):
        raise ValueError("Source series provenance missing")
    if (not isinstance(expected_series_sha256, str)
            or len(expected_series_sha256) != 64
            or any(ch not in "0123456789abcdef"
                   for ch in expected_series_sha256)):
        raise ValueError("Expected SHA256 of source TQGRSeries is required")
    xr = _range(view_x, "X")
    yr = _range(view_y, "Y")
    x_start = _real(x_start, "Source series XStart")
    x_scale = _real(x_scale, "Source series XScale")
    y_scale = _real(y_scale, "Source series YScale")
    if x_scale <= 0 or y_scale <= 0:
        raise ValueError("Native series scale must be positive")
    src = np.asarray(values)
    if (src.ndim != 1 or not 2 <= src.size <= MAX_SERIES_SAMPLES
            or src.dtype.kind not in "fi" or src.dtype.kind == "b"):
        raise ValueError("Full source Float32 TQGRSeries required")
    arr = np.array(src, dtype="<f4", order="C", copy=True)
    if not bool(np.isfinite(arr).all()):
        raise ValueError("Nonfinite TQGRSeries must not reach software renderer")
    digest = sha256(arr.tobytes()).hexdigest()
    if digest != expected_series_sha256:
        raise ValueError("TQGRSeries changed after Core/Qt source binding")

    grid = source_live_software_grid_bitmap(
        view_x=xr, view_y=yr, width=width, height=height)
    base = np.array(
        grid["rgba"][:, ::-1] if x_inverted else grid["rgba"],
        dtype=np.uint8, order="C", copy=True)
    # One-pixel margin keeps the Unit115 Frame inside bounded raster
    # and is a *Qt ViewBox inset candidate*, not an original PaintBox
    # pixel-coordinate acceptance.
    left, right, top, bottom = 1, width-2, 1, height-2
    screen_left = xr[1] if x_inverted else xr[0]
    screen_width = xr[0]-xr[1] if x_inverted else xr[1]-xr[0]
    projection = source_tqgr_series_columns(
        arr,
        scr_left=screen_left, scr_width=screen_width,
        scr_bottom=yr[0], scr_height=yr[1]-yr[0],
        x_start=x_start, x_scale=x_scale, y_scale=y_scale,
        pixel_left=left, pixel_right=right,
        pixel_top=top, pixel_bottom=bottom)
    segments = tuple(tuple(float(v) for v in stroke)
                     for stroke in projection["segments"])
    border = ((left,top,right,top),
              (right,top,right,bottom),
              (right,bottom,left,bottom),
              (left,bottom,left,top))
    base.setflags(write=False)
    return LiveSourceBitmapPlan(
        background_rgba=base,
        series_segments=segments,
        frame_segments=border,
        width=width, height=height,
        source_series_sha256=digest,
        source_series_samples=int(arr.size),
        source_screen_x_inverted=x_inverted,
        view_x=xr, view_y=yr, provenance=provenance,
        grid_source=grid["source"],
        grid_sha256=grid["rgba_sha256"])


class LiveSourceBitmapTask:
    """Incremental, reversible source TCo2Draw compositing.

    Each step does at most 256 source segments. A Qt timer can interleave
    user input between slices; no partially rendered bitmap is published.
    Cancelling the task discards its private image with no external writes.
    """
    def __init__(self, plan: LiveSourceBitmapPlan):
        if not isinstance(plan, LiveSourceBitmapPlan):
            raise ValueError("Independent source bitmap plan required")
        self.plan = plan
        self._rgba = np.array(plan.background_rgba, dtype=np.uint8,
                              order="C", copy=True)
        self._stage = 0  # 0 series, 1 frame, 2 completed
        self._index = 0
        self.slice_count = 0

    @property
    def done(self):
        return self._stage == 2

    def step(self, max_segments: int = 128):
        if (type(max_segments) is not int
                or not 1 <= max_segments <= MAX_STEP_SEGMENTS):
            raise ValueError("Source raster step must be bounded")
        if self.done:
            return True
        lines = (self.plan.series_segments if self._stage == 0
                 else self.plan.frame_segments)
        part = lines[self._index:self._index+max_segments]
        if part:
            self._rgba = source_raster_rgba(
                width=self.plan.width,height=self.plan.height,
                segments=part,
                ink=SERIES_RGB if self._stage == 0 else FRAME_RGB,
                initial_rgba=self._rgba)
            self._index += len(part)
            self.slice_count += 1
        if self._index >= len(lines):
            self._stage += 1
            self._index = 0
            # Empty source series are still a verified grid+frame.
            if self._stage == 1 and not self.plan.frame_segments:
                self._stage = 2
        return self.done

    def finish(self, max_segments: int = 128):
        while not self.step(max_segments=max_segments):
            pass
        return self.result()

    def result(self):
        if not self.done:
            raise ValueError("Cannot publish incomplete source bitmap")
        out = np.array(self._rgba, dtype=np.uint8, order="C", copy=True)
        out.setflags(write=False)
        return {
            "source": SOURCE,
            "rgba": out,
            "logical_size": (self.plan.width, self.plan.height),
            "view_x": self.plan.view_x,
            "view_y": self.plan.view_y,
            "source_series_sha256": self.plan.source_series_sha256,
            "source_series_samples": self.plan.source_series_samples,
            "source_series_provenance": self.plan.provenance,
            "source_grid_backend": self.plan.grid_source,
            "source_grid_sha256": self.plan.grid_sha256,
            "source_x_inverted": self.plan.source_screen_x_inverted,
            "source_software_grid_and_series_and_frame_one_bitmap": True,
            "source_draw_order": (
                "white", "horizontal_grid", "vertical_grid",
                "black_minmax_series", "black_frame"),
            "series_stroke_count": len(self.plan.series_segments),
            "frame_stroke_count": len(self.plan.frame_segments),
            "source_series_original_runtime_0ulp_verified": False,
            "source_textout_full_paintbox_implemented": False,
            "original_win32_gdi_pixel_parity_verified": False,
            "qt_canvas_original_paintbox_registration_verified": False,
            "rgba_sha256": sha256(out.tobytes()).hexdigest(),
            "raster_slices": self.slice_count,
        }
