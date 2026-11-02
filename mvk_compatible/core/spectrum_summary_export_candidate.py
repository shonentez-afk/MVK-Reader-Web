"""Stage111G local-only candidate for MVKView Copy/Save triplet.

Private _Unit128 0084BC28: 007B2090 formatting of OutputMean with 3
digits, OutputPeakX*XScale and OutputPeakY with 4 digits, tab-separated.
0084BD7C: sep=| CSV, pipe triplet, append to existing file.
Original localized header and Delphi FormatFloat are NOT certified.
"""
from __future__ import annotations
from pathlib import Path
import math
from .cursor_format_candidate import format_cursor_idr_candidate

RESEARCH_HEADER='Интегральное значение (IDR-кандидат)|Частота пика, Гц (IDR-кандидат)|Амплитуда пика (IDR-кандидат)'
RESEARCH_UNCALIBRATED_HEADER=(
    'Интегральное значение (НЕ КАЛИБРОВАНО, условные единицы)|'
    'Частота пика, Гц (локальный FFT)|'
    'Амплитуда пика (НЕ КАЛИБРОВАНО, условные единицы)')
MAX_EXPORT_BYTES=2_000_000


def spectrum_triplet_text(summary:dict,*,separator:str='\t',
                          decimal_separator:str='.') -> str:
    """Only three aggregated metrics, never full signal/FFT or original AUX."""
    if separator not in ('\t','|'):
        raise ValueError('Only original tab clipboard and pipe file separators are supported')
    if summary.get('source')!='APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE':
        raise ValueError('Source-derived summary required; not an instrument AUX value')
    values=(summary['output_mean'],summary['output_peak_frequency_hz'],summary['output_peak_y'])
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError('Non-finite spectrum summary')
    return separator.join(format_cursor_idr_candidate(v,digits,decimal_separator)
                          for v,digits in zip(values,(3,4,4)))


def append_research_summary_csv(path:str|Path,summary:dict,*,
                                decimal_separator:str=',',
                                uncalibrated:bool=False)->dict:
    """Explicit local CSV file, research-only header: NEVER mix with original.

    An existing file is appendable only if it has *our exact candidate*
    header; original MVKView SPEC-FREQ exports are deliberately rejected.
    """
    target=Path(path)
    if target.suffix.lower()!='.csv' or target.is_symlink() or not target.parent.is_dir():
        raise ValueError('Choose a regular local .csv path, not a symlink')
    line=spectrum_triplet_text(summary,separator='|',decimal_separator=decimal_separator)
    if '\n' in line or '\r' in line:raise ValueError('Invalid local summary')
    if type(uncalibrated) is not bool:
        raise ValueError('uncalibrated must be an explicit boolean')
    header=(RESEARCH_UNCALIBRATED_HEADER if uncalibrated else RESEARCH_HEADER)
    start='sep=|\r\n'+header+'\r\n'
    if target.exists():
        if not target.is_file() or target.stat().st_size>MAX_EXPORT_BYTES:
            raise ValueError('Refuse non-file or oversized local CSV')
        with target.open('r',encoding='utf-8',newline='') as stream:
            current=stream.read(len(start)+3)
        if not current.startswith(start):
            raise ValueError('Refuse to append to original MVKView or unverified CSV header')
    elif len(start)+len(line)>MAX_EXPORT_BYTES:
        raise ValueError('Export exceeds configured bounds')
    with target.open('a',encoding='utf-8',newline='') as stream:
        if target.stat().st_size==0:stream.write(start)
        stream.write(line+'\r\n')
    return {'source':'APP_DERIVED_SPECTRUM_TRIPLET_EXPORT_CANDIDATE',
            'path':str(target),'row_values':3,
            'original_delphi_export_format_verified':False,
            'physical_units_verified':False if uncalibrated else None,
            'uncalibrated_source_declared':uncalibrated}
