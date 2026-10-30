"""Stage111X: private offline *bitwise* Delphi/x87 observation comparator.

Input is a local-only operator-supplied reference, not authenticated by this
program. Raw FRange, GraphDefaultVScale, runtime CW, paths, and samples are
NEVER printed. No instrument connection, no network, no real golden fixture
committed to GitHub. The Python diagnostic is not a native Delphi emulator.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re
import struct
from .core.spectrum_graph_default_vscale_idr_candidate import spectrum_graph_default_vscale

SOURCE = 'PRIVATE_MVKVIEW_RUNTIME_X87_BITWISE_REFERENCE_COMPARISON'
SCHEMA = 'MVKVIEW_RUNTIME_X87_GOLDEN_V1'
_HEX32 = re.compile(r'0x[0-9A-Fa-f]{8}\Z')
_HEX16 = re.compile(r'0x[0-9A-Fa-f]{4}\Z')
_FIELDS = frozenset(('mode','f_range_bits','graph_default_vscale_bits','runtime_cw'))


def _decode_single_bits(value: str, label: str) -> tuple[float,int]:
    if not isinstance(value,str) or _HEX32.fullmatch(value) is None:
        raise ValueError('Invalid private '+label+' float32 bits')
    bits=int(value,16)
    v=struct.unpack('<f', struct.pack('<I',bits))[0]
    if not math.isfinite(v) or v <= 0:
        raise ValueError('Private '+label+' must be finite positive Single')
    return v,bits


def compare_private_x87_runtime_snapshot(payload:dict)->dict:
    """Only aggregate error/PC/RC counts; no individual original values."""
    if (not isinstance(payload,dict) or set(payload)!= {'schema','records'} or
            payload.get('schema')!=SCHEMA or not isinstance(payload.get('records'),list) or
            not 1<=len(payload['records'])<=256):
        raise ValueError('Invalid private x87 golden comparison schema')
    stats={'24_bit':0,'53_bit':0,'64_bit':0}
    rc_stats={'nearest':0,'down':0,'up':0,'zero':0}
    count=0;matched=0;ulps=[];risky=0;risky_mismatch=0
    static_initial_compatible=0
    for row in payload['records']:
        if not isinstance(row,dict) or set(row)!=_FIELDS:
            raise ValueError('Private reference row schema does not match')
        mode=row['mode']
        if isinstance(mode,bool) or not isinstance(mode,int) or not 0<=mode<=3:
            raise ValueError('Invalid private source mode')
        f_range,_=_decode_single_bits(row['f_range_bits'],'FRange')
        _,expected_bits=_decode_single_bits(row['graph_default_vscale_bits'], 'GraphDefaultVScale')
        cw_raw=row['runtime_cw']
        if not isinstance(cw_raw,str) or _HEX16.fullmatch(cw_raw) is None:
            raise ValueError('Invalid private runtime FPU control word')
        cw=int(cw_raw,16)
        pc=(cw>>8)&3
        if pc==1:raise ValueError('Reserved x87 precision mode')
        pc_label={0:'24_bit',2:'53_bit',3:'64_bit'}[pc]
        rc_label=('nearest','down','up','zero')[(cw>>10)&3]
        stats[pc_label]+=1
        rc_stats[rc_label]+=1
        if (cw & ~0x0040)==0x1332:static_initial_compatible+=1
        pred=spectrum_graph_default_vscale(f_range,mode)
        predicted_bits=struct.unpack('<I',struct.pack('<f',pred['candidate_graph_default_vscale_single']))[0]
        error_ulps=abs(predicted_bits-expected_bits)  # both values strictly positive
        ulps.append(error_ulps)
        matched+=int(error_ulps==0)
        count+=1
        if pred['original_x87_boundary_requires_runtime_reference']:
            risky+=1
            risky_mismatch+=int(error_ulps!=0)
    return {
        'source':SOURCE,'schema':SCHEMA,'records_count':count,
        'python_candidate_bitwise_matching_count':matched,
        'python_candidate_bitwise_nonmatching_count':count-matched,
        'python_candidate_max_positive_float32_ulp_distance':max(ulps),
        'python_candidate_mean_positive_float32_ulp_distance':sum(ulps)/count,
        'extended_log10_boundary_flagged_count':risky,
        'extended_log10_boundary_nonmatching_count':risky_mismatch,
        'runtime_cw_pc_group_counts':stats,
        'runtime_cw_rc_group_counts':rc_stats,
        'runtime_cw_matches_static_1332_ignoring_reserved_bit6_count':static_initial_compatible,
        'operator_provided_runtime_values_independently_authenticated':False,
        'original_selected_channel_frange_source_authenticated':False,
        'original_delphi_bitwise_parity_accepted':False,
        'original_private_values_cw_or_paths_in_report':False,
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description='Private offline MVKView x87 bitwise comparison')
    parser.add_argument('private_json',help='PRIVATE operator-supplied runtime snapshot JSON')
    args=parser.parse_args(argv)
    try:
        path=Path(args.private_json)
        if (path.is_symlink() or not path.is_file() or
                path.suffix.lower()!='.json' or path.stat().st_size>131072):
            raise ValueError('Invalid private reference file')
        payload=json.loads(path.read_text(encoding='utf-8'))
        result=compare_private_x87_runtime_snapshot(payload)
    except (OSError,ValueError,TypeError,OverflowError,struct.error):
        parser.exit(2,'Private reference schema or data invalid; private details withheld\n')
    print(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
