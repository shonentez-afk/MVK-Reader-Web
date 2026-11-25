"""Independent single-socket physical WriteData replay, not a Win32 oracle.
The first nonempty PARAM descriptor latches FRange; close Gain is separate.
"""
from __future__ import annotations
import math
import struct
import numpy as np
from .original_mode2_close_metadata import CloseConfigReplay

PHYSICAL_SCHEMA="MVK_SOURCE_LIVE_ADC_PHYSICAL_V1"

class PhysicalWriteReplay:
    def __init__(self):
        self.config=CloseConfigReplay()
        self.ranges=(1.0,)*8
        self.latched=False

    def on_param(self,blocks,frozen):
        for block in blocks:
            if not frozen:
                self.config.put([block])
            if not self.latched:
                result=[]
                for ch in range(1,9):
                    raw=self.config.read(ch*0x100+0x0e,2)
                    if raw is None:
                        result.append(None)
                        continue
                    value=struct.unpack("<f",raw)[0]
                    result.append(1.0 if value==0 else value
                                  if math.isfinite(value) and value>0 else None)
                self.ranges=tuple(result)
                self.latched=True

    def chunk(self,channel,payload):
        if not 1<=channel<=8 or len(payload)%4:
            raise ValueError("Source physical WriteData: invalid ADC chunk")
        scale=self.ranges[channel-1]
        if scale is None:
            return None
        values=np.frombuffer(payload,dtype="<f4")
        if not np.isfinite(values).all():
            return None
        if scale==1.0:
            return payload
        with np.errstate(over="ignore",invalid="ignore",under="ignore"):
            out=(values.astype(np.float64)*scale).astype("<f4")
        return out.tobytes() if np.isfinite(out).all() else None
