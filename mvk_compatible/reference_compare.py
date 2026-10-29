"""Stage111F LOCAL comparison tool for an operator-exported original MVKView spectrum.

The tool NEVER opens the instrument, connects a socket, pushes data, or
accepts the candidate as 'original'. No automated golden source is currently
available in this project. Quantitative differences require the SAME signal,
FFT N, mode, IDP code and archive end/window on the original MVKView.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np


def read_original_two_column_csv(path:Path,*,delimiter:str=';',decimal:str=',')->dict:
    """Read explicitly exported columns frequency_hz / amplitude (no guessing).

    Export can be transcribed from original MVKView clipboard into local CSV;
    no unsupported automatic parsing of Delphi's actual clipboard format.
    """
    path=Path(path)
    if (path.is_symlink() or not path.is_file() or path.stat().st_size>12_000_000
        or delimiter not in (',',';','\t') or decimal not in (',','.')
        or delimiter==decimal):
        raise ValueError('Expected local CSV under 12MB with explicit delimiter and decimal')
    rows=[]
    with path.open('r',encoding='utf-8-sig',newline='') as stream:
        reader=csv.reader(stream,delimiter=delimiter)
        header=next(reader,[])
        if [h.strip().lower() for h in header]!=['frequency_hz','amplitude']:
            raise ValueError('Reference CSV must have frequency_hz;amplitude header')
        for row in reader:
            if len(row)!=2:raise ValueError('Invalid reference CSV row')
            try:
                f=float(row[0].strip().replace(decimal,'.'))
                a=float(row[1].strip().replace(decimal,'.'))
            except ValueError as exc:
                raise ValueError('Non-numeric original reference CSV') from exc
            if not math.isfinite(f) or not math.isfinite(a):
                raise ValueError('Reference CSV may not contain NaN or Infinity')
            rows.append((f,a))
            if len(rows)>131072:raise ValueError('Reference CSV exceeds original N/2 bin bound')
    if len(rows)<2:
        raise ValueError('Original spectrum needs at least two bins')
    freq,amp=np.asarray(rows,dtype=np.float64).T
    if freq[0]<0 or not np.all(np.diff(freq)>0):
        raise ValueError('Original spectrum frequencies must be strictly increasing')
    return {'frequency_hz':freq,'amplitude':amp,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'row_count':len(freq)}


def compare_full_spectrum(candidate:dict,original:dict, *,
                          frequency_tolerance_hz:float=1e-6,
                          absolute_tolerance:float=1e-5,
                          relative_tolerance:float=.01,
                          original_metadata:dict|None=None)->dict:
    """No interpolation or index shifting, because that hides FFT differences."""
    for v in (frequency_tolerance_hz,absolute_tolerance,relative_tolerance):
        if not math.isfinite(v) or v<0:
            raise ValueError('Comparison tolerances must be nonnegative and finite')
    a=np.asarray(candidate['amplitude'],dtype=np.float64)
    b=np.asarray(original['amplitude'],dtype=np.float64)
    x=np.asarray(candidate['frequency_hz'],dtype=np.float64)
    y=np.asarray(original['frequency_hz'],dtype=np.float64)
    if (a.ndim!=1 or b.ndim!=1 or len(a)<2 or len(a)!=len(b)
        or len(a)!=len(x) or len(b)!=len(y)
        or not (np.isfinite(a).all() and np.isfinite(b).all() and np.isfinite(x).all() and np.isfinite(y).all())):
        raise ValueError('Reference and candidate require same full finite N/2 bins')
    mismatch=np.abs(x-y)
    if bool(np.any(mismatch>frequency_tolerance_hz)):
        i=int(np.argmax(mismatch))
        raise ValueError(f'Frequency-grid mismatch at bin {i}; no interpolation permitted')
    delta=np.abs(a-b)
    allowed=absolute_tolerance+relative_tolerance*np.abs(b)
    passed=bool(np.all(delta<=allowed))
    ref_peak=int(np.argmax(b))
    cand_peak=int(np.argmax(a))
    meta_state='NOT_PROVIDED'
    if original_metadata is not None:
        required={'source_app':'MVKView','confirmed_same_signal_and_window':True,
                  'channel':candidate.get('channel'),
                  'envelope_code':candidate.get('code'),
                  'n_fft':candidate.get('n_fft'),
                  'mode':candidate.get('mode'),
                  'output_sample_rate_hz':candidate.get('output_sample_rate_hz'),
                  'original_csv_sha256':original.get('sha256')}
        meta_state=('OPERATOR_ASSERTED_MATCH'
                    if all(original_metadata.get(k)==v for k,v in required.items())
                    else 'MISMATCH_OR_INCOMPLETE')
    return {'source':'LOCAL_REFERENCE_NUMERIC_DIAGNOSTIC',
            'original_app_parity_certified':False,
            'original_metadata_status':meta_state,
            'within_supplied_numeric_tolerance':passed,
            'n_bins_compared':len(a),
            'frequency_grid_max_abs_error_hz':float(np.max(mismatch)),
            'max_absolute_difference':float(np.max(delta)),
            'rms_absolute_difference':float(np.sqrt(np.mean(delta**2))),
            'mean_absolute_difference':float(np.mean(delta)),
            'out_of_tolerance_bins':int(np.count_nonzero(delta>allowed)),
            'ref_peak_bin':ref_peak,'candidate_peak_bin':cand_peak,
            'peak_frequency_difference_hz':float(x[cand_peak]-y[ref_peak]),
            'ref_peak_amplitude_difference':float(a[ref_peak]-b[ref_peak]),
            'reference_csv_sha256':original.get('sha256'),
            'warning':'Numeric-only synthetic/operator reference; original Delphi equality NOT certified. Confirm actual MVKView settings and window independently.'}


def main(argv=None)->int:
    parser=argparse.ArgumentParser(
        description='MVKView original spectrum vs Stage111F candidate — OFFLINE ONLY')
    parser.add_argument('--archive',required=True,help='Local completed Native R6.1 ZIP')
    parser.add_argument('--idp',required=True,help='Local original mvkview.idp (private)')
    parser.add_argument('--reference',required=True,help='Original two-column CSV, never upload')
    parser.add_argument('--reference-metadata',help='Optional locally operator-checked JSON')
    parser.add_argument('--channel',type=int,required=True,choices=range(1,9))
    parser.add_argument('--code',type=int,required=True,choices=range(1,32))
    parser.add_argument('--n-fft',type=int,required=True)
    parser.add_argument('--mode',type=int,required=True,choices=range(4))
    parser.add_argument('--end-s',type=float,help='End of original candidate raw BIN input window')
    parser.add_argument('--f-range',type=float,default=1.0)
    parser.add_argument('--backend',choices=['idr_float32','numpy'],default='idr_float32')
    parser.add_argument('--delimiter',choices=[';',',','tab'],default=';')
    parser.add_argument('--decimal',choices=[',','.'],default=',')
    parser.add_argument('--freq-tol',type=float,default=1e-6)
    parser.add_argument('--abs-tol',type=float,default=1e-5)
    parser.add_argument('--rel-tol',type=float,default=.01)
    parser.add_argument('--report-json',help='Optional explicit private local report output path')
    args=parser.parse_args(argv)
    try:
        from .core import OfflineSession
        from .core.envelope_idr_candidate import EnvelopeProfile
        session=OfflineSession.open(args.archive)
        prof=EnvelopeProfile.from_original_local_idp(args.idp)
        result=session.spectrum_envelope(
            args.channel,args.code,args.n_fft,prof,end_s=args.end_s,
            mode=args.mode,backend=args.backend,f_range=args.f_range)
        reference=read_original_two_column_csv(Path(args.reference),
            delimiter='\t' if args.delimiter=='tab' else args.delimiter,
            decimal=args.decimal)
        metadata=None
        if args.reference_metadata:
            p=Path(args.reference_metadata)
            if p.is_symlink() or not p.is_file() or p.stat().st_size>32_000:
                raise ValueError('Metadata must be small local JSON')
            metadata=json.loads(p.read_text(encoding='utf-8'))
        report=compare_full_spectrum(result,reference,
            frequency_tolerance_hz=args.freq_tol,
            absolute_tolerance=args.abs_tol,relative_tolerance=args.rel_tol,
            original_metadata=metadata)
        if args.report_json:
            out=Path(args.report_json)
            if out.exists() and out.is_symlink():raise ValueError('Refusing symlink report')
            out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report['within_supplied_numeric_tolerance'] else 1
    except (ValueError,KeyError,OSError,TypeError,OverflowError) as exc:
        parser.exit(2,'Не удалось сравнить локальные измерения: '+str(exc)+'\n')


if __name__=='__main__':
    sys.exit(main())
