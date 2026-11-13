"""Stage111Z31CI: one full PaintBox TCo2Draw + native TextOut bitmap.

Reconstructs the original *ordering* in user-private _Unit115.pas:
TCo2Draw.Create(white) -> horizontal/vertical grid -> TCanvas.TextOut
with inherited PaintBox font -> per-pixel TQGRSeries min/max strokes ->
four black plot frame segments -> display. Supports native negative ADC
ScrWidth. This source-geometry candidate is **not** a claim of Win32
TCanvas/GDI/x87, physical DPI or original process pixel parity.

No Qt, Win32, connected hardware, original exe or private PAS/DFM assets.
The raster receives SHA-checked Float32 samples only, never mutates data.
The only UI-specific operation, TextOut, is an injected bounded callback
and is executed between grid and series passes.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import numpy as np

from .tco2draw_raster_candidate import source_raster_rgba
from .tco2draw_grid_source import GRID_LINE_RGB, BACKGROUND_RGB
from .tqgr_series_source_candidate import (
    source_tqgr_series_columns, MAX_SAMPLES,
)
from .original_live_paintbox_text import (
    SOURCE as SOURCE_TEXT_PLAN, MAX_LABEL_CANVAS_PIXELS,
)

SOURCE = "SOURCE_DERIVED_LIVE_FULL_PAINTBOX_TCO2DRAW_TEXTOUT_STAGE111Z31CI"
ORIGINAL_DRAW_ORDER = (
    "white_32bpp_bitmap", "horizontal_source_grid",
    "vertical_source_grid", "canvas_textout",
    "source_minmax_series", "black_frame")
MAX_STEP_SEGMENTS = 256


@dataclass(frozen=True)
class WholePaintboxPlan:
    width: int
    height: int
    source_text_plan: dict
    horizontal_grid: tuple
    vertical_grid: tuple
    series_segments: tuple
    frame_segments: tuple
    source_series_sha256: str
    source_series_samples: int
    source_series_provenance: str
    inverted_x: bool
    view_x: tuple
    view_y: tuple


def _single(value):
    value = float(np.float32(float(value)))
    if not math.isfinite(value):
        raise ValueError("Source Single view coordinate overflow")
    return value


def prepare_whole_paintbox_plan(
        values, *, source_text_plan, x_start, x_scale, y_scale=1.0,
        provenance, expected_series_sha256):
    """Use measured, shared source canvas and grid for ALL raster passes."""
    if not isinstance(source_text_plan,dict) or (
            source_text_plan.get("source") != SOURCE_TEXT_PLAN):
        raise ValueError("Independent source TextOut/PaintBox contract required")
    canvas = source_text_plan["canvas"]
    grid = source_text_plan["grid"]
    if not isinstance(canvas,dict) or not isinstance(grid,dict):
        raise ValueError("Measured PaintBox geometry and grid required")
    w,h = canvas["canvas_width"],canvas["canvas_height"]
    if (type(w) is not int or type(h) is not int
            or w < 64 or h < 64 or w*h > MAX_LABEL_CANVAS_PIXELS):
        raise ValueError("Full PaintBox pixel budget exceeded")
    l,r,t,b = (canvas[k] for k in
        ("pixel_left","pixel_right","pixel_top","pixel_bottom"))
    if not (all(type(k) is int for k in (l,r,t,b))
            and 1 <= l < r < w-1 and 1 <= t < b < h-1):
        raise ValueError("Source font-based PixelRect invalid")
    if type(source_text_plan.get("source_x_inverted")) is not bool:
        raise ValueError("Original signed ScrWidth orientation required")
    inverted = source_text_plan["source_x_inverted"]
    scrleft = _single(canvas["scr_left"])
    scrwidth = _single(canvas["scr_width"])
    scrbottom = _single(canvas["scr_bottom"])
    scrheight = _single(canvas["scr_height"])
    if abs(scrwidth) < 1e-6 or scrheight < 1e-6 or ((scrwidth < 0) != inverted):
        raise ValueError("Measured reverse-X screen inconsistent")
    if (not isinstance(provenance,str) or not provenance
            or len(provenance)>256):
        raise ValueError("Verified source series provenance missing")
    if (not isinstance(expected_series_sha256,str) or
            len(expected_series_sha256)!=64 or
            any(x not in "0123456789abcdef" for x in expected_series_sha256)):
        raise ValueError("Canonical source Float32 SHA256 required")
    src = np.asarray(values)
    if (src.ndim != 1 or not 2 <= src.size <= MAX_SAMPLES
            or src.dtype.kind not in "fi" or src.dtype.kind == "b"):
        raise ValueError("Full, bounded original TQGRSeries required")
    samples = np.array(src,dtype="<f4",order="C",copy=True)
    if not bool(np.isfinite(samples).all()):
        raise ValueError("Nonfinite original series cannot be rasterized")
    digest = sha256(samples.tobytes()).hexdigest()
    if digest != expected_series_sha256:
        raise ValueError("Source series SHA differs from independent Core")
    # Coordinates from Unit115 ScrLeft/ScrWidth and the same measured
    # PixelRect as TextOut: NO second Qt-only 1px projected frame.
    xscale = _single((r-l)/scrwidth)
    yscale_pixel = _single((b-t)/scrheight)
    def px_x(v):
        return _single(l + _single(_single(v-scrleft)*xscale))
    def px_y(v):
        return _single(b - _single(_single(v-scrbottom)*yscale_pixel))
    # Unit115 paints horizontal grid first, then vertical (and TextOut
    # is interleaved in the original loop; the two passes retain their
    # already-established source layer order).
    horizontal = tuple((float(l),px_y(v),float(r),px_y(v))
                       for v in grid["y_grid_ticks"])
    vertical = tuple((px_x(v),float(t),px_x(v),float(b))
                     for v in grid["x_grid_ticks"])
    projection=source_tqgr_series_columns(
        samples,scr_left=scrleft,scr_width=scrwidth,
        scr_bottom=scrbottom,scr_height=scrheight,
        x_start=x_start,x_scale=x_scale,y_scale=y_scale,
        pixel_left=l,pixel_right=r,pixel_top=t,pixel_bottom=b)
    series = tuple(tuple(map(float,seg))
                   for seg in projection["segments"])
    frame=((l,t,r,t),(r,t,r,b),(r,b,l,b),(l,b,l,t))
    return WholePaintboxPlan(
        width=w,height=h,source_text_plan=source_text_plan,
        horizontal_grid=horizontal,vertical_grid=vertical,
        series_segments=series,frame_segments=frame,
        source_series_sha256=digest,source_series_samples=int(samples.size),
        source_series_provenance=provenance,inverted_x=inverted,
        view_x=(_single(min(scrleft,scrleft+scrwidth)),
                _single(max(scrleft,scrleft+scrwidth))),
        view_y=(scrbottom,_single(scrbottom+scrheight)))


class WholePaintboxTask:
    """Cancellable, bounded graphics state; publish only completed bytes.

    Finite-step scheduling is driven by existing Qt QTimer; text renderer
    is invoked *once* in the same buffer, after grid and before series.
    """
    def __init__(self,plan,text_renderer):
        if not isinstance(plan,WholePaintboxPlan):
            raise ValueError("Source PaintBox plan required")
        if not callable(text_renderer):
            raise ValueError("Bounded platform TextOut callback required")
        self.plan=plan
        self._renderer=text_renderer
        self._rgba=np.full((plan.height,plan.width,4),255,dtype=np.uint8)
        self._pass=0
        self._offset=0
        self.slices=0
        self.textout_calls=0

    @property
    def done(self):
        return self._pass == 5

    def step(self,max_segments=128):
        if type(max_segments) is not int or not 1<=max_segments<=MAX_STEP_SEGMENTS:
            raise ValueError("Bounded source raster step count required")
        if self.done:
            return True
        if self._pass == 2:
            # The original TCanvas draws glyphs into the same opaque
            # bitmap. Only this point in the drawing order may call GDI.
            before=self._rgba.copy(order="C")
            candidate=self._renderer(before,self.plan.source_text_plan["events"])
            if (not isinstance(candidate,np.ndarray) or
                    candidate.dtype!=np.uint8 or
                    candidate.shape!=self._rgba.shape or
                    not bool(np.all(candidate[:,:,3]==255))):
                raise ValueError("TextOut returned nonopaque or invalid source canvas")
            self._rgba=np.array(candidate,dtype=np.uint8,order="C",copy=True)
            self.textout_calls+=1
            self._pass=3
            self.slices+=1
            return False
        strokes=(
            self.plan.horizontal_grid if self._pass==0 else
            self.plan.vertical_grid if self._pass==1 else
            self.plan.series_segments if self._pass==3 else
            self.plan.frame_segments)
        piece=strokes[self._offset:self._offset+max_segments]
        if piece:
            ink = GRID_LINE_RGB if self._pass < 2 else (0,0,0)
            self._rgba=source_raster_rgba(
                width=self.plan.width,height=self.plan.height,
                segments=piece,initial_rgba=self._rgba,ink=ink)
            self._offset += len(piece)
        if self._offset >= len(strokes):
            self._offset=0
            self._pass+=1
        self.slices+=1
        return self.done

    def finish(self,max_segments=128):
        while not self.step(max_segments=max_segments):
            pass
        return self.result()

    def result(self):
        if not self.done:
            raise ValueError("Cannot publish a partially composed PaintBox")
        pixels=np.ascontiguousarray(self._rgba)
        pixels.setflags(write=False)
        p=self.plan
        return {
            "source": SOURCE,
            "rgba":pixels,
            "full_paintbox_width":p.width,
            "full_paintbox_height":p.height,
            "canvas":p.source_text_plan["canvas"],
            "text_plan":p.source_text_plan,
            "textout_event_count":len(p.source_text_plan["events"]),
            "textout_backend":p.source_text_plan["font_metrics_provenance"],
            "source_x_inverted":p.inverted_x,
            "source_series_samples":p.source_series_samples,
            "source_series_sha256":p.source_series_sha256,
            "source_series_provenance":p.source_series_provenance,
            "source_grid_segment_count":(
                len(p.horizontal_grid)+len(p.vertical_grid)),
            "series_stroke_count":len(p.series_segments),
            "frame_stroke_count":len(p.frame_segments),
            "textout_calls":self.textout_calls,
            "source_draw_order":ORIGINAL_DRAW_ORDER,
            "whole_paintbox_grid_text_series_frame_one_bitmap":True,
            "source_gdi_textout_interposed_before_series":True,
            "original_exe_runtime_font_verified":False,
            "original_dpi_awareness_verified":False,
            "original_rtl_formatfloat_parity_verified":False,
            "original_x87_ulp_parity_verified":False,
            "original_win32_pixel_parity_verified":False,
            "qt_canvas_original_paintbox_registration_verified":False,
            "rgba_sha256":sha256(pixels.tobytes()).hexdigest(),
            "raster_slices":self.slices,
        }
