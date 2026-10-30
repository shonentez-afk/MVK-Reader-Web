"""Stage111Z.4: private, read-only identity audit for original FFT rounding.

Accepts only the operator's local IDR project. The original binary, Delphi
source, original measured samples and filesystem path never leave the device.
Outputs only small source-derived invariants and fail-closed booleans.
No original code bytes are embedded here, only SHA256 digests and instruction
classes. Static audit does NOT attest exact Delphi numerical FFT output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from .private_original_cw_idr_audit import (
    _read_at_va,
    _sections,
    audit_original_static_cw,
)

SOURCE="PRIVATE_MVKVIEW_FFT_X87_SINGLE_STORE_AUDIT_V1"

# Original .text windows, verified against private local mvkview.idp.
WINDOWS={
    "fft_forward_wrapper": (0x007CC3F8,0x007CC403,
        "e46cfb486767a74d5ebb080c38d9168dda3a79f00d31249fee02f0bbc18d2764"),
    "fft_reverse_wrapper": (0x007CC404,0x007CC414,
        "5b3df9746e9eabb21a31bc29b2a95b03c7841eed24ffebf0be3c3c5842390886"),
    "twiddle_recurrence": (0x007CC316,0x007CC348,
        "b00491401432fbf2581e179089f041629c60a6cc1f257e8aca884d562544d7de"),
    "butterfly_kernel": (0x007CC22D,0x007CC37F,
        "37bacbffd6d651561e7686519f75742f75de32286f1dc44d9e41e7ece0e05f01"),
    "spectrum_fft_call_and_power": (0x007D2083,0x007D20B6,
        "2f6dd3faffee9076bd2abc79f89258e11ed96a092987800a417f1476b9a4355f"),
    "spectrum_window_multiply": (0x007D205A,0x007D2080,
        "8e4f62dd8c7c67d652ef725133160001cbbf96cf8bcc2565dace6b2c8bfb0f5d"),
    "dc_center_single": (0x007D2344,0x007D2397,
        "9b16d9a87d26b292797378998adb7b9388a68cbc42383a8c36f83bed34b3b1e9"),
}


def _verify_source_window(data:bytes, start:int, stop:int,
                          expected_sha256:str)->None:
    if not isinstance(data,bytes) or stop<=start or len(data)!=stop-start:
        raise ValueError("Invalid original FFT source range")
    if hashlib.sha256(data).hexdigest()!=expected_sha256:
        raise ValueError("Original FFT source bytes differ from verified baseline")


def _read_original_text(src, sections, start:int, stop:int)->bytes:
    length=stop-start
    if length<=0 or length>16384:
        raise ValueError("Refusing unbounded FFT source extraction")
    if length<=128:
        return _read_at_va(src, sections, start, length, ".text")
    matching=next((s for s in sections if
                    s.name==".text" and s.va<=start and stop<=s.va+s.size),None)
    if matching is None:
        raise ValueError("FFT source outside original text")
    src.seek(matching.raw_offset+start-matching.va)
    data=src.read(length)
    if len(data)!=length:
        raise ValueError("Truncated original FFT source")
    return data


def _verified_fft_semantics(windows:dict[str,bytes])->dict:
    """Minimal independent structural checks, beyond whole-window SHA."""
    positive=windows["fft_forward_wrapper"]
    negative=windows["fft_reverse_wrapper"]
    stages=windows["twiddle_recurrence"]
    window=windows["spectrum_window_multiply"]
    graph=windows["spectrum_fft_call_and_power"]
    mean=windows["dc_center_single"]
    # 007CC3F8: push Single(+2pi), 007CC404: push Single(-2pi).
    plus_2pi=struct.unpack("<f",positive[1:5])[0]
    minus_2pi=struct.unpack("<f",negative[5:9])[0]
    if not (positive[0]==0x68 and negative[4]==0x68 and
            plus_2pi>6.28 and plus_2pi<6.29 and
            minus_2pi == -plus_2pi):
        raise ValueError("Original FFT angle wrappers not verified")
    # 007D2083 call points specifically to 007CC3F8 positive wrapper.
    call_address=0x007D2083
    if graph[:1]!=b"\xE8":
        raise ValueError("Original spectrum FFT call changed")
    target=call_address+5+struct.unpack_from("<i",graph,1)[0]
    if target!=0x007CC3F8:
        raise ValueError("Spectrum unexpectedly uses different FFT wrapper")
    # 007CC325 temp-real is FSTP Single. Imag expression stays in x87
    # until subtraction from wi; only then its output is FSTP Single.
    # new wi 007CC33A; new wr 007CC344.
    if not (stages[0xF:0x12] == b"\xD9\x5D\xE8" and
            stages[0x24:0x27] == b"\xD9\x5D\xD0" and
            stages[0x2E:0x31] == b"\xD9\x5D\xD4"):
        raise ValueError("FFT twiddle Single-store sequence changed")
    # 007D2062 FLD f32; FMUL stored periodic Hann table; FSTP Single;
    # imaginary input of each complex FFT datum starts at zero.
    if (b"\xD9\x04\x83" not in window or
            b"\xD8\x0C\xB5" not in window or
            b"\xD9\x1C\xC1" not in window):
        raise ValueError("Original FFT window source missing")
    if (b"\xD9\x1C\x24" not in mean or
            b"\xD9\x1C\x82" not in mean):
        raise ValueError("Mean or mean-subtraction Single store missing")
    return {
        "source_positive_angle_forward_fft_verified": True,
        "source_negative_angle_fft_wrapper_is_separate": True,
        "source_x87_twiddle_real_intermediate_single_store_verified": True,
        "source_x87_twiddle_imag_intermediate_remains_extended": True,
        "source_x87_twiddle_final_real_and_imag_single_stores_verified": True,
        "source_f32_hann_window_multiplication_verified": True,
        "source_f32_dc_running_mean_and_subtraction_verified": True,
    }


def audit_original_fft_rounding(path:str|Path)->dict:
    base=audit_original_static_cw(path)
    source_path=Path(path)
    with source_path.open("rb") as f:
        sections=_sections(f,source_path.stat().st_size)
        decoded={}
        for name,(start,stop,digest) in WINDOWS.items():
            raw=_read_original_text(f,sections,start,stop)
            _verify_source_window(raw,start,stop,digest)
            decoded[name]=raw
        facts=_verified_fft_semantics(decoded)
    return {
        "source":SOURCE,
        "original_fft_code_windows_authenticated":len(WINDOWS),
        **facts,
        "original_static_initial_x87_cw_hex":base["original_static_fpu_cw_hex"],
        "original_fft_runtime_numeric_parity_verified":False,
        "original_runtime_hann_table_bits_verified":False,
        "original_delphi_fft_phase_and_amplitude_parity_verified":False,
        "original_private_code_paths_or_samples_in_report":False,
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description="Offline original FFT rounding audit")
    parser.add_argument("private_idp",help="Local original IDR project (private)")
    args=parser.parse_args(argv)
    try:
        result=audit_original_fft_rounding(args.private_idp)
    except (OSError,ValueError,TypeError,struct.error):
        parser.exit(2,"Original FFT source cannot be authenticated; private content withheld\n")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
