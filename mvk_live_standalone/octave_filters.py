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

def nominal_centres(family:str)->tuple[float,...]:
    if family not in FAMILIES:
        raise ValueError("Неизвестная семья октавного фильтра")
    return NOMINAL_CENTRES[family]

def preset_band(family:str, nominal:float, fs:int|None=None)->tuple[float,float]:
    """Return actual physical half-power design edges, never a made-up Fs."""
    centres=nominal_centres(family)
    if not isinstance(nominal,(int,float)) or not math.isfinite(nominal) or (
            not any(math.isclose(float(nominal),c,rel_tol=0,abs_tol=1e-7)
                    for c in centres)):
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
        index=round(.5*math.log(float(nominal)/2000.,ratio))
        center=2000.*ratio**(2*index)
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
