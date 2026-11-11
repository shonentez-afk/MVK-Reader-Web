#!/usr/bin/env python3
"""Offline original-versus-candidate graph PNG QA; no original process/MCP.

Example (run from repository root, with desktop requirements installed):
 python tools/research/compare_stage111z31az_spectrum_pixel_audit.py \
   --original "C:/mvk_log/original_spectrum_crop.png" \
   --candidate "C:/mvk_log/MVK_SPECTRUM_PIXEL_QA_.../candidate_source_bitmap.png" \
   --manifest "C:/mvk_log/MVK_SPECTRUM_PIXEL_QA_.../candidate_manifest.json" \
   --report "C:/mvk_log/my_comparison_report.json" \
   --operator-same-window --shift-radius 2

Screenshots are PRIVATE and stay on the operator PC. The report contains
only numerical aggregate comparisons, never paths or source pixel buffers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# When invoked directly from tools/research, import the checkout's own
# deterministic offline core/Qt adapter without package installation.
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from mvk_compatible.core.spectrum_graph_pixel_audit import (
    compare_local_graph_pixel_audit,
)
from mvk_compatible.desktop.source_pixel_audit_io import read_png_rgba


def run(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="PRIVATE local source-TQGrapher PNG pixel audit (not proof of original provenance)")
    parser.add_argument("--original",required=True,help="original MVKView PaintBox crop PNG, cursor OFF")
    parser.add_argument("--candidate",required=True,help="exported candidate_source_bitmap.png")
    parser.add_argument("--manifest",required=True,help="exported candidate_manifest.json")
    parser.add_argument("--report",required=True,help="new local JSON report output (not inside Git repo)")
    parser.add_argument("--operator-same-window",action="store_true",
                        help="operator manually declares identical original measurement/window/settings")
    parser.add_argument("--shift-radius",type=int,default=0,choices=range(6),
                        metavar="0..5",help="diagnostic alignment only; never exact acceptance")
    args=parser.parse_args(argv)
    original=Path(args.original).resolve()
    candidate=Path(args.candidate).resolve()
    manifest_path=Path(args.manifest).resolve()
    report_path=Path(args.report).resolve()

    if original == candidate:
        parser.error("Original screenshot MUST be separate from candidate PNG")
    if ROOT in report_path.parents or report_path == ROOT:
        parser.error("Do not store private audit reports inside GitHub checkout")
    if report_path.exists():
        parser.error("Report target exists; refusing to overwrite existing private data")
    if not report_path.parent.is_dir():
        parser.error("Report output directory must already exist")

    try:
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("candidate_png_filename") != candidate.name:
            raise ValueError("Candidate PNG filename disagrees with export manifest")
        orig=read_png_rgba(original)
        cand=read_png_rgba(candidate)
        result=compare_local_graph_pixel_audit(
            orig,cand,manifest,shift_radius=args.shift_radius,
            operator_declared_same_measurement_and_window=args.operator_same_window)
        result["local_report_format"]="stage111z31az_original_candidate_graph_pixel_diff"
        result["operator_supplied_original_crop"]=True
        result["reports_exclude_private_filenames"]=True
        with report_path.open("x",encoding="utf-8") as out:
            json.dump(result,out,ensure_ascii=False,sort_keys=True,indent=2)
            out.write("\n")
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
        parser.exit(2,"Local pixel audit rejected: "+str(e)+"\n")

    whole=result["full_canvas"]
    print("Stage111Z31AZ local audit complete.")
    print("Exact RGB pixels:",whole["exact_rgb_pixels"],"of",whole["pixels_compared"])
    print("Original measurement authenticated independently: NO")
    print("Original MVKView 1:1 declared: NO")
    print("Private report saved to the operator-selected location.")
    return 0 if result["exact_rgb_equal_without_alignment"] else 1


if __name__ == "__main__":
    sys.exit(run())
