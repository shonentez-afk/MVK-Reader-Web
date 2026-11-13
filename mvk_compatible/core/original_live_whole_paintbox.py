"""Stage111Z31CJ: exact source GRID/TextOut event interleaving candidate.

Recovered directly from operator-private _Unit115.pas TQGrapher.Draw:
007CAD77..007CAE35 each horizontal software grid stroke is followed
by its y-tick TextOut; 007CAEA9..007CAF6B does the same for positive
ScrWidth x ticks; negative ScrWidth uses the reverse loop
007CAF76..007CB080; 007CB086..007CB129 writes YName then XName;
007CB12F..007CB3E5 writes source per-pixel series, then the frame.
The tick/grid micro-order is retained in a SINGLE 32-bit PaintBox.

This models source control flow; exact original Win32 GDI font, x87,
RTL locale, physical DPI, pixel AA/parity remain unverified.
No Qt, hardware access, published private PAS/DFM/BIN, or source writes.
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
    "white_32bpp_bitmap",
    "each_horizontal_source_grid_line_then_matching_y_tick_textout",
    "each_vertical_source_grid_line_then_matching_x_tick_textout_signed_scrwidth",
    "y_axis_name_textout", "x_axis_name_textout",
    "source_minmax_series", "black_frame")
MAX_STEP_SEGMENTS = 256


@dataclass(frozen=True)
class WholePaintboxPlan:
    width: int
    height: int
    source_text_plan: dict
    horizontal_grid: tuple
    vertical_grid: tuple
    horizontal_tick_events: tuple
    vertical_tick_events: tuple
    axis_name_events: tuple
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
    # Source has two distinct 007CAE4E branches. For negative
    # ScrWidth, 007CAFBE..007CB080 DECREMENTS the source index,
    # drawing x tick lines right-to-left in index/value order.
    if inverted:
        vertical = tuple(reversed(vertical))
    original_events = tuple(source_text_plan["events"])
    y_events = tuple(e for e in original_events if e["kind"]=="y_tick")
    x_events = tuple(e for e in original_events if e["kind"]=="x_tick")
    name_events = tuple(e for e in original_events
                        if e["kind"] in ("y_name","x_name"))
    if len(y_events) not in (0,len(horizontal)):
        raise ValueError("TQGrapher y line/TextOut source count mismatch")
    if len(x_events) not in (0,len(vertical)):
        raise ValueError("TQGrapher x line/TextOut source count mismatch")
    if (len(name_events)>2 or
            tuple(e["kind"] for e in name_events)
                not in ((),("y_name",),("x_name",),
                        ("y_name","x_name"))):
        raise ValueError("Unexpected source axis-name TextOut order")
    if x_events and inverted:
        x_events = tuple(reversed(x_events))
    # Pair source LineTo with TextOut at the exact iteration that
    # originally emitted it, rather than a bulk text pass.
    for events, ticks in ((y_events,grid["y_grid_ticks"]),
                          (x_events,tuple(reversed(grid["x_grid_ticks"]))
                           if inverted else grid["x_grid_ticks"])):
        if events and not all(
                float(np.float32(e["source_value"])) ==
                float(np.float32(v))
                for e,v in zip(events,ticks)):
            raise ValueError("Grid and TextOut value mapping diverged")
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
        horizontal_tick_events=y_events,vertical_tick_events=x_events,
        axis_name_events=name_events,
        series_segments=series,frame_segments=frame,
        source_series_sha256=digest,source_series_samples=int(samples.size),
        source_series_provenance=provenance,inverted_x=inverted,
        view_x=(_single(min(scrleft,scrleft+scrwidth)),
                _single(max(scrleft,scrleft+scrwidth))),
        view_y=(scrbottom,_single(scrbottom+scrheight)))


class WholePaintboxTask:
    """Bounded source Draw state. Never publishes a partially drawn bitmap.

    Original sequence:
      0: each Y grid line + matching Y tick TextOut
      1: each X grid line + matching X tick TextOut (reverse for ADC)
      2: YName then XName TextOut
      3: full min/max series
      4: four black frame lines
      5: complete
    Platform GDI is deliberately injected and never imported by Core.
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
        self.draw_trace=[]
        self._renderer_closed=False

    def close(self):
        """Release a native GDI DC on finish, cancellation or exception."""
        if self._renderer_closed:
            return
        self._renderer_closed=True
        release=getattr(self._renderer,"close",None)
        if callable(release):
            release()

    @property
    def done(self):
        return self._pass == 5

    def _textout(self,event):
        # A verified per-frame Win32 GDI backend may update only the
        # source glyph ROI IN PLACE. This is a private uncommitted raster:
        # if TextOut fails it is discarded, never presented to Qt.
        candidate=self._renderer(self._rgba,(event,))
        if (not isinstance(candidate,np.ndarray) or
                candidate.dtype!=np.uint8 or
                candidate.shape!=self._rgba.shape or
                not bool(np.all(candidate[:,:,3]==255))):
            raise ValueError("TextOut returned nonopaque or invalid source canvas")
        self._rgba=np.ascontiguousarray(candidate)
        self.textout_calls += 1
        self.draw_trace.append(("textout",event["kind"],
                                event["source_value"]
                                if "source_value" in event else None))

    def _draw_line(self,stroke,ink):
        self._rgba=source_raster_rgba(
            width=self.plan.width,height=self.plan.height,
            segments=(stroke,),initial_rgba=self._rgba,ink=ink)

    def step(self,max_segments=128):
        if type(max_segments) is not int or not 1<=max_segments<=MAX_STEP_SEGMENTS:
            raise ValueError("Bounded source raster step count required")
        if self.done:
            return True
        p=self.plan
        if self._pass in (0,1):
            horizontal=self._pass==0
            strokes=p.horizontal_grid if horizontal else p.vertical_grid
            events=(p.horizontal_tick_events if horizontal
                    else p.vertical_tick_events)
            limit=min(self._offset+max_segments,len(strokes))
            for index in range(self._offset,limit):
                self._draw_line(strokes[index],GRID_LINE_RGB)
                self.draw_trace.append((
                    "grid_horizontal" if horizontal else "grid_vertical",
                    index,None))
                if events:
                    self._textout(events[index])
            self._offset=limit
            if self._offset==len(strokes):
                self._pass+=1
                self._offset=0
        elif self._pass==2:
            events=p.axis_name_events
            limit=min(self._offset+max_segments,len(events))
            for index in range(self._offset,limit):
                self._textout(events[index])
            self._offset=limit
            if self._offset==len(events):
                self._pass=3
                self._offset=0
        else:
            strokes=(p.series_segments if self._pass==3
                     else p.frame_segments)
            limit=min(self._offset+max_segments,len(strokes))
            part=strokes[self._offset:limit]
            if part:
                self._rgba=source_raster_rgba(
                    width=p.width,height=p.height,
                    segments=part,
                    ink=(0,0,0),initial_rgba=self._rgba)
                # One short trace marker per series/frame SLICE, never
                # one marker per FFT sample or source bin.
                self.draw_trace.append((
                    "series" if self._pass==3 else "frame",
                    len(part),None))
            self._offset=limit
            if self._offset==len(strokes):
                self._pass+=1
                self._offset=0
        self.slices+=1
        if self.done:
            self.close()
        return self.done

    def finish(self,max_segments=128):
        try:
            while not self.step(max_segments=max_segments):
                pass
            return self.result()
        finally:
            self.close()

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
            # Keep accepted CG source screen readout for source-driven
            # pan/zoom regression. This is only metadata, not a newly
            # computed pixel transform or numerical resampling.
            "view_x":p.view_x,
            "view_y":p.view_y,
            "source_grid_segment_count":(
                len(p.horizontal_grid)+len(p.vertical_grid)),
            "series_stroke_count":len(p.series_segments),
            "frame_stroke_count":len(p.frame_segments),
            "textout_calls":self.textout_calls,
            "source_draw_order":ORIGINAL_DRAW_ORDER,
            "source_interleaved_tick_textout":True,
            "source_negative_scrwidth_reverse_x_loop":p.inverted_x,
            "source_gdi_textout_per_matching_grid_tick":True,
            "source_interleaved_tick_count":(
                len(p.horizontal_tick_events)+len(p.vertical_tick_events)),
            "source_axis_name_text_count":len(p.axis_name_events),
            "source_draw_trace":tuple(self.draw_trace),
            "source_trace_is_source_derived_candidate":True,
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
