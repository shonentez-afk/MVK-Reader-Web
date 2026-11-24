"""Replay ONLY close-time range/units, independently of latched live FRange.

Original 00806A8C / 00806F93 / 0080705E read configuration at channel
close. Source PARAM gate replay must establish frame order and Freeze.
No physical calibration, device writes or original binary parity claims.
"""
from __future__ import annotations
import math
import struct
from .original_get_value_text_30 import get_value_text_30

class CloseConfigReplay:
    def __init__(self):
        self.data=bytearray(0x8000)
        self.valid=bytearray(0x4000)

    def put(self,blocks):
        for addr,words,raw in blocks:
            if (type(addr) is not int or type(words) is not int or addr<0
                or words<=0 or addr+words>0x4000 or len(raw)!=words*2):
                raise ValueError("Source close config: malformed register block")
            self.data[addr*2:(addr+words)*2]=raw
            self.valid[addr:addr+words]=b"\x01"*words

    def read(self,addr,words):
        if all(self.valid[addr:addr+words]):
            return bytes(self.data[addr*2:(addr+words)*2])
        return None

    def snapshot(self,channel,frame):
        if type(channel) is not int or not 1<=channel<=10:
            raise ValueError("Source close config: invalid channel")
        out=dict(channel=channel,end_after_frame=frame,
                 source="VERIFIED_RAW_PARAM_FREEZE_REPLAY_AT_DATA_CLOSE",
                 gain=None,units=None,gain_raw_le=None,units_raw_le=None,
                 gain_origin="UNOBSERVED",units_origin="UNOBSERVED",
                 original_win32_calibration_verified=False)
        if channel>=9:
            return dict(out,gain=1.0,units="Count",gain_origin="TACH_FIXED",
                        units_origin="TACH_FIXED")
        addr=0x100*channel+0x0e
        raw=self.read(addr,2)
        units=self.read(addr+2,16)
        if raw is not None:
            value=struct.unpack("<f",raw)[0]
            out["gain_raw_le"]=raw.hex()
            if value==0:
                out.update(gain=1.0,gain_origin="REGISTER_ZERO_FALLBACK_ONE")
            elif math.isfinite(value) and value>0:
                out.update(gain=value,gain_origin="REGISTER_SINGLE_AT_CLOSE")
            else:
                out["gain_origin"]="INVALID_REGISTER_NO_XML_GAIN"
        if units is not None:
            out["units_raw_le"]=units.hex()
            result=get_value_text_30(9,units)
            if result.available:
                out.update(units=result.text,units_origin="REGISTER_ASCII_AT_CLOSE")
            else:
                out["units_origin"]="UNKNOWN_WIN32_ANSI_CODEPAGE"
        return out
