"""Fail-closed read-only cross-file evidence for original MVK01 measurements.

Operator-provided original BIN/TSXML and VALUES/TABLE may be from DIFFERENT
captures. Never pair them by filename/date, or rescale BIN to force a match.

VALUES<->TABLE can be proved the *same original text snapshot* by all
RESULT/BAND cells; BIN<->TSXML is checked by exact channel, length, type and
rate; linking the two pairs is statistical only, on PREDECLARED ADC1
'Виброускорение, Польз. 2' vs AC RMS of a half-second BIN window.

The lag is selected on the FIRST part of VALUES, then measured on HELD-OUT
later ticks; no reported identity/Win32/firmware parity flags become True.
No network, instrument TX, original EXE or private file contents in receipt.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import argparse
import json
import math
import re
import xml.etree.ElementTree as ET

import numpy as np

from .original_values_table_pair_qa import (
    ADC_CELLS, SPEC_CELLS, _read_csv, _filename_time, compare_original_values_table,
)

SOURCE="MVK_ORIGINAL_MODE2_BIN_TSXML_VALUES_TABLE_CROSS_RUN_QA_V1"
MAX_BIN_BYTES=64*1024*1024
MAX_XML_BYTES=32*1024
MIN_TICKS=30
DEFAULT_BROADBAND_FIELD="Виброускорение, Польз. 2"
_STEP_MS=25
_SHIFTS_MS=range(-1000,1001,_STEP_MS)
_SERIAL_RE=re.compile(r"MVK[0-9]+-ADC([1-8])\Z")
_CLONE_RE=re.compile(r"\([0-9]+\)(?=\.bin\Z)",re.IGNORECASE)
_VALID_NUM=re.compile(r"-?[0-9]+(?:,[0-9]+)?\Z")


def _regular(path,max_size,label):
    p=Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("Original "+label+" must be a regular local file")
    st=p.stat()
    if not 0<st.st_size<=max_size:
        raise ValueError("Original "+label+" has invalid bounded byte size")
    body=p.read_bytes()
    if len(body)!=st.st_size or (p.stat().st_size,p.stat().st_mtime_ns)!=(
            st.st_size,st.st_mtime_ns):
        raise ValueError("Original "+label+" changed during inspection")
    return p,body


def _text(node,name):
    part=node.find(name)
    if part is None or part.text is None or not part.text.strip():
        raise ValueError("Original TSXML lacks source "+name)
    return part.text.strip()


def _parse_tsxml(file):
    path,body=_regular(file,MAX_XML_BYTES,"TSXML")
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise ValueError("Original TSXML cannot contain external entity/DTD")
    try:
        root=ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError("Original TSXML invalid XML") from exc
    if root.tag!="MainRoot":
        raise ValueError("Original TSXML has unexpected root")
    try:
        finished=datetime.strptime(_text(root,"DateTime"),"%m/%d/%Y %I:%M:%S %p")
        hz=int(_text(root,"FrequencyPerChannel"))
        quantity=int(_text(root,"ChannelsQuantity"))
        from_ms=float(_text(root,"From"))
        to_ms=float(_text(root,"To"))
        channel=root.find("./Channels/Channel")
        if channel is None:
            raise ValueError("Original TSXML Channel is missing")
        ch=int(_text(channel,"ChannelNumber"))
        per_channel=int(_text(channel,"ChannelFrequency"))
        data_bytes=int(_text(channel,"DataLength"))
        offset=int(_text(channel,"DataOffset"))
        gain=float(_text(channel,"InternalChannelGain"))
        serial=_text(channel,"ChannelName")
        filename=_text(root,"DataFileName").replace("\\","/").rsplit("/",1)[-1]
    except (TypeError,OverflowError,ValueError) as exc:
        raise ValueError("Original TSXML fields cannot be decoded") from exc
    if (quantity!=1 or not 1<=ch<=8 or not 1024<=hz<=262144
        or per_channel!=hz or _text(channel,"RealDataType")!="Single"
        or offset!=0 or not 0<data_bytes<=MAX_BIN_BYTES or data_bytes%4
        or not math.isfinite(gain) or gain<=0
        or not math.isfinite(from_ms) or abs(from_ms)>1e-6
        or not math.isfinite(to_ms) or to_ms<=0
        or filename.startswith(".") or "/" in filename
        or _text(channel,"Units") not in ("м/с2","м/с²")
        or not _SERIAL_RE.fullmatch(serial)
        or int(_SERIAL_RE.fullmatch(serial).group(1))!=ch):
        raise ValueError("Original TSXML source ADC single-channel contract mismatched")
    actual_duration=data_bytes/4/hz
    if abs(to_ms/1000-actual_duration)>.00003:
        raise ValueError("Original TSXML duration inconsistent with BIN bytes")
    return {
        "tsxml_sha256":sha256(body).hexdigest(),
        "channel":ch,
        "sample_rate_hz":hz,
        "duration_seconds":actual_duration,
        "data_bytes":data_bytes,
        "closed_local_time":finished,
        "start_local_time":finished-timedelta(seconds=actual_duration),
        "data_filename":filename,
        "channel_serial":serial,
        "internal_gain_declared":gain,
        "culture":_text(root,"Culture"),
    }


def _parsed_values(values_file,channel,field_name):
    rows,meta=_read_csv(values_file)
    if len(rows)<4 or rows[1][0]!="" or rows[2][0]!="Время":
        raise ValueError("Original VALUES source header is incomplete")
    groups,titles=rows[1:3]
    if len(groups)!=len(titles) or (len(groups)-1)%ADC_CELLS:
        raise ValueError("Original VALUES channels must have 73 source cells")
    ch_name=f"АЦП {channel}"
    offsets=[1+i*ADC_CELLS for i in range((len(groups)-1)//ADC_CELLS)
             if groups[1+i*ADC_CELLS]==ch_name]
    if len(offsets)!=1:
        raise ValueError("Original VALUES does not have one selected matching ADC")
    start=offsets[0]
    if groups[start:start+ADC_CELLS]!=[ch_name]*ADC_CELLS:
        raise ValueError("Original VALUES source channel order invalid")
    if titles[start:start+ADC_CELLS].count(field_name)!=1:
        raise ValueError("Original VALUES requested field is not unique")
    column=start+titles[start:start+ADC_CELLS].index(field_name)
    if column<start+SPEC_CELLS+6:
        raise ValueError("Original correlation field must be a BAND/RESULT text")
    times=[]
    values=[]
    for row in rows[3:]:
        if len(row)!=len(groups) or not _VALID_NUM.fullmatch(row[column]):
            raise ValueError("Original VALUES has nonnumeric/missing selected field")
        try:
            t=datetime.strptime(row[0],"%H:%M:%S.%f").time()
            f=float(row[column].replace(",","."))
        except ValueError as exc:
            raise ValueError("Original VALUES row time/value invalid") from exc
        if not math.isfinite(f):
            raise ValueError("Original VALUES contains nonfinite selected values")
        times.append(t)
        values.append(f)
    if len(times)<MIN_TICKS:
        raise ValueError("Original VALUES requires enough independent ticks")
    return times,np.asarray(values,dtype=np.float64),meta


def _pearson(a,b):
    x=np.asarray(a,dtype=np.float64)
    y=np.asarray(b,dtype=np.float64)
    if x.size!=y.size or x.size<3 or not (
            np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        return None
    x=x-x.mean();y=y-y.mean()
    norm=float(np.linalg.norm(x)*np.linalg.norm(y))
    return float(np.dot(x,y)/norm) if norm>1e-12 else None


def _bin_statistics(body,hz):
    # Chunked cumsum is independent of any source vendor calibration.
    # This is AC RMS (std), NOT original 3rd-octave filtering.
    wave=np.frombuffer(body,dtype="<f4")
    if not bool(np.isfinite(wave).all()):
        raise ValueError("Original BIN contains non-finite Float32 data")
    dbl=wave.astype(np.float64)
    count=len(dbl)
    sums=np.empty(count+1,dtype=np.float64)
    powers=np.empty(count+1,dtype=np.float64)
    sums[0]=powers[0]=0
    np.cumsum(dbl,out=sums[1:])
    np.cumsum(dbl*dbl,out=powers[1:])
    return sums,powers


def _window_rms(sums,powers,start,end):
    n=end-start
    if start<0 or end>len(sums)-1 or n<64:
        return None
    avg=(sums[end]-sums[start])/n
    variance=(powers[end]-powers[start])/n-avg*avg
    return math.sqrt(max(0.,variance))


def compare_original_bin_tsxml_values_table(
    bin_file,tsxml_file,values_file,table_file, *,
    source_field=DEFAULT_BROADBAND_FIELD,
)->dict:
    """Three distinct evidence strengths: exact TSXML/BIN, text snapshot,
    then out-of-sample waveform/VALUES timing similarity.

    A strong holdout correlation proves only that the trends are
    statistically consistent with a common measurement. It CANNOT prove
    identical source device packets, Delphi x87, or calibration.
    """
    if source_field!=DEFAULT_BROADBAND_FIELD:
        raise ValueError("Only predeclared source broadband field is audited")
    info=_parse_tsxml(tsxml_file)
    bp,raw=_regular(bin_file,MAX_BIN_BYTES,"Float32 BIN")
    if len(raw)!=info["data_bytes"] or (
            _CLONE_RE.sub("",bp.name)!=info["data_filename"]):
        raise ValueError("Original BIN size/name mismatch with TSXML declaration")
    if bp.name.split("-ADC",1)[0]!=info["channel_serial"].split("-ADC",1)[0]:
        raise ValueError("Original BIN instrument serial differs from TSXML")
    if f"-ADC{info['channel']}-" not in bp.name:
        raise ValueError("Original BIN channel differs from TSXML channel")
    paired=compare_original_values_table(values_file,table_file)
    original_table_same_snapshot=(paired["classification"]=="verified_same_snapshot")
    times,target,meta=_parsed_values(
        values_file,info["channel"],source_field)
    start=info["start_local_time"];closed=info["closed_local_time"]
    bin_day=start.date()
    relative=[]
    for t in times:
        stamp=datetime.combine(bin_day,t)
        if stamp<start-timedelta(hours=12):
            stamp+=timedelta(days=1)
        relative.append((stamp-start).total_seconds())
    relative=np.asarray(relative,dtype=np.float64)
    filename_time=_filename_time(meta["basename"])
    # Time-of-day alone is NOT a session identity. The original VALUES
    # filename must also agree with the TSXML calendar day, permitting
    # a legitimate midnight-spanning instrument run.
    same_day=bool(
        filename_time is not None and
        filename_time.date() in (
            info["start_local_time"].date(),info["closed_local_time"].date()))
    sane=bool(
        same_day and np.all(np.diff(relative)>0)
        and relative[0]>=-.75
        and relative[-1]<=info["duration_seconds"]+.75
        and original_table_same_snapshot)
    baseline={
        "schema":SOURCE,
        "original_files_sha256":{
            "BIN":sha256(raw).hexdigest(),
            "TSXML":info["tsxml_sha256"],
            "VALUES":meta["sha256"],
            "TABLE":paired["original_files"][1]["sha256"],
        },
        "bin_tsxml_exact_channel_bytes_rate_duration_verified":True,
        "values_table_same_original_snapshot_verified":
            original_table_same_snapshot,
        "values_table_matched_cells":paired["cells_compared_per_row"],
        "values_table_unique_matching_tick":paired["unique_matching_tick"],
        "selected_source_adc":info["channel"],
        "bin_sample_rate_hz":info["sample_rate_hz"],
        "bin_samples":len(raw)//4,
        "bin_duration_seconds":info["duration_seconds"],
        "values_ticks_compared":len(target),
        "bin_values_time_window_plausible":sane,
        "values_filename_calendar_day_consistent_with_tsxml":same_day,
        "source_original_broadband_field":source_field,
        "alignment_window_ms":500,
        "lag_grid_ms":[_SHIFTS_MS.start,_SHIFTS_MS.stop-1,_STEP_MS],
        "source_locale_from_tsxml":info["culture"],
        "bin_gain_is_not_assumed_equal_to_live_f_range":True,
        "same_physical_capture_authenticated":False,
        "same_original_raw_tcp_payload_authenticated":False,
        "original_delphi_numeric_parity_verified":False,
        "original_writevalues_to_signal_byte_parity_verified":False,
        "original_getsignal_fft_parity_verified":False,
        "hardware_commands_sent":False,
        "private_signal_and_csv_cells_in_report":False,
        "private_paths_and_original_filenames_in_report":False,
    }
    if not sane:
        return {**baseline,"classification":"separate_or_not_proven",
                "reason":"source timestamps or original TABLE snapshot not proven"}
    hz=info["sample_rate_hz"]
    sums,powers=_bin_statistics(raw,hz)
    split=len(target)//2
    # Keep a 3-tick gap between fit and holdout, so a 0.5s moving window
    # cannot cover the same 0.5s epoch on both sides of the partition.
    train=np.arange(0,split-2)
    test=np.arange(split+1,len(target))
    if len(train)<10 or len(test)<10:
        return {**baseline,"classification":"separate_or_not_proven",
                "reason":"insufficient disjoint train/holdout ticks"}
    best=None
    valid_shifts=0
    for lag in _SHIFTS_MS:
        rms=[]
        for at in relative:
            end=int(round((at+lag/1000)*hz))
            begin=end-int(round(hz*.5))
            v=_window_rms(sums,powers,begin,end)
            rms.append(v)
        if any(v is None for v in rms):
            continue
        predictor=np.asarray(rms,dtype=np.float64)
        fit=_pearson(predictor[train],target[train])
        if fit is None:continue
        valid_shifts+=1
        if best is None or fit>best[0]:
            best=(fit,lag,predictor)
    if best is None:
        return {**baseline,"classification":"separate_or_not_proven",
                "reason":"no complete original source alignment window",
                "tested_lags":valid_shifts}
    train_corr,lag,predictor=best
    holdout=_pearson(predictor[test],target[test])
    full=_pearson(predictor,target)
    cycled=[_pearson(predictor[test],np.roll(target[test],shift))
            for shift in range(1,len(test))]
    null=[x for x in cycled if x is not None]
    pvalue=(1+sum(v>=holdout for v in null))/(len(null)+1) if (
        null and holdout is not None) else None
    ratio=float(np.median(target[test]/predictor[test])) if (
        np.all(predictor[test]>0)) else None
    corr_strong=bool(
        train_corr>=.8 and holdout is not None and holdout>=.8
        and pvalue is not None and pvalue<=.05)
    return {
        **baseline,
        "classification":("time_series_aligned_not_byte_authenticated"
                          if corr_strong else "separate_or_not_proven"),
        "selected_lag_ms":lag,
        "valid_lags_fitted_on_first_half":valid_shifts,
        "train_source_ticks":len(train),
        "holdout_source_ticks":len(test),
        "train_pearson":train_corr,
        "holdout_pearson":holdout,
        "all_tick_pearson":full,
        "holdout_circular_shift_null_max":max(null) if null else None,
        "holdout_circular_shift_pvalue":pvalue,
        "holdout_bin_to_values_rms_ratio_not_calibration":ratio,
        "lag_fitted_without_holdout_peeking":True,
        "raw_signal_vs_bandlimited_measurement_not_same_algorithm":True,
        "strong_statistical_evidence_only":corr_strong,
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(
        description="Local, read-only original BIN/TSXML/VALUES/TABLE cross-run evidence")
    parser.add_argument("bin")
    parser.add_argument("tsxml")
    parser.add_argument("values")
    parser.add_argument("table")
    a=parser.parse_args(argv)
    report=compare_original_bin_tsxml_values_table(
        a.bin,a.tsxml,a.values,a.table)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    # Never exit 0 as proof of original 1:1. Exit 0 only when strong
    # *statistical* relation and original VALUES/TABLE snapshot are found.
    return 0 if report["classification"]=="time_series_aligned_not_byte_authenticated" else 2


if __name__=="__main__":
    raise SystemExit(main())
