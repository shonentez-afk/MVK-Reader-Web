"""Stage111N — private batch original TQGrapher Canvas/Font/DPI comparator.

Every case must explicitly supply the original TextWidth/TextHeight at the
actual Canvas/font/DPI and an independent original PixelRect/affine reference.
We do NOT infer font metrics by scaling Qt values; the case's optional DPI
is recorded only as operator metadata. Nothing is uploaded to any server.
Reports contain only differences and SHA-256, never original measurements.
Synthetic zero-difference fixtures cannot prove original Delphi x87 parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from .canvas_reference_compare import (
    INPUT_FIELDS, PIXEL_FIELDS, COEFFICIENT_FIELDS,
    reference_geometry_comparison,
)
from .core.tqgrapher_canvas_idr_candidate import source_canvas_geometry

MAX_BYTES=131072
MAX_CASES=128


def compare_canvas_sweep(document:dict, *, pixel_tolerance:float=0.,
                         coefficient_tolerance:float=1e-5,
                         operator_confirmed_same_canvas:bool=False)->dict:
    """Fail on any case/field mismatch; never echo original values/metrics."""
    if not isinstance(document,dict) or set(document)!={'cases'}:
        raise ValueError('Expected an object with exactly one cases array')
    cases=document['cases']
    if not isinstance(cases,list) or not 1<=len(cases)<=MAX_CASES:
        raise ValueError('Canvas batch must contain 1..128 explicit cases')
    if not isinstance(operator_confirmed_same_canvas,bool):
        raise ValueError('Canvas confirmation must be an explicit boolean')
    rows=[]
    max_diff={}
    passed=0
    for index,case in enumerate(cases):
        if not isinstance(case,dict) or not {'metrics','original'}<=set(case) or (
            set(case)-{'metrics','original','dpi'}):
            raise ValueError('Each case needs metrics/original and optional dpi')
        metrics=case['metrics']
        if not isinstance(metrics,dict) or set(metrics)!=set(INPUT_FIELDS):
            raise ValueError('Each original Canvas metrics block needs 14 fields')
        if 'dpi' in case:
            dpi=case['dpi']
            if (isinstance(dpi,bool) or not isinstance(dpi,(float,int))
                or not math.isfinite(dpi) or dpi<=0 or dpi>960):
                raise ValueError('Optional operator DPI must be a finite positive number')
        model=source_canvas_geometry(**metrics)
        result=reference_geometry_comparison(
            model,case['original'],pixel_tolerance=pixel_tolerance,
            coefficient_tolerance=coefficient_tolerance,
            operator_confirmed_same_canvas=operator_confirmed_same_canvas)
        for k,diff in result['absolute_errors'].items():
            max_diff[k]=max(max_diff.get(k,0.),diff)
        valid=result['within_supplied_tolerances']
        passed+=int(valid)
        rows.append({
            'case_number':index+1,
            'operator_dpi_declared':'dpi' in case,
            'x_reversed':model['screen_x_reversed'],
            'source_scr_width_clamped':model['scr_width_source_clamped'],
            'source_scr_height_clamped':model['scr_height_source_clamped'],
            'source_series_scale_clamped':model['series_x_scale_source_clamped'],
            'compared_fields':result['compared_fields'],
            'absolute_errors':result['absolute_errors'],
            'within_supplied_tolerances':valid,
        })
    return {
        'source':'LOCAL_TQGRAPHER_CANVAS_SWEEP_REFERENCE_DIAGNOSTIC',
        'case_count':len(cases),
        'passing_case_count':passed,
        'all_cases_within_supplied_tolerances':passed==len(cases),
        'max_absolute_errors_by_field':max_diff,
        'case_results':rows,
        'operator_confirmed_same_canvas_and_font':
            operator_confirmed_same_canvas,
        'delphi_pixel_font_dpi_parity_verified':False,
        'delphi_x87_numerical_parity_verified':False,
        'warning':('Measured original Canvas/TextWidth/TextHeight/DPI must be '
                   'collected independently; synthetic comparisons are not acceptance'),
    }


def _private_json(path:str|Path)->tuple[dict,str]:
    p=Path(path)
    if (p.suffix.lower()!='.json' or p.is_symlink() or not p.is_file()
        or not 0<p.stat().st_size<=MAX_BYTES):
        raise ValueError('Expected a bounded regular private .json file')
    raw=p.read_bytes()
    return json.loads(raw.decode('utf-8-sig')),hashlib.sha256(raw).hexdigest()


def main(argv=None)->int:
    parser=argparse.ArgumentParser(
        description='PRIVATE offline Canvas/Font/DPI measured sweep vs MVKView')
    parser.add_argument('--cases',required=True,help='Local private cases JSON')
    parser.add_argument('--pixel-tol',type=float,default=0.)
    parser.add_argument('--coefficient-tol',type=float,default=1e-5)
    parser.add_argument('--confirm-same-canvas',action='store_true')
    parser.add_argument('--report-json',help='Private error-only output path')
    args=parser.parse_args(argv)
    try:
        data,digest=_private_json(args.cases)
        result=compare_canvas_sweep(data,
            pixel_tolerance=args.pixel_tol,
            coefficient_tolerance=args.coefficient_tol,
            operator_confirmed_same_canvas=args.confirm_same_canvas)
        result['cases_file_sha256']=digest
        report=json.dumps(result,ensure_ascii=False,indent=2)
        if args.report_json:
            p=Path(args.report_json)
            if p.suffix.lower()!='.json' or p.is_symlink() or not p.parent.is_dir():
                raise ValueError('Report must be an explicitly selected local JSON')
            p.write_text(report,encoding='utf-8')
        print(report)
        return 0 if result['all_cases_within_supplied_tolerances'] else 1
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,OverflowError) as exc:
        parser.exit(2,'Private Canvas sweep rejected: '+str(exc)+'\n')


if __name__=='__main__':
    sys.exit(main())
