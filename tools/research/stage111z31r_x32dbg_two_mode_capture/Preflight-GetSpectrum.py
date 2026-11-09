#!/usr/bin/env python3
"""Offline, read-only GetSpectrum EIP=007D14AA preflight.

Consumes *raw binary* snapshots saved by a local MCP controller. Never starts,
connects to, resumes or modifies x32dbg/MVKView. No network or dependencies.
Does NOT independently authenticate that the MCP snapshots came from one run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import tempfile

EXPECTED_EIP = 0x007D14AA
PARAMS_SIZE = 0x3C
STORAGE_SIZE = 0x38
LOCALS_SIZE = 0x30

class CaptureError(Exception):
    pass

def u32(buf: bytes, at: int) -> int:
    return struct.unpack_from("<I", buf, at)[0]

def f32(buf: bytes, at: int) -> float:
    return struct.unpack_from("<f", buf, at)[0]

def load_exact(root: Path, filename: str, length: int) -> bytes:
    data = (root / filename).read_bytes()
    if len(data) != length:
        raise CaptureError(f"{filename}: expected {length} bytes, got {len(data)}")
    return data

def hexnum(value: object, name: str) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError("boolean")
        return int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as exc:
        raise CaptureError(f"session_at_14AA.json: invalid {name}: {value!r}") from exc

def must(condition: bool, msg: str) -> None:
    if not condition:
        raise CaptureError(msg)

def validate(root: Path) -> dict:
    params = load_exact(root, "params_at_14AA.bin", PARAMS_SIZE)
    verify = load_exact(root, "params_recheck_10_2f.bin", 0x20)
    storage_ptr_raw = load_exact(root, "storage_ptr_at_14AA.bin", 4)
    storage = load_exact(root, "storage_at_14AA.bin", STORAGE_SIZE)
    locals_ = load_exact(root, "locals_at_14AA.bin", LOCALS_SIZE)
    meta = json.loads((root / "session_at_14AA.json").read_text(encoding="utf-8"))
    must(isinstance(meta, dict), "session metadata must be an object")

    must(str(meta.get("state", "")).lower() == "paused", "debugger is not paused")
    eip = hexnum(meta.get("eip"), "eip")
    ebx = hexnum(meta.get("ebx"), "ebx")
    ebp = hexnum(meta.get("ebp"), "ebp")
    pid = hexnum(meta.get("pid"), "pid")
    tid = hexnum(meta.get("tid"), "tid")
    must(eip == EXPECTED_EIP, f"EIP=0x{eip:08X}, expected 0x{EXPECTED_EIP:08X}")
    must(0 < ebx < 2**32 and 0 < ebp < 2**32, "invalid EBX/EBP")
    must(pid > 0 and tid > 0, "invalid PID/TID")
    must(params[0x10:0x30] == verify,
         "second MCP read of EBX+0x10..0x2F differs from the first read")

    storage_ptr = u32(storage_ptr_raw, 0)
    must(storage_ptr == u32(locals_, 0x2C),
         "Storage ptr [EBP-4] differs between independent stack reads")
    must(storage_ptr != 0, "Storage pointer is NULL")
    work_ptr = u32(locals_, 0x04)  # [EBP-2C]
    y_ptr = u32(locals_, 0x00)     # [EBP-30] (may not be final Y yet)
    ring_ptr = u32(storage, 0x34)
    must(work_ptr != 0 and ring_ptr != 0, "work/ring pointer is NULL")

    n = u32(params, 0x04)
    envelope = u32(params, 0x08)
    mode = u32(params, 0x18)
    end = u32(params, 0x20)
    end_hi = u32(params, 0x24)
    output_fs = u32(params, 0x2C)
    raw_fs = u32(storage, 0x18)
    data_type = u32(storage, 0x0C)
    capacity = u32(storage, 0x10)
    mask = u32(storage, 0x14)
    write_pos = u32(storage, 0x20)
    write_hi = u32(storage, 0x24)
    oldest = u32(storage, 0x28)
    oldest_hi = u32(storage, 0x2C)
    frange = f32(storage, 0x04)

    must(mode in (0, 1, 2, 3),
         f"BLOCK_MODE: DWORD[EBX+0x18]=0x{mode:08X} ({mode}); "
         "expected 0..3; do not guess offsets or start capture")
    must(envelope in (0, 20), f"BLOCK_FILTER: EnvelopeCode={envelope}; current capture supports only 0/20")
    must(4096 <= n <= 262144 and (n & (n - 1)) == 0,
         f"BLOCK_N: FFT N={n} invalid for current 2-mode capture")
    must(data_type == 0, f"BLOCK_TYPE: FAdcDataType={data_type} != Float32 type 0")
    must(capacity >= n and capacity <= 0x800000 and (capacity & (capacity - 1)) == 0,
         f"BLOCK_RING: ring sample capacity={capacity} invalid")
    must(mask == capacity - 1,
         f"BLOCK_RING: ring mask={mask} != capacity-1={capacity-1}")
    must(raw_fs == 65536, f"BLOCK_FS: raw Fs={raw_fs}; expected 65536 Hz for current archive")
    must(output_fs > 0, "BLOCK_FS: output Fs is zero")
    must(math.isfinite(frange) and frange > 0.0, "BLOCK_FRANGE: invalid FRange Float32")
    must(end_hi == 0 and write_hi == 0 and oldest_hi == 0,
         "BLOCK_HISTORY: high-word source indices must be zero in current capture")
    must(n <= end <= write_pos,
         f"BLOCK_HISTORY: require N<=end<=write_pos, got {n}<={end}<={write_pos}")
    must(end - n >= oldest, f"BLOCK_HISTORY: missing raw history, start={end-n} oldest={oldest}")

    names = ["params_at_14AA.bin", "params_recheck_10_2f.bin",
             "storage_ptr_at_14AA.bin", "storage_at_14AA.bin", "locals_at_14AA.bin"]
    arrays = [params, verify, storage_ptr_raw, storage, locals_]
    return {
        "status": "STRUCTURAL_PREFLIGHT_PASS_NOT_RUNTIME_ATTESTATION",
        "warning": "Does not verify memory-region permissions, opcode anchors, cross-stop TID/EBX/EBP, or original-to-BIN identity",
        "session_agent_report": {"pid": pid, "tid": tid, "eip": f"0x{eip:08X}",
                                 "ebx": f"0x{ebx:08X}", "ebp": f"0x{ebp:08X}"},
        "fields": {"fft_n_samples": n, "fft_half_bins": n//2,
                   "envelope_code": envelope, "spectrum_mode": mode,
                   "window_end_index": end, "window_start_index": end-n,
                   "output_fs_hz_at_stop": output_fs, "raw_fs_hz": raw_fs,
                   "f_range_float32": frange, "f_range_bits": f"0x{u32(storage, 4):08X}",
                   "adc_type": data_type, "ring_capacity_samples": capacity,
                   "ring_capacity_bytes": capacity*4, "ring_mask": mask,
                   "storage_ptr": f"0x{storage_ptr:08X}",
                   "ring_ptr": f"0x{ring_ptr:08X}",
                   "work_ptr": f"0x{work_ptr:08X}",
                   "stack_local_ebp_minus_30": f"0x{y_ptr:08X}"},
        "params_offsets": {
            f"+0x{k:02X}": {"raw_hex": params[k:k+4].hex(" ").upper(),
                          "le_u32": u32(params, k)}
            for k in (0x04, 0x08, 0x18, 0x20, 0x2C)
        },
        "files_sha256": {name: hashlib.sha256(data).hexdigest()
                         for name, data in zip(names, arrays)}
    }

def self_test() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        p = bytearray(PARAMS_SIZE)
        s = bytearray(STORAGE_SIZE)
        stack = bytearray(LOCALS_SIZE)
        def w32(buf: bytearray, at: int, value: int) -> None:
            struct.pack_into("<I", buf, at, value)
        for off, val in ((4,262144),(8,0),(0x18,2),(0x20,294912),(0x2C,65536)):
            w32(p,off,val)
        for off, val in ((0x0C,0),(0x10,2097152),(0x14,2097151),
                         (0x18,65536),(0x20,294912),(0x28,32768),(0x34,0x7E620010)):
            w32(s,off,val)
        w32(s,4,0x43FF4853)
        w32(stack,4,0x7E510010)
        w32(stack,0x2C,0x02B28850)
        (root/"session_at_14AA.json").write_text(json.dumps({
            "state":"paused","eip":"0x007D14AA","ebx":"0x02A40E58",
            "ebp":"0x0019F270","pid":1856,"tid":1234}),encoding="utf-8")
        def save() -> None:
            (root/"params_at_14AA.bin").write_bytes(p)
            (root/"params_recheck_10_2f.bin").write_bytes(p[0x10:0x30])
            (root/"storage_ptr_at_14AA.bin").write_bytes(struct.pack("<I",0x02B28850))
            (root/"storage_at_14AA.bin").write_bytes(s)
            (root/"locals_at_14AA.bin").write_bytes(stack)
        save()
        assert validate(root)["fields"]["fft_half_bins"]==131072
        w32(p,0x18,0x00048000)
        save()
        try: validate(root)
        except CaptureError as e: assert "BLOCK_MODE" in str(e)
        else: raise AssertionError("invalid mode accepted")
        w32(p,0x18,2)
        w32(s,0x10,8192)
        save()
        try: validate(root)
        except CaptureError as e: assert "BLOCK_RING" in str(e)
        else: raise AssertionError("wrong ring size accepted")
        w32(s,0x10,2097152)
        save()
        (root/"params_recheck_10_2f.bin").write_bytes(b"\x00"*32)
        try: validate(root)
        except CaptureError as e: assert "second MCP read" in str(e)
        else: raise AssertionError("inconsistent second read accepted")
    print("SELF_TEST_PASS: valid fixture + invalid mode + invalid ring + inconsistent reread (4/4)")

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", nargs="?", type=Path,
                    help="local folder with five raw MCP snapshots + session_at_14AA.json")
    ap.add_argument("--self-test", action="store_true", help="offline deterministic synthetic QA")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.folder is None:
        ap.error("folder is required unless --self-test")
    try:
        result = validate(args.folder)
    except (CaptureError, OSError, ValueError, struct.error, json.JSONDecodeError) as exc:
        print(json.dumps({"status":"BLOCK", "reason":str(exc)},ensure_ascii=False,indent=2))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    sys.exit(main())
