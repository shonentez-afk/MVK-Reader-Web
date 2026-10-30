"""Stage111P native Windows GDI LineTo/XORPEN verification using synthetic RGB.

This deliberately uses Win32 Gdi32, NOT the vendor application or its DLLs.
The test is skipped on Linux and runs in CircleCI Windows Core; no instrument.
"""
import ctypes
import sys
import numpy as np
import pytest
from mvk_compatible.core.tqgrapher_gdi_xor_idr_candidate import (
    GdiLineTo,xor_gdi_line)


@pytest.mark.skipif(sys.platform != 'win32', reason='Native Win32 GDI only')
def test_native_windows_gdi_xorpen_line_to_matches_independent_raster_model():
    """Pixel-by-pixel compare source-derived model against actual Win32 Gdi32."""
    W,H=20,15
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_=[('biSize',ctypes.c_uint32),
                  ('biWidth',ctypes.c_int32),('biHeight',ctypes.c_int32),
                  ('biPlanes',ctypes.c_uint16),('biBitCount',ctypes.c_uint16),
                  ('biCompression',ctypes.c_uint32),('biSizeImage',ctypes.c_uint32),
                  ('biXPelsPerMeter',ctypes.c_int32),('biYPelsPerMeter',ctypes.c_int32),
                  ('biClrUsed',ctypes.c_uint32),('biClrImportant',ctypes.c_uint32)]
    class BITMAPINFO(ctypes.Structure):
        _fields_=[('bmiHeader',BITMAPINFOHEADER),('bmiColors',ctypes.c_uint32*3)]

    gdi=ctypes.WinDLL('gdi32',use_last_error=True)
    ptr=ctypes.c_void_p
    gdi.CreateCompatibleDC.argtypes=[ptr]
    gdi.CreateCompatibleDC.restype=ptr
    gdi.CreateDIBSection.argtypes=[ptr,ctypes.POINTER(BITMAPINFO),
                                  ctypes.c_uint32,ctypes.POINTER(ptr),ptr,ctypes.c_uint32]
    gdi.CreateDIBSection.restype=ptr
    gdi.SelectObject.argtypes=[ptr,ptr]
    gdi.SelectObject.restype=ptr
    gdi.CreatePen.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_uint32]
    gdi.CreatePen.restype=ptr
    gdi.SetROP2.argtypes=[ptr,ctypes.c_int]
    gdi.SetROP2.restype=ctypes.c_int
    gdi.MoveToEx.argtypes=[ptr,ctypes.c_int,ctypes.c_int,ptr]
    gdi.MoveToEx.restype=ctypes.c_int
    gdi.LineTo.argtypes=[ptr,ctypes.c_int,ctypes.c_int]
    gdi.LineTo.restype=ctypes.c_int
    gdi.DeleteObject.argtypes=[ptr]
    gdi.DeleteObject.restype=ctypes.c_int
    gdi.DeleteDC.argtypes=[ptr]
    gdi.DeleteDC.restype=ctypes.c_int

    dc=gdi.CreateCompatibleDC(None)
    assert dc,'CreateCompatibleDC failed'
    bmp=pen=oldbmp=oldpen=None
    try:
        info=BITMAPINFO()
        info.bmiHeader.biSize=ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth=W
        info.bmiHeader.biHeight=-H  # top-down Windows DIB
        info.bmiHeader.biPlanes=1
        info.bmiHeader.biBitCount=32
        info.bmiHeader.biCompression=0
        info.bmiHeader.biSizeImage=W*H*4
        bits=ptr()
        bmp=gdi.CreateDIBSection(dc,ctypes.byref(info),0,ctypes.byref(bits),None,0)
        assert bmp and bits.value,'CreateDIBSection failed'
        oldbmp=gdi.SelectObject(dc,bmp)
        assert oldbmp,'SelectObject(bitmap) failed'
        pen=gdi.CreatePen(0,1,0x00008000)  # VCL clGreen
        assert pen,'CreatePen failed'
        oldpen=gdi.SelectObject(dc,pen)
        assert oldpen,'SelectObject(pen) failed'
        previous_mode=gdi.SetROP2(dc,7)  # Win32 R2_XORPEN
        assert previous_mode!=0

        rng=np.random.default_rng(2026111)
        original=rng.integers(0,256,size=(H,W,3),dtype=np.uint8)
        native=np.ctypeslib.as_array(
            (ctypes.c_uint8*(W*H*4)).from_address(bits.value)).reshape(H,W,4)
        native[:,:,:3]=original[:,:,::-1]  # DIB B,G,R,reserved
        native[:,:,3]=0
        expected=original.copy()
        strokes=[
            GdiLineTo('vertical',None,(6,3),(6,10)),
            GdiLineTo('horizontal',0,(2,7),(12,7)),
            GdiLineTo('horizontal',1,(2,8),(12,8)),
            GdiLineTo('vertical',None,(6,3),(6,10)),
            GdiLineTo('horizontal',0,(2,7),(12,7)),
            GdiLineTo('horizontal',1,(2,8),(12,8)),
        ]
        for segment in strokes:
            x0,y0=segment.start_xy
            x1,y1=segment.stop_xy_exclusive
            assert gdi.MoveToEx(dc,x0,y0,None)!=0
            assert gdi.LineTo(dc,x1,y1)!=0
            xor_gdi_line(expected,segment)
            actual=native[:,:,:3][:,:,::-1].copy()
            np.testing.assert_array_equal(actual,expected)
        np.testing.assert_array_equal(actual,original)
        assert gdi.SetROP2(dc,previous_mode)!=0
    finally:
        if oldpen:gdi.SelectObject(dc,oldpen)
        if pen:gdi.DeleteObject(pen)
        if oldbmp:gdi.SelectObject(dc,oldbmp)
        if bmp:gdi.DeleteObject(bmp)
        gdi.DeleteDC(dc)
