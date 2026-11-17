"""Read-only provenance and validation for MVK01 original AUX4700 DSP bands.

Original 43 third-octave acceleration RMS cells are calculated by the MVK
instrument (AUX4700), not reconstructed from locally sampled ADC Float32.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math

import numpy as np

@dataclass(frozen=True)
class OriginalDSPBands:
    adc: int
    frequency_hz: np.ndarray
    acceleration_rms: np.ndarray
    update: int
    status_hex: str
    time_utc: str
    nonfinite_fields: int
    source: str = "MVK_DSP_ORIGINAL_AUX4700"


def read_original_dsp_bands(status: dict, adc: int) -> OriginalDSPBands | None:
    if type(adc) is not int or not 1<=adc<=8:
        raise ValueError("Invalid ADC")
    records=status.get("dsp_original_aux4700_channels")
    if records is None:
        return None
    if not isinstance(records,list) or len(records)>8:
        raise ValueError("Malformed original AUX4700 channels")
    if status.get("aux4700_updates",0)==0:
        raise ValueError("Original AUX values without a real update tick")
    matching=[p for p in records if isinstance(p,dict) and p.get("adc")==adc]
    if not matching:
        return None
    if len(matching)!=1:
        raise ValueError("Duplicated original DSP ADC")
    row=matching[0]
    freqs=row.get("third_octave_hz")
    values=row.get("third_octave_acceleration_rms")
    if not isinstance(freqs,list) or not isinstance(values,list) or len(freqs)!=43 or len(values)!=43:
        raise ValueError("Wrong original 43-band DSP shape")
    f=np.asarray(freqs,dtype=float)
    y=np.array([float(v) if type(v) in (int,float) and np.isfinite(v)
                else np.nan for v in values],dtype=float)
    if not np.isfinite(f).all() or np.any(f<=0) or np.any(np.diff(f)<=0):
        raise ValueError("Bad original band frequencies")
    if (type(row.get("update")) is not int or
        not 0<row["update"]<=status["aux4700_updates"] or
        not isinstance(row.get("status_hex"),str) or
        not row["status_hex"].startswith("0x") or
        len(row["status_hex"])!=10 or
        not isinstance(row.get("time_utc"),str)):
        raise ValueError("Unverified original DSP metadata")
    fields=row.get("nonfinite_fields")
    if type(fields) is not int or fields<0:
        raise ValueError("Bad original DSP nonfinite count")
    if fields<np.isnan(y).sum():
        raise ValueError("DSP nonfinite count inconsistent")
    return OriginalDSPBands(adc,f,y,row["update"],row["status_hex"],
                            row["time_utc"],fields)
