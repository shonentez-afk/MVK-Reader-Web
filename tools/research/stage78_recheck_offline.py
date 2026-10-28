#!/usr/bin/env python3
"""Offline Stage 78 independent structural recheck. No network/device access.

Usage:
 python tools/research/stage78_recheck_offline.py --tables PATH [--idr _Unit128.pas]
 PATH can be a directory of TABLE-*.csv or MVKVIEW_STAGE78_TABLE_CSV_20261028.zip.
 A PASS here confirms structural invariants, NOT numeric equivalence to MVKView.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

ANCHORS = (
    "procedure Tmvkform.bWriteTableClick",
    "0084E0FE    call        @RewritText",
    "0084E209    call        TCheckListBox.GetChecked",
    "0084E2C1    call        TMvkCellList.GetTitle",
    "0084E319    call        TMvkCellList.GetValueText",
    "0084E3AE    call        TMvkCellList.GetTitle",
    "0084E409    call        TMvkCellList.GetValueText",
    "0084E5FB    call        TMvkCellList.GetValueText",
    "0084E6CD    call        @Close",
)
def iter_csv(root):
    if root.is_dir():
        for p in sorted(root.rglob("TABLE-*.csv")):
            yield str(p), p.read_bytes()
    elif root.suffix.lower() == ".zip":
        with ZipFile(root) as archive:
            for item in sorted(archive.namelist()):
                if Path(item).name.startswith("TABLE-") and item.lower().endswith(".csv"):
                    yield item, archive.read(item)
    else:
        raise ValueError("Expected directory or ZIP archive")
def run(root, idr):
    records = []
    for name, data in iter_csv(root):
        text = data.decode("cp1251", errors="strict").lstrip("\ufeff")
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter="|"))
        heads = rows[1] if len(rows) > 1 else []
        n_adc = sum(cell.strip().startswith("АЦП ") for cell in heads)
        records.append(dict(file=name, sha256=hashlib.sha256(data).hexdigest(),
                            physical_rows=len(rows), n_adc=n_adc,
                            separator_ok=bool(rows and rows[0] == ["sep=", ""]),
                            nonempty=bool(data)))
    counts = {str(n): sum(r["n_adc"] == n for r in records) for n in (1, 3)}
    structural = bool(records) and all(r["separator_ok"] and r["physical_rows"] == 40 for r in records)
    original_sample_match = len(records) == 32 and counts == {"1": 19, "3": 13}
    idr_result = "not_supplied"
    if idr:
        code = idr.read_text(errors="replace")
        missing = [anchor for anchor in ANCHORS if anchor not in code]
        idr_result = {"passed": not missing, "checked": len(ANCHORS), "missing": missing}
    report = dict(stage=78, mode="offline", files=len(records),
                  structural_pass=structural, matches_reported_32_file_set=original_sample_match,
                  idr=idr_result, channel_counts=counts, records=records,
                  caveat="Not an end-to-end numeric validation; checksum records file identity only.")
    return report
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", type=Path, required=True)
    ap.add_argument("--idr", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    output = run(args.tables, args.idr)
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    raise SystemExit(0 if output["structural_pass"] and output["idr"] != {"passed": False} else 1)
