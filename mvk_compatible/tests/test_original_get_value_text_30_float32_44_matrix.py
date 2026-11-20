"""44 reproducible bit-pattern guards for the *portable candidate* Float32.

Inputs cover signed zero, subnormals, max finite, infinity, NaN, decimal
rounding near the four-significant-digit cut and integer boundaries.
Independent Go candidate matched all of these plus 50,007 pseudo-random
binary32 values in a local analysis; NONE is an original Delphi/x87 oracle.
"""
from hashlib import sha256
import struct
from ..core.original_get_value_text_30 import get_value_text_30

_F32_BITS=(
    0x00000000,
    0x80000000,
    0x00000001,
    0x80000001,
    0x007fffff,
    0x00800000,
    0x80800000,
    0x3dcccccd,
    0xbdcccccd,
    0x3f800000,
    0xbf800000,
    0x3fc00000,
    0x40200000,
    0x7f7fffff,
    0xff7fffff,
    0x7f800000,
    0xff800000,
    0x7fc00000,
    0xffc00000,
    0x3f000000,
    0x3eaaaaab,
    0x42f70000,
    0x447a0000,
    0x44fa0000,
    0x45000000,
    0x461c4000,
    0x477fe000,
    0x3a83126f,
    0x3935bdc6,
    0x1cb3d9b5,
    0x5f3759df,
    0x2c3d4e5f,
    0x7e4fffff,
    0xf74fffff,
    0x3f7fffff,
    0x3f800001,
    0x447a0001,
    0x4479ffff,
    0x4c000000,
    0x4bfffffe,
    0x4d800000,
    0x4d7fffff,
    0x80000002,
    0x47c35000,
)
_EXPECTED_SHA256="2d473a0bef28878044163499021c74571d5072c62dc3fc839c447268b9ca31f2"


def test_source_float32_44_fixed_ieee_vectors_stable_candidate_not_delphi():
    rendered=[]
    for bits in _F32_BITS:
        source=get_value_text_30(0,struct.pack("<I",bits))
        assert source.source_case==1
        assert not source.original_win32_delphi_text_verified
        rendered.append(f"{bits:08x}:{source.text}\n")
    assert len(rendered)==44
    assert sha256("".join(rendered).encode("utf-8")).hexdigest()==_EXPECTED_SHA256
