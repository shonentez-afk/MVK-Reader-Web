"""Stage111K private/offline source geometry comparator for an original screenshot.

Operator measures original Delphi TCanvas and/or records original offsets.
Neither photographs nor original Delphi content are uploaded or transmitted.
The comparison is DIAGNOSTIC; numbers alone never certify Delphi parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from .core.tqgrapher_canvas_idr_candidate import source_canvas_geometry

PIXEL_FIELDS=('pixel_left','pixel_right','pixel_top','pixel_bottom')
COEFFICIENT_FIELDS=('itos_m','itos_c','stoi_m','stoi_c','ytos_m','ytos_c')
INPUT_FIELDS=('pixel_width','pixel_height','margin','zero_text_width',
              'six_decimals_text_width','zero_text_height','x_name_present',
              'y_name_present','scr_left','scr_width','scr_bottom','scr_height',
              'series_x_start','series_x_scale')


def _private_json(path:str|Path)->dict:
    p=Path(path)
    if p.suffix.lower()!='.json' or p.is_symlink() or not p.is_file():
        raise ValueError('A regular, private, local .json file is required')
    data=p.read_bytes()
    if len(data)>16384 or not data:raise ValueError('Private geometry file too large or empty')
    obj=json.loads(data.decode('utf-8-sig'))
    if not isinstance(obj,dict):raise ValueError('Geometry input must be an object')
    return obj


def reference_geometry_comparison(model:dict, original:dict, *,
                                   pixel_tolerance:float=0.,
                                   coefficient_tolerance:float=1e-5,
                                   operator_confirmed_same_canvas:bool=False)->dict:
    """Compare only original-supplied numeric fields, without exposing them."""
    if not isinstance(original,dict) or not original:
        raise ValueError('At least one original Canvas reference field is required')
    if not isinstance(operator_confirmed_same_canvas,bool):
        raise ValueError('Operator confirmation must be boolean')
    if (not math.isfinite(pixel_tolerance) or pixel_tolerance<0
        or not math.isfinite(coefficient_tolerance) or coefficient_tolerance<0):
        raise ValueError('Invalid geometry tolerances')
    unknown=set(original)-set(PIXEL_FIELDS+COEFFICIENT_FIELDS)
    if unknown:raise ValueError('Unexpected original reference field names')
    diffs={}
    passed={}
    for key,raw in original.items():
        if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw):
            raise ValueError('Original Canvas reference values must be finite numbers')
        difference=abs(float(model[key])-float(raw))
        diffs[key]=difference
        passed[key]=difference <= (pixel_tolerance if key in PIXEL_FIELDS
                                    else coefficient_tolerance)
    return {
        'source':'LOCAL_TQGRAPHER_GEOMETRY_REFERENCE_DIAGNOSTIC',
        'compared_fields':list(diffs),
        'absolute_errors':diffs,
        'within_tolerance_per_field':passed,
        'within_supplied_tolerances':all(passed.values()),
        'operator_confirmed_same_canvas_and_font':operator_confirmed_same_canvas,
        'original_delphi_pixel_parity_verified':False,
        'original_font_metrics_parity_verified':False,
        'original_x87_numeric_parity_verified':False,
        'warning':'Pixel geometry numerically compared; original provenance/font/Delphi RTL is not certified',
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(
        description='OFFLINE source TQGrapher geometry vs operator-measured original PixelRect')
    parser.add_argument('--metrics',required=True,
                        help='Private local JSON of TCanvas widths and axis parameters')
    parser.add_argument('--reference',required=True,
                        help='Private original measured geometry JSON, minimum one field')
    parser.add_argument('--pixel-tol',type=float,default=0.)
    parser.add_argument('--coefficient-tol',type=float,default=1e-5)
    parser.add_argument('--confirm-same-canvas',action='store_true')
    parser.add_argument('--report-json',help='Optional local summary only; never original measurements')
    a=parser.parse_args(argv)
    try:
        metrics=_private_json(a.metrics)
        if set(metrics)!=set(INPUT_FIELDS):
            raise ValueError('Explicit 14 original Canvas metric fields required; no defaults')
        original=_private_json(a.reference)
        model=source_canvas_geometry(**metrics)
        report=reference_geometry_comparison(model,original,
                pixel_tolerance=a.pixel_tol,
                coefficient_tolerance=a.coefficient_tol,
                operator_confirmed_same_canvas=a.confirm_same_canvas)
        report['metrics_sha256']=hashlib.sha256(Path(a.metrics).read_bytes()).hexdigest()
        report['reference_sha256']=hashlib.sha256(Path(a.reference).read_bytes()).hexdigest()
        if a.report_json:
            path=Path(a.report_json)
            if path.suffix.lower()!='.json' or path.is_symlink() or not path.parent.is_dir():
                raise ValueError('Report must be an explicitly selected local JSON')
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report['within_supplied_tolerances'] else 1
    except (OSError,TypeError,UnicodeError,ValueError,OverflowError,KeyError) as exc:
        parser.exit(2,'Исходная геометрия MVKView не принята: '+str(exc)+'\n')


if __name__=='__main__':
    sys.exit(main())
