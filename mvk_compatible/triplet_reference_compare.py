"""Stage111H: PRIVATE operator reference for original MVKView 3-value Copy triplet.

Source _Unit128.pas 0084BC28: TAB separated OutputMean(3),
OutputPeakX*XScale(4), OutputPeakY(4) via 007B2090.
Numerical source GetSpectrum summary in Stage111G is only a candidate.
Read operator-exported SINGLE-LINE text; NEVER retrieve data from a device,
rewrite vendor CSV, or commit private measurements. No interpolation/offset.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from .core.spectrum_summary_export_candidate import spectrum_triplet_text

LABELS = ('output_mean','output_peak_frequency_hz','output_peak_y')
CANDIDATE_SOURCE = 'APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE'


def parse_operator_triplet(text:str,*,separator:str='\t',
                           decimal_separator:str=',')->tuple[float,float,float]:
    """Require one exact 3-field source line. No ambiguous decimal auto-detect."""
    if separator not in ('\t','|') or decimal_separator not in (',','.'):
        raise ValueError('Explicit supported TAB/pipe and comma/dot required')
    if not isinstance(text,str) or '\x00' in text or len(text)>8192:
        raise ValueError('Invalid original clipboard text')
    lines=text.strip('\r\n').splitlines()
    if len(lines)!=1:
        raise ValueError('Expected ONE original Copy triplet, not a time series')
    parts=lines[0].split(separator)
    if len(parts)!=3:
        raise ValueError('Original MVKView Copy must contain exactly three columns')
    result=[]
    for part in parts:
        item=part.strip()
        if not item or any(c in item for c in '\t|\r\n;'):
            raise ValueError('Unexpected original number field')
        if decimal_separator==',':
            if '.' in item or item.count(',')>1:raise ValueError('Decimal locale mismatch')
            item=item.replace(',','.')
        elif ',' in item:
            raise ValueError('Decimal locale mismatch')
        try:
            value=float(item)
        except ValueError as exc:
            raise ValueError('Original triplet contains non-numeric value') from exc
        if not math.isfinite(value):
            raise ValueError('Original triplet may not contain NaN or Infinity')
        result.append(value)
    return tuple(result)


def read_operator_triplet_file(path:Path,*,separator:str='\t',
                               decimal_separator:str=',',
                               encoding:str='utf-8-sig')->dict:
    """Private file only; SHA for traceability; do not print original values."""
    file=Path(path)
    if (file.is_symlink() or not file.is_file() or file.stat().st_size>8192
        or encoding not in ('utf-8-sig','cp1251')):
        raise ValueError('Expected a small regular local TXT file (UTF-8/CP1251)')
    raw=file.read_bytes()
    values=parse_operator_triplet(raw.decode(encoding),
                    separator=separator,decimal_separator=decimal_separator)
    return {'values':values,'sha256':hashlib.sha256(raw).hexdigest(),
            'field_count':3,'source':'OPERATOR_SUPPLIED_ORIGINAL_TRIPLET'}


def compare_operator_triplet(candidate:dict,original:dict, *,
                             abs_tolerance:float=1e-5,
                             rel_tolerance:float=.01,
                             operator_confirmed_same_window:bool=False)->dict:
    """Numerical diagnostics only. Operator declaration is NOT a golden proof."""
    if (candidate.get('source')!=CANDIDATE_SOURCE
        or original.get('source')!='OPERATOR_SUPPLIED_ORIGINAL_TRIPLET'):
        raise ValueError('Expected app-derived GetSpectrum and operator original')
    for tol in (abs_tolerance,rel_tolerance):
        if not math.isfinite(tol) or tol<0:raise ValueError('Invalid numerical tolerance')
    if not isinstance(operator_confirmed_same_window,bool):
        raise ValueError('Same-window declaration must be boolean')
    vals=original['values']
    if len(vals)!=3:
        raise ValueError('Expected three original field values')
    differences={}
    flags={}
    for key,ref in zip(LABELS,vals):
        val=float(candidate[key])
        if not math.isfinite(val) or not math.isfinite(float(ref)):
            raise ValueError('Input values must be finite')
        delta=abs(val-float(ref))
        differences[key]=delta
        flags[key]=delta <= abs_tolerance+rel_tolerance*abs(float(ref))
    return {
        'source':'LOCAL_MVKVIEW_TRIPLET_COMPARISON_CANDIDATE',
        'reference_sha256':original.get('sha256'),
        'field_count':3,
        'absolute_errors':differences,
        'within_tolerance_per_field':flags,
        'within_supplied_tolerances':all(flags.values()),
        'operator_confirmed_same_signal_and_window':operator_confirmed_same_window,
        'original_delphi_parity_verified':False,
        'original_display_text_parity_verified':False,
        'warning':'Numerical diagnostic only; original x87/FormatFloat/FRange, exact archive window not certified'
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(
        description='Offline local comparison of original MVKView Copy triplet to candidate.')
    parser.add_argument('--archive',required=True)
    parser.add_argument('--reference',required=True,
                        help='Local one-line TAB-separated original MVKView Copy text')
    parser.add_argument('--channel',type=int,required=True,choices=range(1,9))
    parser.add_argument('--n-fft',required=True,type=int)
    parser.add_argument('--mode',required=True,type=int,choices=range(4))
    parser.add_argument('--code',type=int,default=0,choices=range(32))
    parser.add_argument('--idp',help='Local original IDP, only for --code > 0')
    parser.add_argument('--start-s',type=float)
    parser.add_argument('--end-s',type=float)
    parser.add_argument('--f-range',type=float,default=None,
                        help='Operator-entered FRange; if omitted candidate uses unverified 1.0')
    parser.add_argument('--backend',choices=['idr_float32','numpy'],default='idr_float32')
    parser.add_argument('--separator',choices=['tab','pipe'],default='tab')
    parser.add_argument('--decimal',choices=[',','.'],default=',')
    parser.add_argument('--encoding',choices=['utf-8-sig','cp1251'],default='utf-8-sig')
    parser.add_argument('--abs-tol',type=float,default=1e-5)
    parser.add_argument('--rel-tol',type=float,default=.01)
    parser.add_argument('--confirm-same-window',action='store_true')
    parser.add_argument('--report-json',help='Optional private local summary report')
    args=parser.parse_args(argv)
    try:
        from .core import OfflineSession
        from .core.envelope_idr_candidate import EnvelopeProfile
        session=OfflineSession.open(args.archive)
        if args.code:
            if not args.idp or args.start_s is not None:
                raise ValueError('Envelope needs explicit local IDP and optional --end-s only')
            profile=EnvelopeProfile.from_original_local_idp(args.idp)
            spectrum=session.spectrum_envelope(
                args.channel,args.code,args.n_fft,profile,
                end_s=args.end_s,mode=args.mode,backend=args.backend,
                f_range=1.0 if args.f_range is None else args.f_range)
        else:
            if args.idp or args.end_s is not None:
                raise ValueError('Plain BIN FFT accepts --start-s without IDP/end-s')
            spectrum=session.spectrum(
                args.channel,args.n_fft,args.mode,start_s=args.start_s,
                max_hz=1e9,max_points=args.n_fft//2,backend=args.backend,
                f_range=args.f_range)
        original=read_operator_triplet_file(
            Path(args.reference),separator='\t' if args.separator=='tab' else '|',
            decimal_separator=args.decimal,encoding=args.encoding)
        report=compare_operator_triplet(spectrum['spectrum_summary'],original,
            abs_tolerance=args.abs_tol,rel_tolerance=args.rel_tol,
            operator_confirmed_same_window=args.confirm_same_window)
        report['candidate_f_range_used']=spectrum.get('f_range_used',1.0)
        report['candidate_f_range_source']=spectrum.get(
            'f_range_source',
            'OPERATOR_SUPPLIED_UNVERIFIED' if args.f_range is not None
            else 'DEFAULT_ONE_NOT_CALIBRATION_VERIFIED')
        report['candidate_f_range_original_verified']=False
        report['candidate_window_origin_verified']=False
        if args.report_json:
            path=Path(args.report_json)
            if path.is_symlink() or not path.parent.is_dir():
                raise ValueError('Refusing nonlocal/symlink report path')
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report['within_supplied_tolerances'] else 1
    except (ValueError,TypeError,KeyError,UnicodeError,OSError,OverflowError) as exc:
        parser.exit(2,'Локальное сравнение отклонено: '+str(exc)+'\n')


if __name__=='__main__':
    sys.exit(main())
