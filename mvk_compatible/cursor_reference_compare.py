"""Stage111L: private LOCAL original MVKView native cursor text/pixel comparator.

No device connection, no web, no writes to original signal, no original
Delphi/IDP bundled, and no raw original cursor strings in comparison report.
Data input is an operator-selected local .npy series. np.load pickle disabled.
A numerically equal candidate is not certified Delphi RTL/pixel parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

from .core.tqgrapher_multiseries_idr_candidate import original_multiseries_cursor
from .core.tqgrapher_canvas_idr_candidate import source_canvas_geometry
from .core.tqgrapher_crosshair_idr_candidate import original_cursor_crosshair

REFERENCE_LIMIT=8192
SERIES_LIMIT=2_500_000


def _read_file(path, *, suffix, limit):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.suffix.lower()!=suffix:
        raise ValueError('Expected a regular private '+suffix+' file, not symlink')
    if not 0<p.stat().st_size<=limit:
        raise ValueError('Private input file exceeds configured bounds or is empty')
    return p.read_bytes()


def _safe_npy(path):
    raw=_read_file(path,suffix='.npy',limit=SERIES_LIMIT)
    # Use np.load with allow_pickle=False: never load arbitrary Python objects.
    import io
    a=np.load(io.BytesIO(raw),allow_pickle=False)
    if a.ndim!=1 or a.dtype.kind not in 'fiu' or len(a)>262144:
        raise ValueError('One-dimensional numeric FFT grapher series required')
    if not np.isfinite(a).all():
        raise ValueError('Nonfinite native series')
    return a.astype(np.float32),hashlib.sha256(raw).hexdigest()


def _canvas_from_metrics(raw: bytes) -> dict:
    m=json.loads(raw.decode('utf-8-sig'))
    keys=('pixel_width','pixel_height','margin','zero_text_width',
          'six_decimals_text_width','zero_text_height',
          'x_name_present','y_name_present','scr_left','scr_width',
          'scr_bottom','scr_height','series_x_start','series_x_scale')
    if not isinstance(m,dict) or set(m)!=set(keys):
        raise ValueError('Exactly 14 original Canvas metric fields are required')
    return source_canvas_geometry(**m)


def compare_cursor_candidate(candidate:dict, original_text:str, *,
                             original_line_pixel:int|None=None,
                             original_horizontal_pixels:list[int]|tuple[int,...]|None=None,
                             confirm_same_canvas:bool=False)->dict:
    """Exact string comparison without writing actual values to report."""
    if not isinstance(confirm_same_canvas,bool):raise ValueError('Invalid confirmation')
    if not isinstance(original_text,str) or not 1<=len(original_text)<=REFERENCE_LIMIT:
        raise ValueError('Original clipboard text is invalid or too long')
    if '\x00' in original_text:raise ValueError('Embedded zero character')
    actual=candidate.get('cursor_string','')
    if not isinstance(actual,str):raise ValueError('Source candidate required')
    expected=original_text  # Strict: preserve CRLF, including a terminal newline
    a=actual.split('\r\n')
    b=expected.split('\r\n')
    equal=[a[i]==b[i] for i in range(min(len(a),len(b)))]
    offset=next((i for i,(x,y) in enumerate(zip(actual,expected)) if x!=y),None)
    if offset is None and len(actual)!=len(expected):offset=min(len(actual),len(expected))
    pixel_difference=None
    if original_line_pixel is not None:
        if not isinstance(original_line_pixel,int) or isinstance(original_line_pixel,bool):
            raise ValueError('Original native cursor line pixel must be integer')
        pixel_difference=(abs(candidate.get('snapped_vertical_pixel',-999999)-original_line_pixel)
                          if candidate.get('drawn') else None)
    horizontal_errors=None
    horizontal_pixel_exact_match=None
    if original_horizontal_pixels is not None:
        if (not isinstance(original_horizontal_pixels,(list,tuple))
            or not 1<=len(original_horizontal_pixels)<=2
            or any(not isinstance(p,int) or isinstance(p,bool)
                   for p in original_horizontal_pixels)):
            raise ValueError('One/two original native horizontal pixel integers required')
        actual_y_pixels=candidate.get('horizontal_pixels')
        if (not candidate.get('drawn') or not isinstance(actual_y_pixels,list)
            or not all(isinstance(x,int) for x in actual_y_pixels)):
            raise ValueError('Crosshair horizontal source candidate missing')
        if len(actual_y_pixels)==len(original_horizontal_pixels):
            horizontal_errors=[abs(a-b) for a,b in
                               zip(actual_y_pixels,original_horizontal_pixels)]
            horizontal_pixel_exact_match=all(d==0 for d in horizontal_errors)
        else:
            horizontal_pixel_exact_match=False
    return {
        'source':'LOCAL_ORIGINAL_TQGRAPHER_CURSOR_COMPARISON_CANDIDATE',
        'candidate_drawn':bool(candidate.get('drawn')),
        'exact_cursor_string_equal':actual==expected,
        'original_text_sha256':hashlib.sha256(original_text.encode('utf-8')).hexdigest(),
        'candidate_line_count':len(a),
        'original_line_count':len(b),
        'per_line_equal':equal,
        'first_different_character_index':offset,
        'line_pixel_absolute_error':pixel_difference,
        'horizontal_pixel_absolute_errors':horizontal_errors,
        'horizontal_pixel_exact_match':horizontal_pixel_exact_match,
        'horizontal_line_count_match':(None if original_horizontal_pixels is None
            else horizontal_errors is not None),
        'operator_confirmed_same_canvas_and_archive':confirm_same_canvas,
        'original_delphi_rtl_parity_verified':False,
        'original_pixel_parity_verified':False,
        'original_source_sample_parity_verified':False,
        'warning':'Diagnostics only; original TCanvas font/layout, x87, locale and archive window require independent acceptance'
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description='Private offline original TQGrapher two-series CursorString comparison')
    parser.add_argument('--metrics',required=True,help='Private 14-field original TCanvas JSON')
    parser.add_argument('--series0',required=True,help='Private complete native float/FFT series0 .npy')
    parser.add_argument('--series1',help='Optional private second native series .npy')
    parser.add_argument('--reference',required=True,help='Private original cursor text .txt, CRLF preserved')
    parser.add_argument('--pixel',required=True,type=int,help='Native original absolute TCanvas integer CursorPos')
    parser.add_argument('--line-pixel',type=int,help='Original native CursorDrawnX integer')
    parser.add_argument('--horizontal-pixels',help='One or two operator-measured CursorDrawnY, comma-separated; no auto-detect')
    parser.add_argument('--y-scale0',type=float,default=1.,help='Original first series YScale')
    parser.add_argument('--y-scale1',type=float,default=1.,help='Original second series YScale')
    parser.add_argument('--averaging',type=int,choices=[1,3],default=1)
    parser.add_argument('--no-precise',action='store_true')
    parser.add_argument('--x-name',default='Гц')
    parser.add_argument('--y-name',default='м/с²')
    parser.add_argument('--decimal',choices=['.',','],default=',')
    parser.add_argument('--confirm-same-canvas',action='store_true')
    parser.add_argument('--report-json',help='Optional private summary JSON without sample/text values')
    args=parser.parse_args(argv)
    try:
        metrics_raw=_read_file(args.metrics,suffix='.json',limit=REFERENCE_LIMIT)
        canvas=_canvas_from_metrics(metrics_raw)
        series0,hash0=_safe_npy(args.series0)
        series1,hash1=_safe_npy(args.series1) if args.series1 else (None,None)
        reference_raw=_read_file(args.reference,suffix='.txt',limit=REFERENCE_LIMIT)
        # bytes.decode preserves original CRLF, unlike newline translation.
        text=reference_raw.decode('utf-8-sig')
        candidate=original_multiseries_cursor(
            series0,pixel=args.pixel,canvas=canvas,averaging=args.averaging,
            precise=not args.no_precise,series1=series1,
            x_name=args.x_name,y_name=args.y_name,
            decimal_separator=args.decimal)
        original_horizontal=None
        if args.horizontal_pixels is not None:
            tokens=args.horizontal_pixels.split(',')
            if (not 1<=len(tokens)<=2 or
                any(not tok or len(tok)>10 or not tok.lstrip('-').isdigit()
                    for tok in tokens)):
                raise ValueError('Use --horizontal-pixels N or N,M with native integer pixels')
            original_horizontal=[int(tok) for tok in tokens]
            crosshair=original_cursor_crosshair(
                candidate,canvas,y_scale0=args.y_scale0,y_scale1=args.y_scale1)
            candidate['horizontal_pixels']=crosshair.get('horizontal_pixels',[])
        result=compare_cursor_candidate(candidate,text,
            original_line_pixel=args.line_pixel,
            original_horizontal_pixels=original_horizontal,
            confirm_same_canvas=args.confirm_same_canvas)
        result['metrics_sha256']=hashlib.sha256(metrics_raw).hexdigest()
        result['series0_sha256']=hash0
        result['series1_sha256']=hash1
        result['original_reference_file_sha256']=hashlib.sha256(reference_raw).hexdigest()
        result['original_source_geometry_verified']=False
        if args.report_json:
            path=Path(args.report_json)
            if path.suffix.lower()!='.json' or path.is_symlink() or not path.parent.is_dir():
                raise ValueError('Report must be an explicitly selected local JSON')
            path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return (0 if (result['exact_cursor_string_equal'] and
                      (result['line_pixel_absolute_error'] in (None,0)) and
                      (result['horizontal_pixel_exact_match'] in (None,True))) else 1)
    except (ValueError,TypeError,KeyError,UnicodeError,OSError,OverflowError) as exc:
        parser.exit(2,'Локальная сверка оригинального курсора отклонена: '+str(exc)+'\n')

if __name__=='__main__':
    sys.exit(main())
