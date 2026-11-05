"""Stage111Z31G: bounded source-derived TCo2Draw software line raster.

Only abstracted source logic is public; original Delphi material and
measurements stay private. Native x87/PixelRect/DPI parity remains unproven.
"""
from __future__ import annotations
import math
import numbers
import numpy as np
from .tco2draw_grid_source import GRID_LINE_RGB, BACKGROUND_RGB, _rgb

SOURCE="APP_DERIVED_TCO2DRAW_007C98B4_007C9A30_RASTER"
MAX_PIXELS=6000000

def contract():
    return dict(source=SOURCE, scanline_32bit=True, x_major="007C98B4",
                y_major="007C9A30", blend="007C9808",
                neighbors=3, excludes_endpoint=True,
                original_delphi_pixel_parity_verified=False,
                original_x87_runtime_rounding_verified=False,
                original_bitmap_scanline_orientation_verified=False)

def _f32(v):
    if isinstance(v,bool) or not isinstance(v,numbers.Real):
        raise ValueError("finite real coordinate required")
    n=float(v)
    if not math.isfinite(n) or abs(n)>1e8:
        raise ValueError("coordinate outside safe range")
    return float(np.float32(n))

def _line(image, x0,y0,x1,y1,ink):
    if x0==x1 and y0==y1:
        return
    dx=x0-x1
    dy=y1-y0
    length=math.hypot(dx,dy)
    if length<=0:
        return
    cosa=float(np.float32(dy/length))
    sina=float(np.float32(dx/length))
    pi=float(np.float32((x1*y0-y1*x0)/length))
    height,width=image.shape[:2]
    def paint(x,y,dist):
        factor=min(1.0,float(np.float32(math.sqrt(abs(dist)))))
        if factor>=1:
            return
        old=image[y,x,:3]
        image[y,x,:3]=[int(a+(int(b)-a)*factor)
                        for a,b in zip(ink,old)]
    if abs(x1-x0)>abs(y1-y0):
        if sina==0:
            return
        lo,hi=(round(x0),round(x1)-1) if x1>=x0 else (
            round(x1)+1,round(x0))
        for x in range(max(0,lo),min(width-1,hi)+1):
            tmp=float(np.float32(x*cosa+pi))
            y0p=round(-tmp/sina)
            if 0<y0p<height-1:
                for y in (y0p,y0p-1,y0p+1):
                    paint(x,y,y*sina+tmp)
    else:
        if cosa==0:
            return
        lo,hi=(round(y0),round(y1)-1) if y1>=y0 else (
            round(y1)+1,round(y0))
        for y in range(max(0,lo),min(height-1,hi)+1):
            tmp=float(np.float32(y*sina+pi))
            x0p=round(-tmp/cosa)
            if 0<x0p<width-1:
                for x in (x0p,x0p-1,x0p+1):
                    paint(x,y,x*cosa+tmp)

def source_raster_rgba(*,width,height,segments,ink=GRID_LINE_RGB,
                       background=BACKGROUND_RGB,initial_rgba=None):
    """Return (H,W,4) RGBA in Qt LOGICAL pixels, +Y downward.

    Optional initial_rgba composes on a COPIED existing 32bpp scanline
    bitmap; original layer order is retained, input never mutated.
    """
    if (any(isinstance(v,bool) or not isinstance(v,numbers.Integral)
            for v in (width,height))):
        raise ValueError("integer image dimensions required")
    width,height=int(width),int(height)
    if not (4<=width<=10000 and 4<=height<=10000
            and width*height<=MAX_PIXELS):
        raise ValueError("image exceeds bounded research viewport")
    if not isinstance(segments,(tuple,list)) or len(segments)>2048:
        raise ValueError("bounded segment list required")
    ink=_rgb(ink,"ink")
    background=_rgb(background,"background")
    normalized=[]
    for coords in segments:
        if not isinstance(coords,(tuple,list)) or len(coords)!=4:
            raise ValueError("four coordinates required per segment")
        normalized.append(tuple(_f32(v) for v in coords))
    if initial_rgba is None:
        rgba=np.empty((height,width,4),dtype=np.uint8)
        rgba[:,:,:3]=background
        rgba[:,:,3]=255
    else:
        # Original TCo2Draw paints GRID -> SERIES -> FRAME onto ONE
        # 32-bit scanline buffer. A validated copy lets independent
        # passes reproduce the same ordered RGB blending, without
        # modifying caller-owned frames or archived measurement data.
        if (not isinstance(initial_rgba,np.ndarray)
                or initial_rgba.dtype!=np.uint8
                or initial_rgba.shape!=(height,width,4)
                or not np.all(initial_rgba[:,:,3]==255)):
            raise ValueError("initial_rgba must be opaque HxWx4 uint8")
        rgba=np.array(initial_rgba,copy=True,order='C')
    for coords in normalized:
        _line(rgba,*coords,ink)
    return rgba

def source_grid_segments(*,x_ticks,y_ticks,view_x,view_y,width,height):
    """Map source 10x10 grid to Qt ViewBox, NOT Delphi runtime PixelRect."""
    if not isinstance(width,int) or not isinstance(height,int):
        raise ValueError("integer viewport required")
    x0,x1=map(_f32,view_x)
    y0,y1=map(_f32,view_y)
    if not x1>x0 or not y1>y0:
        raise ValueError("positive viewport span required")
    if (not isinstance(x_ticks,(tuple,list)) or
            not isinstance(y_ticks,(tuple,list)) or
            len(x_ticks)+len(y_ticks)>2048):
        raise ValueError("bounded ticks required")
    lines=[]
    for tick in x_ticks:
        t=_f32(tick)
        if t<x0-0.0001 or t>x1+0.0001:
            raise ValueError("tick outside X range")
        pos=(t-x0)/(x1-x0)*(width-1)
        lines.append((pos,0.0,pos,float(height-1)))
    for tick in y_ticks:
        t=_f32(tick)
        if t<y0-0.0001 or t>y1+0.0001:
            raise ValueError("tick outside Y range")
        pos=(y1-t)/(y1-y0)*(height-1)
        lines.append((0.0,pos,float(width-1),pos))
    return tuple(lines)
