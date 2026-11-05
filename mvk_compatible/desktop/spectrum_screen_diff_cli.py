"""Stage111Z31M local PNG spectrum comparison; prints only aggregate metrics.

Both screenshots must be cropped to the SAME physical pixel dimensions.
No network calls, no uploads, no screenshot data or filenames in output.
The original screenshot's provenance must be checked by the operator.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage
from ..core.spectrum_bitmap_diff import compare_spectrum_bitmap_crops


def _rect(s):
    try:
        parts=[int(x.strip()) for x in s.split(",")]
    except (TypeError,ValueError) as e:
        raise argparse.ArgumentTypeError("Need x,y,width,height") from e
    if len(parts)!=4 or parts[0]<0 or parts[1]<0 or parts[2]<64 or parts[3]<64:
        raise argparse.ArgumentTypeError("Crop must be x>=0,y>=0,w>=64,h>=64")
    return tuple(parts)


def _read(path,rect):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>32_000_000:
        raise ValueError("local PNG unavailable or outside size limits")
    im=QImage(str(p))
    if im.isNull() or im.width()*im.height()>12_000_000:
        raise ValueError("unreadable or oversized local image")
    im=im.convertToFormat(QImage.Format_RGBA8888)
    w,h=im.width(),im.height()
    if rect is None:
        x,y,cw,ch=0,0,w,h
    else:
        x,y,cw,ch=rect
    if x+cw>w or y+ch>h or cw*ch>6_000_000:
        raise ValueError("plot crop exceeds image bounds")
    raw=np.frombuffer(im.bits(),dtype=np.uint8).reshape(h,im.bytesPerLine())
    rgba=raw[:, :w*4].reshape(h,w,4)[y:y+ch,x:x+cw,:].copy()
    rgba[:,:,3]=255
    return rgba


def main(argv=None):
    p=argparse.ArgumentParser(
        description="Local original vs candidate spectrum bitmap diff, no screenshots uploaded.")
    p.add_argument("--original",required=True)
    p.add_argument("--candidate",required=True)
    p.add_argument("--original-crop",type=_rect)
    p.add_argument("--candidate-crop",type=_rect)
    p.add_argument("--shift-radius",type=int,default=3)
    args=p.parse_args(argv)
    try:
        report=compare_spectrum_bitmap_crops(
            _read(args.original,args.original_crop),
            _read(args.candidate,args.candidate_crop),
            shift_radius=args.shift_radius)
    except (ValueError,OSError) as err:
        p.exit(2,"Image comparison unavailable: "+str(err)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
