"""Read ONLY the original calculated AUX4700 fields transmitted by MVK01.

Go's accepted AUX4700 decode for EACH of 8 ADCs has:
- third_octave_acceleration_rms: 43 float32, centres 0.63..10000 Hz,
  register offsets base+0x02+2*i;
- band_rms: 24 float32, base+0x60+2*i;
- band_peak_equiv: 24 float32, base+0xA0+2*i;
- band_span_equiv: 24 float32, base+0xE0+2*i.

"Equiv" is intentionally preserved: original sources have NOT established
the physical units, filter ranges or user-facing labels for all 24 slots.
Never manufacture a 24-slot frequency axis or copy APP_DERIVED features
into vendor DSP. None/null means unavailable, never zero.

AUX4700 is device-calculated data, not the local GUI FFT / Welch PSD.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np

_THIRD_HZ = np.asarray((
    .63,.8,1.,1.25,1.6,2.,2.5,3.15,4.,5.,6.3,8.,
    10.,12.5,16.,20.,25.,31.5,40.,50.,63.,80.,
    100.,125.,160.,200.,250.,315.,400.,500.,
    630.,800.,1000.,1250.,1600.,2000.,2500.,
    3150.,4000.,5000.,6300.,8000.,10000.,
), dtype=np.float64)

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
    # All three 24-slot arrays are supplied by the same instrument frame.
    # If any are absent, this is a legacy 43-band-only status, NOT zero data.
    band_rms: np.ndarray | None = None
    band_peak_equiv: np.ndarray | None = None
    band_span_equiv: np.ndarray | None = None
    not_ready: tuple[str, ...] = ()

    @property
    def has_extended(self) -> bool:
        return all(v is not None for v in (
            self.band_rms,self.band_peak_equiv,self.band_span_equiv))

    @property
    def total_transmitted_cells(self) -> int:
        return 115 if self.has_extended else 43


def _real_or_unavailable(values: list, length: int, label: str) -> np.ndarray:
    if not isinstance(values,list) or len(values)!=length:
        raise ValueError(f"Original AUX4700 {label}: expected {length} transmitted cells")
    clean=[]
    for v in values:
        if v is None:
            clean.append(np.nan)
        elif type(v) in (int,float) and np.isfinite(v):
            clean.append(float(v))
        else:
            raise ValueError(f"Original AUX4700 {label}: bad cell type")
    return np.asarray(clean,dtype=np.float64)


def read_original_dsp_bands(status: dict, adc: int) -> OriginalDSPBands | None:
    if type(adc) is not int or not 1<=adc<=8:
        raise ValueError("Invalid ADC")
    if not isinstance(status,dict):
        raise ValueError("Original AUX4700 status must be validated mapping")
    records=status.get("dsp_original_aux4700_channels")
    if records is None:
        return None
    if not isinstance(records,list) or len(records)>8:
        raise ValueError("Malformed original AUX4700 channels")
    total=status.get("aux4700_updates",0)
    if type(total) is not int or total<=0:
        raise ValueError("Original AUX values without a real update tick")
    matching=[p for p in records if isinstance(p,dict) and p.get("adc")==adc]
    if not matching:
        return None
    if len(matching)!=1:
        raise ValueError("Duplicated original DSP ADC")
    row=matching[0]
    f=_real_or_unavailable(row.get("third_octave_hz"),43,"frequency_hz")
    y=_real_or_unavailable(row.get("third_octave_acceleration_rms"),43,
                           "third_octave_acceleration_rms")
    if not np.array_equal(f,_THIRD_HZ):
        raise ValueError("Original AUX4700 43 band centres do not match decoder")

    fields=row.get("nonfinite_fields")
    if type(fields) is not int or not 0<=fields<=115:
        raise ValueError("Bad original DSP nonfinite count")
    if (type(row.get("update")) is not int or
        not 0<row["update"]<=total or
        not isinstance(row.get("status_hex"),str) or
        re.fullmatch(r"0x[0-9A-F]{8}",row["status_hex"]) is None or
        not isinstance(row.get("time_utc"),str) or
        not row["time_utc"]):
        raise ValueError("Unverified original DSP metadata")

    keys=("band_rms","band_peak_equiv","band_span_equiv")
    present=[key in row for key in keys]
    if any(present) and not all(present):
        raise ValueError("Partial original 24-slot RMS/Peak/Span fields")
    raw=[_real_or_unavailable(row[key],24,key) for key in keys] if all(present) else [None]*3
    unavailable=int(np.count_nonzero(np.isnan(y)))
    if all(present):
        unavailable+=sum(int(np.count_nonzero(np.isnan(a))) for a in raw)
        if fields!=unavailable:
            raise ValueError("Original DSP nonfinite count inconsistent across 115 cells")
    elif fields<unavailable:
        raise ValueError("DSP nonfinite count inconsistent")

    nr=row.get("not_ready",{})
    if not isinstance(nr,dict) or any(
        k not in ("fs16","fs64","fs512") or type(v) is not bool
        for k,v in nr.items()
    ):
        raise ValueError("Malformed original DSP not_ready flags")
    pending=tuple(k for k in ("fs16","fs64","fs512") if nr.get(k) is True)
    return OriginalDSPBands(adc,f,y,row["update"],row["status_hex"],
                            row["time_utc"],fields,band_rms=raw[0],
                            band_peak_equiv=raw[1],
                            band_span_equiv=raw[2],not_ready=pending)
