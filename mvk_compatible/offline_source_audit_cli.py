"""Stage111Z.22: local read-only inspection of original BIN/TSXML and FFT.

Examples:
  python -m mvk_compatible.offline_source_audit_cli inspect file.bin
  python -m mvk_compatible.offline_source_audit_cli verify-fft before.bin after.bin --fs 65536

No network, device calls, file writes, user filenames, raw signal samples or
private paths in JSON output. All processing is on local operator files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .core.direct_bin_session import (
    _bin_from_selection,_sidecar_for_bin,_checked_file,
    _MAX_BIN_BYTES,MAX_TSXML_BYTES,
)
from .core.original_tsxml_contract import (
    inspect_original_tsxml,ORIGINAL_TSXML_SOURCE
)
from .core.original_spectrum_independent_check import (
    compare_original_snapshot_pair,
)


def inspect_local_bin_sidecar(file:str | Path)->dict:
    """Metadata-only Byte/Single audit, without claiming physical calibration."""
    selected=Path(file).absolute()
    if selected.is_symlink() or not selected.is_file():
        raise ValueError("Требуется обычный локальный BIN/TSXML, не ссылка")
    binfile=_bin_from_selection(selected)
    sidecar=_sidecar_for_bin(binfile)
    meta_xml=_checked_file(sidecar,limit=MAX_TSXML_BYTES,what="TSXML")
    contract=inspect_original_tsxml(
        meta_xml,actual_bin_filename=binfile.name,max_data_bytes=_MAX_BIN_BYTES)
    raw=_checked_file(binfile,limit=_MAX_BIN_BYTES+4096,what="BIN")
    if contract.data_offset_bytes+contract.data_length_bytes!=len(raw):
        raise ValueError(
            "BIN/TSXML: DataOffset+DataLength не соответствуют файлу")
    if contract.data_type=="Single":
        samples=np.frombuffer(
            raw,dtype="<f4",
            offset=contract.data_offset_bytes,
            count=contract.data_length_bytes//4)
        if not bool(np.isfinite(samples).all()):
            raise ValueError("BIN содержит NaN/Inf")
        status="SINGLE_STRUCTURAL_CANDIDATE_CALIBRATION_UNVERIFIED"
    else:
        # Counter bytes are accepted for provenance-only inspection, never
        # recast into float32 or passed into GetSpectrum.
        status="BYTE_COUNTER_METADATA_ONLY_ACCELERATION_FFT_NOT_AVAILABLE"
    return {
        "status":status,
        "source":ORIGINAL_TSXML_SOURCE,
        "sample_count":contract.data_length_bytes//contract.sample_width_bytes,
        "bin_size_bytes":len(raw),
        "data_length_bytes":contract.data_length_bytes,
        "data_offset_bytes":contract.data_offset_bytes,
        "data_type":contract.data_type,
        "channel_number":contract.channel_number,
        "channel_frequency_hz":contract.sample_rate_hz,
        "units_from_tsxml_unverified":contract.channel_units_text,
        "original_writer_fields_complete":contract.source_meta_complete,
        "original_writer_offset_zero":contract.original_writer_offset_zero,
        "internal_channel_gain_single_from_tsxml":
            contract.internal_gain_single,
        "f_range_source_candidate_static_only":
            contract.original_f_range_single_candidate,
        "gain_loader_branch":contract.gain_loader_branch,
        "bin_sha256":hashlib.sha256(raw).hexdigest(),
        "tsxml_sha256":hashlib.sha256(meta_xml).hexdigest(),
        "physical_units_verified":False,
        "samples_scaled_by_this_inspection":False,
        "original_runtime_f_range_verified":False,
        "original_signal_spectrum_numeric_parity_verified":False,
        "file_names_and_paths_exposed":False,
        "contains_original_sample_data":False,
        "no_device_or_network_io":True,
    }


def main(argv:list[str] | None=None)->int:
    parser=argparse.ArgumentParser(
        prog="MVKView Compatible offline source audit",
        description="Read-only original BIN/TSXML or memory FFT snapshot QA")
    cmds=parser.add_subparsers(dest="cmd",required=True)
    original=cmds.add_parser("inspect",help="Inspect local BIN/TSXML metadata")
    original.add_argument("path")
    spectrum=cmds.add_parser(
        "verify-fft",help="Independently compare local pre-FFT/power snapshots")
    spectrum.add_argument("before_fft")
    spectrum.add_argument("after_power")
    spectrum.add_argument("--fs",type=int)
    args=parser.parse_args(argv)
    if args.cmd=="inspect":
        outcome=inspect_local_bin_sidecar(args.path)
    else:
        outcome=compare_original_snapshot_pair(
            args.before_fft,args.after_power,sample_rate_hz=args.fs)
    print(json.dumps(outcome,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
