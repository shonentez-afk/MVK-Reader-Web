"""Stage111Q independent OFFLINE Windows GDI font measurement candidate.

Original TQGrapher calls TextWidth('0'), TextWidth('0.000000'),
TextHeight('0') on the caller's TPaintBox.Canvas. This probe creates
an OPERATOR-SPECIFIED HFONT in a private Win32 memory DC. Its metrics
are NOT the actual font/DPI of original MVKView until independently
measured there. No vendor fonts, data or screenshots are included.
"""
from __future__ import annotations
import argparse
import ctypes
import json
import sys
from pathlib import Path

SOURCE='APP_DERIVED_NATIVE_WINDOWS_GDI_FONT_PROBE_ONLY'


def _validate(font_family:str,height_px:int,weight:int,italic:bool)->None:
    if (not isinstance(font_family,str) or not font_family
        or len(font_family)>31 or '\x00' in font_family
        or any(ord(c)<32 for c in font_family)):
        raise ValueError('Family must be a nonempty Win32 LF_FACESIZE-compatible name')
    if type(height_px) is not int or not -512<=height_px<=512 or height_px==0:
        raise ValueError('GDI font height must be a nonzero signed integer -512..512')
    if type(weight) is not int or not 1<=weight<=1000:
        raise ValueError('GDI font weight must be integer 1..1000')
    if type(italic) is not bool:
        raise ValueError('Italic must be explicit boolean')


def measure_win32_font_metrics(font_family:str,height_px:int,*,
                              weight:int=400,italic:bool=False)->dict:
    """Measure Win32 GetTextExtentPoint32W under one selected HFONT.

    Negative height_px is requested character height, positive cell height.
    Never assume this font is the one in the original MVKView TPaintBox.
    """
    _validate(font_family,height_px,weight,italic)
    if sys.platform!='win32':
        raise RuntimeError('Only available on a native Windows host')
    gdi=ctypes.WinDLL('gdi32',use_last_error=True)
    p=ctypes.c_void_p;i=ctypes.c_int;u=ctypes.c_uint32

    class SIZE(ctypes.Structure):
        _fields_=[('cx',i),('cy',i)]

    gdi.CreateCompatibleDC.argtypes=[p];gdi.CreateCompatibleDC.restype=p
    gdi.DeleteDC.argtypes=[p];gdi.DeleteDC.restype=i
    gdi.CreateFontW.argtypes=[i,i,i,i,i,u,u,u,u,u,u,u,u,ctypes.c_wchar_p]
    gdi.CreateFontW.restype=p
    gdi.SelectObject.argtypes=[p,p];gdi.SelectObject.restype=p
    gdi.DeleteObject.argtypes=[p];gdi.DeleteObject.restype=i
    gdi.GetTextExtentPoint32W.argtypes=[p,ctypes.c_wchar_p,i,ctypes.POINTER(SIZE)]
    gdi.GetTextExtentPoint32W.restype=i
    gdi.GetTextFaceW.argtypes=[p,i,ctypes.c_wchar_p];gdi.GetTextFaceW.restype=i
    gdi.GetDeviceCaps.argtypes=[p,i];gdi.GetDeviceCaps.restype=i

    dc=gdi.CreateCompatibleDC(None)
    if not dc:raise OSError('Cannot create private GDI memory DC')
    font=old=None
    try:
        font=gdi.CreateFontW(height_px,0,0,0,weight,int(italic),0,0,
                             1,0,0,0,0,font_family)
        if not font:raise OSError('CreateFontW failed')
        old=gdi.SelectObject(dc,font)
        if not old:raise OSError('SelectObject font failed')
        measurements={}
        for sample,key in [('0','zero'),('0.000000','six_decimals')]:
            size=SIZE()
            if not gdi.GetTextExtentPoint32W(dc,sample,len(sample),ctypes.byref(size)):
                raise OSError('GetTextExtentPoint32W failed')
            if size.cx<=0 or size.cy<=0:
                raise ValueError('Invalid native GDI font width or height')
            measurements[key]=(int(size.cx),int(size.cy))
        face=ctypes.create_unicode_buffer(256)
        if not gdi.GetTextFaceW(dc,256,face):raise OSError('GetTextFaceW failed')
        dpi_x=int(gdi.GetDeviceCaps(dc,88))
        dpi_y=int(gdi.GetDeviceCaps(dc,90))
        if dpi_x<=0 or dpi_y<=0:raise ValueError('Memory DC cannot measure DPI')
        return {
            'source':SOURCE,'font_requested':font_family,
            'font_actual_selected':face.value,
            'font_height_requested_px':height_px,
            'font_weight_requested':weight,'font_italic_requested':italic,
            'text_width_zero':measurements['zero'][0],
            'text_width_six_decimals':measurements['six_decimals'][0],
            'text_height_zero':measurements['zero'][1],
            'gdi_dpi_x':dpi_x,'gdi_dpi_y':dpi_y,
            'all_three_metrics_same_selected_gdi_font':True,
            'original_delphi_tcanvas_font_verified':False,
            'original_tpaintbox_dpi_verified':False,
            'qt_font_metrics_equivalent_verified':False,
            'warning':'Operator HFONT memory HDC, not actual original MVKView TPaintBox',
        }
    finally:
        if old:gdi.SelectObject(dc,old)
        if font:gdi.DeleteObject(font)
        gdi.DeleteDC(dc)


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description='Private offline Windows GDI font probe')
    parser.add_argument('--font-family',required=True)
    parser.add_argument('--font-height-px',type=int,required=True)
    parser.add_argument('--font-weight',type=int,default=400)
    parser.add_argument('--italic',action='store_true')
    parser.add_argument('--report-json',help='Explicit local output path only')
    a=parser.parse_args(argv)
    try:
        report=measure_win32_font_metrics(
            a.font_family,a.font_height_px,weight=a.font_weight,italic=a.italic)
        text=json.dumps(report,indent=2,ensure_ascii=False)
        if a.report_json:
            path=Path(a.report_json)
            if (path.suffix.lower()!='.json' or path.is_symlink()
                or not path.parent.is_dir()):
                raise ValueError('Report must be an explicit local .json destination')
            path.write_text(text,encoding='utf-8')
        print(text)
        return 0
    except (OSError,TypeError,ValueError,RuntimeError,UnicodeError) as exc:
        parser.exit(2,'Win32 GDI font probe refused: '+str(exc)+'\n')


if __name__=='__main__':
    sys.exit(main())
