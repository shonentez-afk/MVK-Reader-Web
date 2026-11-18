"""Operator-selectable 1/1-, 1/3- and 2-octave local vibration filters.

Nominal centre labels are separate from exact calculation frequencies:
IEC 61260-1 (G=10**(3/10)) defines 1/1 and 1/3 band centres/edges.
These are application-side 4th-order zero-phase Butterworth passes, NOT
the proprietary original MVKView FIR bank and NOT an IEC-certified bank.
Two-octave bands are local presets, not claimed as IEC-class filters.
Native Go FRange/BIN, original AUX4700 and device commands are untouched.
"""
from __future__ import annotations

import math

from .original_dsp import _THIRD_HZ

FAMILIES=("octave","third_octave","double_octave")
NOMINAL_CENTRES={
    "octave":(1.,2.,4.,8.,16.,31.5,63.,125.,250.,500.,1000.,2000.,4000.,8000.),
    "third_octave":tuple(float(v) for v in _THIRD_HZ),
    "double_octave":(2.,8.,31.5,125.,500.,2000.,8000.),
}
FAMILY_LABELS={
    "octave":"1/1 октавы",
    "third_octave":"1/3 октавы",
    "double_octave":"2 октавы",
}

# 31 vendor MENU LABELS extracted from original MVKView IDP Unicode
# string pool; Pascal _Unit128.pas confirms popEnvelopeType has 32 items
# (index 0 is the localized off entry). These are NAMES/CENTRES only;
# the OEM filter coefficients and exact runtime processing are unknown.
_ORIGINAL_MENU_CENTRES=(
    ("third_octave",(25000,20000,16000,13000,10000,8000,6300,5000,
                     4000,3150,2500,2000,1600,1250,1000,800,630,500,400)),
    ("octave",(16000,8000,4000,2000,1000,500)),
    ("double_octave",(13000,6400,3200,1600,800,400)),
)

def _original_label(family:str,nominal:int)->str:
    prefix={"third_octave":"1/3окт","octave":"1окт",
            "double_octave":"2окт"}[family]
    amount=(f"{nominal//1000} кГц" if nominal>=10000
            else f"{nominal} Гц")
    return f"{prefix} {amount}"

ORIGINAL_MVK_MENU=(("Без фильтра","none",None),)+tuple(
    (_original_label(family,frequency),family,float(frequency))
    for family,centres in _ORIGINAL_MENU_CENTRES for frequency in centres
)

def nominal_centres(family:str)->tuple[float,...]:
    if family not in FAMILIES:
        raise ValueError("Неизвестная семья октавного фильтра")
    return NOMINAL_CENTRES[family]

def preset_band(family:str, nominal:float, fs:int|None=None)->tuple[float,float]:
    """Return actual physical half-power design edges, never a made-up Fs."""
    centres=nominal_centres(family)
    # Local extended families plus exactly verified ORIGINAL MENU centres.
    # No acceptance of arbitrary typed/nonexistent factory filter labels.
    original=dict(_ORIGINAL_MENU_CENTRES)[family]
    allowed=tuple(centres)+tuple(float(v) for v in original)
    if not isinstance(nominal,(int,float)) or not math.isfinite(nominal) or (
            not any(math.isclose(float(nominal),c,rel_tol=0,abs_tol=1e-7)
                    for c in allowed)):
        raise ValueError("Выберите центральную частоту из готового списка")
    ratio=10.**.3
    if family=="third_octave":
        index=round(3*math.log(float(nominal)/1000.,ratio))
        center=1000.*ratio**(index/3.)
        width=ratio**(1./6.)
    elif family=="octave":
        index=round(math.log(float(nominal)/1000.,ratio))
        center=1000.*ratio**index
        width=ratio**.5
    else:
        # Two-octave vendor NOMINAL labels include 400, 800, 1600,
        # 3200, 6400, 13k; not powers-of-four around 2000 Hz.
        # Use centre as a local engineering approximation only.
        center=float(nominal)
        width=ratio
    low,high=center/width,center*width
    if fs is not None:
        if type(fs) is not int or fs<2 or high>=fs/2:
            raise ValueError(
                f"Полоса {FAMILY_LABELS[family]} {nominal:g} Гц не помещается "
                f"в Nyquist выбранного АЦП (Fs={fs} Гц)")
    return low,high

def preset_description(family:str, nominal:float)->str:
    low,high=preset_band(family,nominal)
    return (f"{FAMILY_LABELS[family]} · {nominal:g} Гц "
            f"({low:.3g}–{high:.3g} Гц; локальный фильтр, не приборный FIR)")

def octave_rss_from_thirds(third_hz, third_rms):
    """APP_DERIVED RSS of three original 1/3-octave RMS cells; not device 1/1."""
    import numpy as np
    frequency=np.asarray(third_hz,dtype=np.float64)
    raw=np.asarray(third_rms,dtype=np.float64)
    if frequency.shape!=(43,) or raw.shape!=(43,):
        raise ValueError("Для сводных 1/1 нужны 43 исходные 1/3 полосы")
    centres=np.asarray(NOMINAL_CENTRES["octave"],dtype=np.float64)
    values=np.full(centres.shape,np.nan,dtype=np.float64)
    for i,nominal in enumerate(centres):
        matches=np.flatnonzero(np.isclose(frequency,nominal,atol=.001,rtol=0))
        if len(matches)!=1:continue
        index=int(matches[0])
        if index==0 or index+1>=len(raw):continue
        triple=raw[index-1:index+2]
        if np.all(np.isfinite(triple)) and np.all(triple>=0):
            values[i]=float(np.sqrt(np.sum(triple**2)))
    return centres,values
