"""Privacy-safe original MVKView VALUES/TABLE pairing and format evidence.

Source CSVs are operator-owned; never commit them. No network or device IO.
Original VALUES has 43 SPEC + 6 RESULT + 24 BAND = 73 cells per ADC,
two header lines and time ticks. TABLE is a 30-row ADC snapshot plus
6 TACH rows. Files from different runs are NOT paired by filename alone.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
import struct

from .original_get_value_text_30 import get_value_text_30

SOURCE = "MVK_ORIGINAL_VALUES_TABLE_SOURCE_PAIR_QA_V1"
ADC_CELLS = 73
SPEC_CELLS = 43
RESULT_CELLS = 6
BAND_CELLS = 24
MAX_BYTES = 32_000_000
MAX_ROWS = 150_000
TIME_RE = re.compile(r"\d\d:\d\d:\d\d\.\d{3}\Z")
NUMBER_RE = re.compile(r"-?\d+(?:,\d+)?\Z")
FILE_DATE_RE = re.compile(
    r"(?:VALUES|TABLE)-(\d{4}-\d{2}-\d{2})--(\d{2}-\d{2}-\d{2})(?:\(\d+\))?\.csv\Z"
)


def _read_csv(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or not 0 < p.stat().st_size <= MAX_BYTES:
        raise ValueError("VALUES/TABLE must be regular, bounded, non-symlink files")
    b = p.read_bytes()
    if (len(b) != p.stat().st_size or not b.startswith(b"sep=|\r\n")
            or not b.endswith(b"\r\n") or b.count(b"\n") != b.count(b"\r\n")
            or b"\x00" in b):
        raise ValueError("VALUES/TABLE requires original sep=|, CRLF, no BOM")
    rows = [line.split("|") for line in b.decode("cp1251").splitlines()]
    if not 3 <= len(rows) <= MAX_ROWS+4:
        raise ValueError("VALUES/TABLE row count out of bounds")
    return rows, {"basename": p.name, "size_bytes": len(b),
                  "sha256": sha256(b).hexdigest()}


def _source_time(s):
    if not isinstance(s, str) or not TIME_RE.fullmatch(s):
        raise ValueError("VALUES time must be hh:mm:ss.zzz")
    return datetime.strptime(s, "%H:%M:%S.%f")


def _filename_time(name):
    m = FILE_DATE_RE.fullmatch(name)
    if not m:
        return None
    return datetime.strptime(
        m.group(1) + " " + m.group(2), "%Y-%m-%d %H-%M-%S")


def _format_probe(data_rows):
    """4-significant-digit candidate reverse test, not original DWORD proof."""
    numeric = nonzero = four_sig = reproduced = 0
    for row in data_rows:
        for cell in row[1:]:
            if not NUMBER_RE.fullmatch(cell):
                continue
            numeric += 1
            if cell == "0":
                continue
            nonzero += 1
            if len(cell.lstrip("-").replace(",", "").lstrip("0")) <= 4:
                four_sig += 1
            try:
                f32 = struct.pack("<f", float(cell.replace(",", ".")))
                predicted = get_value_text_30(0, f32).text.replace(".", ",")
                if predicted == cell:
                    reproduced += 1
            except (OverflowError, ValueError):
                continue
    return {
        "numeric_cells": numeric,
        "nonzero_numeric_cells": nonzero,
        "nonzero_with_at_most_four_significant_digits": four_sig,
        "reverse_float32_4digit_text_matches": reproduced,
        "reverse_roundtrip_does_not_prove_original_float32_bits": True,
    }


def compare_original_values_table(values_file, table_file) -> dict:
    """Compare actual files without assuming they belong to the same run.

    One unique FULL 30 * ADC text match + date agreement + a time
    proximity to TABLE creation identifies a shared observed snapshot.
    If any check fails, return unverified, NOT "definitely other run".
    No original rows or numeric values are returned in the report.
    """
    values, vf = _read_csv(values_file)
    table, tf = _read_csv(table_file)
    if values[0] != ["sep=", ""] or table[0] != ["sep=", ""]:
        raise ValueError("Source sep header invalid")
    if len(values)<4 or values[1][0]!="" or values[2][0]!="Время":
        raise ValueError("VALUES source two-row/time header missing")
    g, names = values[1], values[2]
    if len(g)!=len(names) or (len(g)-1)%ADC_CELLS:
        raise ValueError("VALUES requires 73 source cells per selected ADC")
    count=(len(g)-1)//ADC_CELLS
    if not 1<=count<=8:
        raise ValueError("VALUES channel count invalid")
    vc=[g[1+i*ADC_CELLS] for i in range(count)]
    if len(set(vc))!=len(vc) or any(
            not re.fullmatch(r"АЦП [1-8]", c) for c in vc):
        raise ValueError("VALUES source ADC selection invalid")
    first=names[1:74]
    if any(not name.startswith("Полоса ") for name in first[:SPEC_CELLS]):
        raise ValueError("VALUES original 43-band spectrum order invalid")
    for i,ch in enumerate(vc):
        sl=slice(1+i*ADC_CELLS,1+(i+1)*ADC_CELLS)
        if g[sl]!=[ch]*ADC_CELLS or names[sl]!=first:
            raise ValueError("VALUES channel SPEC43/RESULT6/BAND24 layout mismatch")
    if any(len(row)!=len(g) for row in values[3:]):
        raise ValueError("VALUES source data row width inconsistent")
    ts=[_source_time(r[0]) for r in values[3:]]
    if any(b<=a for a,b in zip(ts,ts[1:])):
        raise ValueError("VALUES non-monotonic or duplicate tick")
    if (len(table)!=40 or table[32]!=[""] or table[33][0]!="Наименование параметра"
            or table[1][0]!="Наименование параметра" or table[1][-1]!=""):
        raise ValueError("TABLE original 30 ADC + separator + 6 TACH layout missing")
    tc=table[1][1:-1]
    if not tc or len(tc)>8 or len(set(tc))!=len(tc):
        raise ValueError("TABLE selected ADC headers invalid")
    if any(len(r)!=len(table[1]) for r in table[2:32]):
        raise ValueError("TABLE source ADC result widths invalid")
    if any(len(r)<2 for r in table[34:]):
        raise ValueError("TABLE source TACH result widths invalid")
    if [r[0] for r in table[2:32]]!=first[SPEC_CELLS:]:
        raise ValueError("TABLE source 30 result/band names mismatch")
    same_channels=(tc==vc)
    fields=[]
    if same_channels:
        for i,r in enumerate(table[2:32]):
            for j,ch in enumerate(tc):
                field=1+ADC_CELLS*vc.index(ch)+SPEC_CELLS+i
                fields.append((r[j+1],field))
    scores=[(sum(row[i]==expected for expected,i in fields),row[0])
            for row in values[3:]] if same_channels else []
    best=max((n for n,_ in scores),default=0)
    perfect=[at for n,at in scores if fields and n==len(fields)]
    ordered=sorted((n for n,_ in scores),reverse=True)
    vdate,tdate=_filename_time(vf["basename"]),_filename_time(tf["basename"])
    same_date=bool(vdate is not None and tdate is not None
                   and vdate.date()==tdate.date())
    delta=None
    if len(perfect)==1 and tdate is not None:
        tick=_source_time(perfect[0])
        actual=tdate.replace(hour=tick.hour,minute=tick.minute,
                             second=tick.second,microsecond=tick.microsecond)
        delta=round((actual-tdate).total_seconds(),3)
    verified=bool(same_channels and same_date and len(perfect)==1
                  and delta is not None and -2<=delta<=2)
    interval=Counter(round((b-a).total_seconds()*1000)
                     for a,b in zip(ts,ts[1:]))
    return {
        "schema":SOURCE,
        "original_files":(vf,tf),
        "original_encoding":"cp1251",
        "original_delimiter":"|",
        "original_line_ending":"CRLF",
        "original_has_bom":False,
        "values_channels":tuple(vc),
        "table_channels":tuple(tc),
        "source_columns_per_adc":ADC_CELLS,
        "source_spec_per_adc":SPEC_CELLS,
        "source_result_per_adc":RESULT_CELLS,
        "source_band_per_adc":BAND_CELLS,
        "values_tick_count":len(values)-3,
        "values_columns_including_time":len(g),
        "values_first_tick":values[3][0],
        "values_last_tick":values[-1][0],
        "values_interval_ms_histogram":dict(sorted(interval.items())),
        "table_result_rows":30,
        "table_tach_rows":6,
        "cells_compared_per_row":len(fields),
        "best_same_row_exact_cell_matches":best,
        "second_best_same_row_matches":ordered[1] if len(ordered)>1 else None,
        "number_of_perfect_matching_ticks":len(perfect),
        "unique_matching_tick":perfect[0] if len(perfect)==1 else None,
        "filename_date_agrees":same_date,
        "matching_tick_minus_table_filename_seconds":delta,
        "classification":"verified_same_snapshot" if verified else "separate_or_not_proven",
        "original_win32_rounding_byte_parity_verified":False,
        "instrument_live_register_parity_verified":False,
        "bin_tsxml_same_run_verified":False,
        "includes_private_original_values":False,
        "format_probe":_format_probe(values[3:]),
    }



def verify_full_table_byte_rebuild(values_file,table_file)->dict:
    """Reconstruct TABLE entirely from a unique original VALUES snapshot.

    This is stronger than matching 90 cells: includes section headers,
    source cell titles, units, CRLF and CP1251. It DOES NOT claim that
    guessed register raw input reproduces an original Delphi Float32.
    When TACH is selected, source VALUES/TABLE may not share the same
    snapshots; this reconstruction intentionally requires no TACH columns.
    """
    from .original_ru_csv_layout import (
        source_ru_table_rows,source_ru_encode_csv,PROFILE,
    )
    paired=compare_original_values_table(values_file,table_file)
    ok=paired["classification"]=="verified_same_snapshot"
    result={
        "schema":"MVK_SOURCE_ORIGINAL_TABLE_FULL_BYTE_REBUILD_V1",
        "source_layout_profile":PROFILE,
        "original_values_table_unique_snapshot_verified":ok,
        "full_table_bytes_equal":False,
        "full_table_length":None,
        "full_table_sha256":None,
        "original_delphi_input_register_parity_verified":False,
        "original_delphi_formatfloat_all_inputs_verified":False,
        "private_original_values_embedded":False,
        "instrument_commands_sent":False,
    }
    if not ok:
        return result
    vr,_=_read_csv(values_file)
    tr,_=_read_csv(table_file)
    # Original TACH section with unselected TACH has an empty header
    # and 6 'label|units' lines. A selected TACH cannot be guessed.
    if tr[33]!=["Наименование параметра",""] or any(
            len(row)!=2 for row in tr[34:]):
        return result
    clock=paired["unique_matching_tick"]
    matches=[row for row in vr[3:] if row[0]==clock]
    if len(matches)!=1:return result
    matched=matches[0]
    channels=[int(ch.rsplit(" ",1)[1]) for ch in paired["values_channels"]]
    per_adc=[
        [matched[1+i*ADC_CELLS+SPEC_CELLS+j] for j in range(30)]
        for i in range(len(channels))]
    reconstructed=source_ru_encode_csv(source_ru_table_rows(
        channels,[],per_adc,[]))
    # Read only in memory and do not return measured values in report.
    original=Path(table_file).read_bytes()
    result["full_table_bytes_equal"]=reconstructed==original
    result["full_table_length"]=len(reconstructed)
    result["full_table_sha256"]=sha256(reconstructed).hexdigest()
    return result


def main(argv=None) -> int:
    """CLI: python -m mvk_compatible.core.original_values_table_pair_qa VALUES TABLE."""
    import argparse
    import json
    parser=argparse.ArgumentParser(
        description="Strict source VALUES/TABLE pairing without leaking CSV rows")
    parser.add_argument("--full-table-parity",action="store_true",
                        help="Verify all TABLE bytes from the unique VALUES snapshot")
    parser.add_argument("values")
    parser.add_argument("table")
    args=parser.parse_args(argv)
    result=(verify_full_table_byte_rebuild(args.values,args.table)
            if args.full_table_parity else
            compare_original_values_table(args.values,args.table))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if (result.get("classification")=="verified_same_snapshot" or
                 result.get("full_table_bytes_equal") is True) else 2


if __name__=="__main__":
    raise SystemExit(main())
