"""Original-TCanvas-compatible Windows GDI glyph candidate (Stage111Z31M).

Original _Unit115 007CACEE copies PaintBox.Canvas.Font to 32bpp bitmap,
then invokes TCanvas.TextOut. DFM: Tahoma -13, DEFAULT_CHARSET, PPI96.
Runtime original Font, DPI mode and PixelRect remain UNVERIFIED.
This module never connects to hardware or accesses the original process.
"""
from __future__ import annotations
import ctypes
import sys
import numpy as np

SOURCE="SOURCE_DERIVED_WIN32_GDI_TEXTOUT_STAGE111Z31M"
MAX_PIXELS=6_000_000


class _BIH(ctypes.Structure):
    _fields_=[
        ("biSize",ctypes.c_uint32),("biWidth",ctypes.c_int32),
        ("biHeight",ctypes.c_int32),("biPlanes",ctypes.c_uint16),
        ("biBitCount",ctypes.c_uint16),("biCompression",ctypes.c_uint32),
        ("biSizeImage",ctypes.c_uint32),("biXPelsPerMeter",ctypes.c_int32),
        ("biYPelsPerMeter",ctypes.c_int32),("biClrUsed",ctypes.c_uint32),
        ("biClrImportant",ctypes.c_uint32),
    ]


class _BI(ctypes.Structure):
    _fields_=[("bmiHeader",_BIH),("bmiColors",ctypes.c_uint32*1)]


class _SIZE(ctypes.Structure):
    _fields_=[("cx",ctypes.c_int32),("cy",ctypes.c_int32)]


def native_gdi_supported():
    return sys.platform=="win32"


class Win32SourceTextCanvas:
    """An ephemeral Windows GDI DC with DFM-derived font and bitmap.

    No assumed original runtime font parity. Use with context manager.
    """
    def __init__(self,*,font_face="Tahoma",font_height=-13,font_quality=0):
        if not native_gdi_supported():
            raise RuntimeError("GDI drawing requires native Windows")
        if (not isinstance(font_face,str) or not font_face or
                len(font_face)>32 or "\x00" in font_face):
            raise ValueError("invalid bounded font family")
        if type(font_height) is not int or not -128<=font_height<=-5:
            raise ValueError("invalid negative logical font height")
        if type(font_quality) is not int or font_quality not in (0,3,4,5):
            raise ValueError("invalid explicit font quality")
        self.font_face=font_face
        self.font_height=font_height
        self.font_quality=font_quality
        gdi=ctypes.WinDLL("gdi32",use_last_error=True)
        self._gdi=gdi
        def p(name,res,args):
            fn=getattr(gdi,name)
            fn.restype=res
            fn.argtypes=args
            return fn
        H=ctypes.c_void_p
        I=ctypes.c_int
        self._dc_new=p("CreateCompatibleDC",H,[H])
        self._dc_del=p("DeleteDC",I,[H])
        self._font_new=p("CreateFontW",H,[I]*5+[ctypes.c_uint]*8+[ctypes.c_wchar_p])
        self._select=p("SelectObject",H,[H,H])
        self._delete=p("DeleteObject",I,[H])
        self._extent=p("GetTextExtentPoint32W",I,[H,ctypes.c_wchar_p,I,ctypes.POINTER(_SIZE)])
        self._dib=p("CreateDIBSection",H,[H,ctypes.POINTER(_BI),ctypes.c_uint,ctypes.POINTER(H),H,ctypes.c_uint])
        self._text=p("TextOutW",I,[H,I,I,ctypes.c_wchar_p,I])
        self._bk=p("SetBkMode",I,[H,I])
        self._color=p("SetTextColor",ctypes.c_uint32,[H,ctypes.c_uint32])
        self._align=p("SetTextAlign",ctypes.c_uint32,[H,ctypes.c_uint])
        self._dc=self._dc_new(None)
        self._font=None
        self._oldfont=None
        self._closed=False
        if not self._dc:
            raise OSError("CreateCompatibleDC failed")
        try:
            self._font=self._font_new(
                font_height,0,0,0,400,0,0,0,1,0,0,font_quality,0,font_face)
            if not self._font:
                raise OSError("CreateFontW failed")
            self._oldfont=self._select(self._dc,self._font)
            if not self._oldfont or not self._bk(self._dc,1):
                raise OSError("SelectObject font or transparent background failed")
            self._color(self._dc,0x000000)
            self._align(self._dc,0)
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

    def close(self):
        if self._closed:
            return
        self._closed=True
        if self._dc and self._oldfont:
            self._select(self._dc,self._oldfont)
        if self._font:
            self._delete(self._font)
            self._font=None
        if self._dc:
            self._dc_del(self._dc)
            self._dc=None

    def _textsize(self,text):
        if self._closed:
            raise RuntimeError("GDI DC already closed")
        if not isinstance(text,str) or len(text)>256 or "\x00" in text:
            raise ValueError("bounded original string required")
        size=_SIZE()
        if not self._extent(self._dc,text,len(text),ctypes.byref(size)):
            raise OSError("GetTextExtentPoint32W failed")
        return int(size.cx),int(size.cy)

    def text_width(self,text):
        return self._textsize(text)[0]

    def text_height(self,text):
        return self._textsize(text)[1]

    def diagnostics(self):
        return dict(
            source=SOURCE,backend="Win32 GetTextExtentPoint32W/TextOutW",
            requested_font_face=self.font_face,
            requested_font_height=self.font_height,
            requested_font_quality=self.font_quality,
            gdi_width_zero=self.text_width("0"),
            gdi_width_sixdecimals=self.text_width("0.000000"),
            gdi_height_zero=self.text_height("0"),
            original_font_in_process_verified=False,
            original_dpi_awareness_verified=False,
            pixel_by_pixel_parity_verified=False,
        )

    def draw_text(self,rgba,events):
        """Copy RGB into top-down BGRA DIB, transparent GDI TextOut, return RGB."""
        if self._closed:
            raise RuntimeError("GDI DC already closed")
        if (not isinstance(rgba,np.ndarray) or rgba.dtype!=np.uint8 or
                rgba.ndim!=3 or rgba.shape[2]!=4 or
                min(rgba.shape[:2])<4 or rgba.shape[0]*rgba.shape[1]>MAX_PIXELS
                or not bool(np.all(rgba[:,:,3]==255))):
            raise ValueError("opaque bounded HxWx4 RGBA required")
        if not isinstance(events,(tuple,list)) or len(events)>2048:
            raise ValueError("bounded source TextOut events required")
        for item in events:
            if (not isinstance(item,dict) or
                    item.get("kind") not in ("x_tick","y_tick","x_name","y_name")
                    or not isinstance(item.get("text"),str)
                    or len(item["text"])>256 or "\x00" in item["text"]
                    or type(item.get("x")) is not int
                    or type(item.get("y")) is not int):
                raise ValueError("invalid source TextOut event")
        h,w=map(int,rgba.shape[:2])
        bi=_BI()
        bi.bmiHeader.biSize=ctypes.sizeof(_BIH)
        bi.bmiHeader.biWidth=w
        bi.bmiHeader.biHeight=-h
        bi.bmiHeader.biPlanes=1
        bi.bmiHeader.biBitCount=32
        bi.bmiHeader.biCompression=0
        bi.bmiHeader.biSizeImage=w*h*4
        ptr=ctypes.c_void_p()
        bmp=self._dib(self._dc,ctypes.byref(bi),0,ctypes.byref(ptr),None,0)
        if not bmp or not ptr.value:
            if bmp:
                self._delete(bmp)
            raise OSError("CreateDIBSection failed")
        old=None
        try:
            old=self._select(self._dc,bmp)
            if not old:
                raise OSError("SelectObject DIB failed")
            bgra=np.ascontiguousarray(rgba[:,:,[2,1,0,3]])
            ctypes.memmove(ptr.value,bgra.ctypes.data,w*h*4)
            for item in events:
                txt=item["text"]
                if txt and not self._text(
                        self._dc,item["x"],item["y"],txt,len(txt)):
                    raise OSError("Win32 TextOutW failed")
            raw=np.frombuffer(ctypes.string_at(ptr.value,w*h*4),dtype=np.uint8)
            raw=raw.reshape((h,w,4))
            result=np.ascontiguousarray(raw[:,:,[2,1,0,3]])
            result[:,:,3]=255 # GDI may clear DIB alpha on ink pixels
            return result
        finally:
            if old:
                self._select(self._dc,old)
            self._delete(bmp)
