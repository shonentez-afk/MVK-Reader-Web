"""Stage111U: PRIVATE offline original GraphDefaultVScale reference comparison.

Operator-provided original values stay in a local JSON file. Output contains
ONLY aggregate errors and provenance flags; not raw FRange/original Y values,
paths, channel names, screenshots, or proprietary source. No network.
Matching one private fixture does NOT certify Delphi x87 or general parity.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

from .core.spectrum_graph_default_vscale_idr_candidate import spectrum_graph_default_vscale

SOURCE='PRIVATE_ORIGINAL_GRAPHDEFAULTVSCALE_REFERENCE_DIAGNOSTIC'


def compare_private_reference(records:list[dict], *, tolerance_relative:float=1e-5)->dict:
    if (not isinstance(records,list) or not 1<=len(records)<=256 or
            isinstance(tolerance_relative,bool) or not isinstance(tolerance_relative,(float,int)) or
            not math.isfinite(float(tolerance_relative)) or
            not 0<=tolerance_relative<=.1):
        raise ValueError('Expected 1..256 original reference records and bounded tolerance')
    errors=[]
    threshold_count=0
    for row in records:
        if not isinstance(row,dict) or set(row)!= {'mode','f_range','original_graph_default_vscale'}:
            raise ValueError('Each private record needs only mode, f_range, original_graph_default_vscale')
        reference=row['original_graph_default_vscale']
        if (isinstance(reference,bool) or not isinstance(reference,(float,int)) or
                not math.isfinite(reference) or reference<=0):
            raise ValueError('Invalid original reference scale')
        prediction=spectrum_graph_default_vscale(row['f_range'],row['mode'])
        predicted=prediction['candidate_graph_default_vscale_single']
        relative=abs(predicted-reference)/max(abs(reference),1e-45)
        if not math.isfinite(relative):
            raise ValueError('Unrepresentable reference comparison error')
        errors.append(relative)
        if not prediction['ideal_matches_reconstructed_single']:
            threshold_count+=1
    return {
        'source':SOURCE,
        'compared_count':len(errors),
        'matched_count':sum(e<=tolerance_relative for e in errors),
        'nonmatching_count':sum(e>tolerance_relative for e in errors),
        'max_relative_error':max(errors),
        'mean_relative_error':sum(errors)/len(errors),
        'modeled_threshold_ambiguity_count':threshold_count,
        'tolerance_relative':float(tolerance_relative),
        'no_raw_original_values_in_report':True,
        'original_runtime_reference_authenticated':False,
        'original_delphi_x87_parity_verified':False,
        'original_sensor_f_range_calibration_verified':False,
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description='Private offline comparison, prints aggregate metrics only')
    p.add_argument('private_json',help='Private local JSON containing reference records')
    p.add_argument('--tolerance-relative',type=float,default=1e-5)
    args=p.parse_args(argv)
    try:
        path=Path(args.private_json)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>200000:
            raise ValueError('Missing, linked or oversized private reference file')
        payload=json.loads(path.read_text(encoding='utf-8'))
        report=compare_private_reference(payload,tolerance_relative=args.tolerance_relative)
    except (ValueError,TypeError,KeyError,OSError,json.JSONDecodeError) as ex:
        p.error('Invalid private reference or model input; details retained locally')
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
