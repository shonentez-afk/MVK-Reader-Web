"""Stage111P local/private original TQGrapher XOR bitmap comparison.

Accepts only bounded local uint8 RGB .npy snapshots (before/after one
original UpdateCursor) and separate source-derived Canvas/crosshair JSON.
Never prints pixels or private reference coordinates. This checks the
GDI XOR model, NOT authenticated original Delphi font/DPI/pixel parity.
No instrument, network, original images or closed source in this project.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from .core.tqgrapher_gdi_xor_idr_candidate import (
    OriginalGdiXorCursorModel, _validated_bitmap)

MAX_PRIVATE_BYTES = 16*1024*1024


def _local_file(path: str | Path, suffix: str) -> Path:
    p=Path(path)
    if (p.suffix.lower()!=suffix or p.is_symlink() or not p.is_file()
        or not 0<p.stat().st_size<=MAX_PRIVATE_BYTES):
        raise ValueError('Expected small regular local '+suffix+' file, not a symlink')
    return p


def _safe_json(path: str | Path) -> dict:
    obj=json.loads(_local_file(path,'.json').read_text(encoding='utf-8-sig'))
    if not isinstance(obj,dict):
        raise ValueError('Expected a JSON object')
    return obj


def _safe_rgb(path: str | Path) -> np.ndarray:
    value=np.load(_local_file(path,'.npy'),allow_pickle=False)
    return _validated_bitmap(value)


def compare_private_xor_frames(before:np.ndarray,after:np.ndarray,*,
                               canvas:dict,crosshair:dict,mouse_x:int,
                               operator_confirms_identical_canvas:bool=False)->dict:
    if not isinstance(operator_confirms_identical_canvas,bool):
        raise ValueError('Operator confirmation must be boolean')
    original=_validated_bitmap(before)
    actual=_validated_bitmap(after)
    if original.shape!=actual.shape:
        raise ValueError('Original before/after dimensions differ')
    model=OriginalGdiXorCursorModel(canvas)
    predicted,operation=model.update(mouse_x,original,crosshair)
    mismatched=np.any(actual!=predicted,axis=2)
    channel_counts={c:int(np.count_nonzero(actual[:,:,i]!=predicted[:,:,i]))
                    for i,c in enumerate('RGB')}
    count=int(np.count_nonzero(mismatched))
    return {
        'source':'LOCAL_PRIVATE_TQGRAPHER_GDI_XOR_BITMAP_COMPARATOR',
        'compared_pixel_count':int(original.shape[0]*original.shape[1]),
        'pixel_mismatch_count':count,
        'pixel_mismatch_fraction':float(count/original.shape[0]/original.shape[1]),
        'per_channel_mismatches':channel_counts,
        'match_source_raster_model':count==0,
        'operator_confirms_identical_canvas':operator_confirms_identical_canvas,
        'original_delphi_pixel_parity_verified':False,
        'delphi_font_dpi_alignment_verified':False,
        'original_x87_parity_verified':False,
        'warning':'Model-only pixel comparison; original GDI Canvas/DPI and screenshot provenance not certified',
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description='PRIVATE original before/after TQGrapher XOR comparator')
    p.add_argument('--before',required=True,help='Local private original RGB .npy before cursor')
    p.add_argument('--after',required=True,help='Local private original RGB .npy after cursor')
    p.add_argument('--canvas',required=True,help='Local source Canvas JSON')
    p.add_argument('--crosshair',required=True,help='Local source cursor crosshair JSON')
    p.add_argument('--mouse-x',required=True,type=int)
    p.add_argument('--confirm-identical-canvas',action='store_true')
    p.add_argument('--report-json',help='Optional local report path containing only error counts')
    a=p.parse_args(argv)
    try:
        before=_safe_rgb(a.before);after=_safe_rgb(a.after)
        canvas=_safe_json(a.canvas);crosshair=_safe_json(a.crosshair)
        result=compare_private_xor_frames(before,after,canvas=canvas,crosshair=crosshair,
            mouse_x=a.mouse_x,operator_confirms_identical_canvas=a.confirm_identical_canvas)
        result['local_before_sha256']=hashlib.sha256(_local_file(a.before,'.npy').read_bytes()).hexdigest()
        result['local_after_sha256']=hashlib.sha256(_local_file(a.after,'.npy').read_bytes()).hexdigest()
        encoded=json.dumps(result,indent=2,ensure_ascii=False)
        if a.report_json:
            target=Path(a.report_json)
            if (target.suffix.lower()!='.json' or target.is_symlink()
                or not target.parent.is_dir()):
                raise ValueError('Report path must be explicit local .json')
            target.write_text(encoded,encoding='utf-8')
        print(encoded)
        return 0 if result['match_source_raster_model'] else 1
    except (OSError,ValueError,TypeError,KeyError,UnicodeError) as e:
        p.exit(2,'Private GDI XOR comparison rejected: '+str(e)+'\n')


if __name__=='__main__':
    sys.exit(main())
