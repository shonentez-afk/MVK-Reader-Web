"""Stage111S: recovered ORIGINAL MVKView spectrum scale/FFT integer tables.

Privately cross-verified directly in mvkview.idp adjacent static DWORD data
and the matching original _Unit128.pas references at:
  gvar_008D3428 (H values; 10 menu items),
  gvar_008D3450 (FFT lengths; 6 menu items),
  gvar_008D3468 (physical Y divisors; 6 items),
  gvar_008D3480 (dB Y ranges; 6 items).
This file includes only small derivative numeric constants, NEVER original
private IDP/PAS/DFM bytes or instrument data.
Original runtime Canvas/FFT numeric parity is not proven by source constants.
"""
from __future__ import annotations
import math
import numbers
from fractions import Fraction

SOURCE='APP_DERIVED_ORIGINAL_MVKVIEW_SCALE_TABLES_IDR_VERIFIED'
HORIZONTAL_HZ=(25600,12800,6400,3200,1600,800,400,200,100,50)
FFT_WINDOW_SAMPLES=(262144,131072,65536,32768,16384,8192)
PHYSICAL_Y_DIVISORS=(1,10,100,1000,10000,100000)
DB_Y_RANGES=(150,100,75,50,25,10)
PRIVATE_ORIGINAL_ADDRESSES={
    'horizontal':0x008D3428,
    'fft_sizes':0x008D3450,
    'vertical_physical':0x008D3468,
    'vertical_db':0x008D3480,
}


def original_h_scale_options()->tuple[dict,...]:
    """10 source-verified horizontal popup Tag->Hz values."""
    return tuple({
        'source':SOURCE,'tag':i,'hz':v,'caption':f'{v} Гц',
        'source_menu_value_verified':True,
        'original_runtime_canvas_parity_verified':False,
    } for i,v in enumerate(HORIZONTAL_HZ))


def original_v_scale_options(mode:int)->tuple[dict,...]:
    """6 original tags; dB mode0, all other unit modes use divisors.

    Exact localized derived-unit labels depend on original sensor/channel
    settings and are intentionally not fabricated here.
    """
    if isinstance(mode,bool) or not isinstance(mode,numbers.Integral) or int(mode) not in (0,1,2,3):
        raise ValueError('Original spectrum mode must be an integer 0..3')
    db=int(mode)==0
    values=DB_Y_RANGES if db else PHYSICAL_Y_DIVISORS
    return tuple({
        'source':SOURCE,'tag':i,
        'db_range':v if db else None,
        'physical_divisor':v if not db else None,
        'caption':(f'{v} дБ' if db else f'÷ {v}'),
        'source_menu_value_verified':True,
        'actual_channel_derived_units_verified':False,
    } for i,v in enumerate(values))


def original_fft_size_options()->tuple[dict,...]:
    """6 original bSpecLines menu Tag->NFFT source constants."""
    return tuple({
        'source':SOURCE,'tag':i,'n_fft':n,'caption':str(n),
        'source_menu_value_verified':True,
        'actual_archive_history_sufficient':False,
    } for i,n in enumerate(FFT_WINDOW_SAMPLES))


def validate_source_h_scale(hz:int)->int:
    if (isinstance(hz,bool) or not isinstance(hz,numbers.Integral)
            or int(hz) not in HORIZONTAL_HZ):
        raise ValueError('Not one of the 10 verified Delphi horizontal scale presets')
    return int(hz)


def validate_source_v_scale(mode:int,tag:int)->dict:
    options=original_v_scale_options(mode)
    if isinstance(tag,bool) or not isinstance(tag,numbers.Integral) or not 0<=int(tag)<len(options):
        raise ValueError('Not a valid original vertical scale menu tag')
    return dict(options[int(tag)])

def original_fft_resolution_caption(n_fft:int,sample_rate_hz:int|float)->str:
    """Source six-tag FFT menu: Hz per line at the selected sample rate."""
    if (isinstance(n_fft,bool) or not isinstance(n_fft,numbers.Integral)
            or int(n_fft) not in FFT_WINDOW_SAMPLES):
        raise ValueError("Original bSpecLines supports six Delphi N only")
    if (isinstance(sample_rate_hz,bool)
            or not isinstance(sample_rate_hz,numbers.Real)
            or not math.isfinite(float(sample_rate_hz))
            or not 0<float(sample_rate_hz)<=10_000_000):
        raise ValueError("Original FFT resolution requires finite source Fs")
    step=float(sample_rate_hz)/int(n_fft)
    ratio=Fraction(step).limit_denominator(10000)
    if ratio.denominator<=64 and abs(float(ratio)-step)<1e-8:
        value=(str(ratio.numerator) if ratio.denominator==1 else
               f"{ratio.numerator}/{ratio.denominator}")
    else:
        value=f"{step:.6g}"
    return value+" Гц/лин"


def original_physical_y_caption(mode:int,visible_height:float,*,units:str|None=None)->str:
    """Nominal source-mode units, not a hardware calibration attestation."""
    if (isinstance(mode,bool) or not isinstance(mode,numbers.Integral)
            or int(mode) not in (1,2,3)):
        raise ValueError("Physical source Y captions require mode 1..3")
    if (isinstance(visible_height,bool)
            or not isinstance(visible_height,numbers.Real)
            or not math.isfinite(float(visible_height))
            or visible_height<=0):
        raise ValueError("Physical source Y height must be positive finite")
    if units is None:
        units={1:"м/с²",2:"мм/с",3:"мкм"}[int(mode)]
    if not isinstance(units,str) or len(units)>64 or any(ord(c)<32 for c in units):
        raise ValueError("Invalid original Y unit text")
    return f"{float(visible_height):.6g}".replace(".",",")+(" "+units if units else "")


# Stage111Z31CQ: extra screenshot-grounded LABEL and DATA-VIEW adaptation.
# The four source modes are Tag0=dB, Tag1=acceleration, Tag2=velocity,
# Tag3=displacement. Never infer an instrument sensor calibration here.
SPECTRUM_Y_UNITS=("дБ","м/с²","мм/с","мкм")


def source_spectrum_y_unit(mode:int)->str:
    if type(mode) is not int or mode not in range(4):
        raise ValueError("Original spectrum mode must be Tag0..3")
    return SPECTRUM_Y_UNITS[mode]


def source_derived_units(mode:int,units:str|None)->str|None:
    """007D1268..007D1355. 0042AA10 folds ASCII A-Z only."""
    if type(mode) is not int or mode not in range(4):
        raise ValueError("Original spectrum mode must be Tag0..3")
    if units is None:
        return None
    if not isinstance(units,str) or len(units)>64 or any(ord(c)<32 for c in units):
        raise ValueError("Invalid source FUnits")
    if mode in (0,1):
        return units
    ascii_fold=units.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"))
    if ascii_fold=="м/с2":
        return "мм/с" if mode==2 else "мкм"
    return "~"*(mode-1)+units


def source_spectrum_unit_contract(mode:int,units:str|None,*,source_bound:bool)->dict:
    derived=source_derived_units(mode,units)
    if source_bound:
        summary=derived if derived is not None else "ед. не подтверждены"
    else:
        summary=SPECTRUM_Y_UNITS[1 if mode==0 else mode]
    return {"source_derived_units":derived if source_bound else None,
            "source_summary_unit":summary,
            "source_unit_text_known":source_bound and derived is not None,
            "source_unit_bound":source_bound,
            "unit":"дБ" if mode==0 else summary}


def research_spectrum_vscale_auto_basis(peak:float)->float:
    """No FRange: LOCAL 1/2/5 peak-fit, source Tag3 = basis / 1000.

    Original GraphDefaultVScale is computed from channel FRange and NOT
    from the FFT peak. This explicitly local fallback must not be
    mistaken for physical device calibration or original Win32 scale.
    """
    if (isinstance(peak,bool) or not isinstance(peak,numbers.Real)
            or not math.isfinite(float(peak)) or float(peak)<0):
        raise ValueError("Local spectrum peak must be finite and nonnegative")
    target=max(float(peak),1e-12)*1000.*1.2
    if not math.isfinite(target) or target<=0:
        raise ValueError("Local Y fallback overflows")
    decade=10.**math.floor(math.log10(target))
    for step in (1.,2.,5.,10.):
        value=decade*step
        if value>=target*(1.-1e-12):
            if not math.isfinite(value) or value<=0:
                raise ValueError("Unrepresentable local Y fallback")
            return value
    raise ValueError("No finite local Y step")


def source_spectrum_h_available(axis_end_hz:float)->tuple[bool,...]:
    """All ten original Hz captions remain; only valid data widths enable.

    For a source FFT after decimation / lower Fs, Qt must not pan into an
    empty 25600 Hz band. This is explicitly an app data-viewport policy,
    not a claim of exact original Delphi bSpecHScale behavior.
    """
    if (isinstance(axis_end_hz,bool) or
            not isinstance(axis_end_hz,numbers.Real) or
            not math.isfinite(float(axis_end_hz)) or axis_end_hz<=0):
        raise ValueError("Spectrum plot needs a real positive X axis")
    limit=min(float(HORIZONTAL_HZ[0]),float(axis_end_hz))
    return tuple(float(hz)<=limit+1e-5 for hz in HORIZONTAL_HZ)
