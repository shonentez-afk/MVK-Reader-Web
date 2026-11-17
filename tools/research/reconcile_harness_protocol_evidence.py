#!/usr/bin/env python3
"""Review a third-party Ghidra protocol evidence JSON against verified MVKView IDR.

Read-only. No access to network, instruments, process memory, or original EXE.
The facts checked here were confirmed independently from operator-owned
Projects.7z/_Unit125.pas and mvk_idr(1).sqlite, with mvkview.idp metadata.
Do not turn this checker into a packet sender or publish private source files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_DISPATCH = {
    0x00000001: ("IDENTITY_DRAIN", "00808060..00808076"),
    0x00010FF0: ("OPERATION_ACK", "0080807B"),
    0x00010FFF: ("OPERATION_DENIED", "008080AC"),
    0xFF8001AC: ("TACH_DATA", "008080EB..00808339"),
    0xFF800ADC: ("ADC_DATA", "008080EB..00808339"),
    0xFF800C0D: ("PARAM_REGISTERS", "0080839E..00808718"),
}
WRONG_KINDS = {
    0x00000001: {"DATA_STREAM", "ADC_STREAM", "TACH_STREAM"},
    0x00010FF0: {"STATUS_CONFIG", "STREAM_STATUS"},
    0xFF8001AC: {"REPLY_A", "GENERIC_REPLY"},
    0xFF800ADC: {"REPLY_B", "GENERIC_REPLY"},
    0xFF800C0D: {"REPLY_CMD", "COMMAND_ACK"},
}


def review(evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("Evidence root must be an object")
    problems: list[dict[str, Any]] = []

    def issue(code: str, where: str, actual: Any, expected: str, address: str,
              severity: str = "source_conflict") -> None:
        problems.append({
            "code": code, "field": where, "reported": actual,
            "expected": expected, "source_address": address,
            "severity": severity,
        })

    proto = evidence.get("wire_protocol")
    if not isinstance(proto, dict):
        raise ValueError("Missing wire_protocol object")
    dispatch = proto.get("packet_type_dispatch", {})
    entries = dispatch.get("types", []) if isinstance(dispatch, dict) else []
    if not isinstance(entries, list):
        raise ValueError("Invalid packet type list")
    seen: dict[int, str] = {}
    for row in entries:
        if not isinstance(row, dict) or "type_hex" not in row:
            raise ValueError("Malformed packet type entry")
        try:
            kind = int(row["type_hex"], 16)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid packet type identifier") from exc
        if kind in seen:
            raise ValueError("Duplicate packet type in evidence")
        name = str(row.get("name_inferred", "")).upper()
        seen[kind] = name
        if kind in WRONG_KINDS and name in WRONG_KINDS[kind]:
            label, address = EXPECTED_DISPATCH[kind]
            issue(
                f"MISLABELED_{kind:08X}",
                f"wire_protocol.packet_type_dispatch.types[{kind:08X}].name_inferred",
                name, label, address,
            )
    missing = set(EXPECTED_DISPATCH) - set(seen)
    if missing:
        issue("PACKET_TYPES_INCOMPLETE", "wire_protocol.packet_type_dispatch.types",
              [f"{x:08X}" for x in sorted(missing)],
              "All six original dispatch IDs must be reviewed", "00808022..0080805B")

    cmd = proto.get("outgoing_command_frame", {})
    if not isinstance(cmd, dict):
        raise ValueError("Invalid outgoing command frame")
    words = cmd.get("words", [])
    if isinstance(words, list) and words:
        if len(words) != 8:
            issue("WRITER_HEADER_WORD_COUNT", "wire_protocol.outgoing_command_frame.words",
                  len(words),
                  "0080937C writes exactly 8 UInt32 values; 00807F52 writes a 9th Data word for queued commands",
                  "00809395..008093F5;00807F52")
        zeros = sum(isinstance(x, dict) and str(x.get("value", "")).strip()=="0"
                    for x in words)
        if zeros != 4:
            issue("WRITER_RESERVED_ZERO_COUNT", "wire_protocol.outgoing_command_frame.words",
                  zeros, "Exactly four zero-valued Write calls in 0080937C",
                  "008093B6;008093C1;008093CC;008093D7")
    claimed = cmd.get("min_frame_bytes")
    if claimed is not None and claimed != 32:
        issue("WRITER_FUNCTION_SIZE_CONFLATED", "wire_protocol.outgoing_command_frame.min_frame_bytes",
              claimed, "0080937C emits 32 bytes; the SetRate caller emits a further 4-byte data word (36 total)",
              "0080937C..008093FD;00807F52")

    flags = evidence.get("channel_processing", {}).get("write_flags", [])
    if isinstance(flags, list):
        for entry in flags:
            if not isinstance(entry, dict):
                continue
            value = str(entry.get("field", "")).upper()
            if "0X400E0" in value:
                issue("WRITEDATA_TIME_WRONG_OFFSET", "channel_processing.write_flags",
                      value, "WriteDataTime at TMVKThread+0x404E0 (not +0x400E0)",
                      "008061B2;0084E936")
            if "0X400E8" in value:
                issue("WRITEVALUES_TIME_WRONG_OFFSET", "channel_processing.write_flags",
                      value, "WriteValuesTime at TMVKThread+0x404E8",
                      "008061BF;0084E9B3")

    controls=evidence.get("dfm_measure_controls", [])
    if isinstance(controls, list):
        for entry in controls:
            if isinstance(entry, dict) and entry.get("handler")=="tmInterfaceUpdateTimer" and entry.get("flag_field"):
                issue("TIMER_BODY_CONFUSION", "dfm_measure_controls.tmInterfaceUpdateTimer.flag_field",
                      entry["flag_field"],
                      "0084F7C8 only calls 00847248 then RET; 0084F7D0 is a different function",
                      "0084F7C8..0084F7CD")

    sources = evidence.get("sources_used", {})
    if isinstance(sources, dict):
        archive=sources.get("projects_7z", {})
        if isinstance(archive, dict) and archive.get("used") is False:
            issue("ARCHIVE_NOT_EXAMINED", "sources_used.projects_7z.used", False,
                  "Evidence was not independently cross-checked against the extracted original Pascal/DFM",
                  "Projects.7z (_Unit125.pas, _Unit128.pas, mvkform.dfm)",
                  severity="provenance_gap")
    changes=evidence.get("changes_made", {})
    count_conflicts=sum(x["severity"]=="source_conflict" for x in problems)
    count_gaps=sum(x["severity"]=="provenance_gap" for x in problems)
    return {
        "schema": "MVK_HARNESS_PROTOCOL_SOURCE_REVIEW_V1",
        "input_registry_id": evidence.get("registry_id"),
        "review_status": "SOURCE_CONFLICTS" if count_conflicts else
            "PROVENANCE_GAPS" if count_gaps else "NO_KNOWN_SOURCE_CONFLICTS",
        "finding_count": len(problems),
        "source_conflict_count": count_conflicts,
        "provenance_gap_count": count_gaps,
        "conflicts": problems,
        "already_in_core": {
            "source_receive_emulator": "mvk_compatible/core/original_mode2_received_frames.py",
            "source_transmit_word_plan": "mvk_compatible/core/original_mode2_wire_word_candidate.py",
            "offline_exchange": "mvk_compatible/core/original_mode2_task2_exchange.py",
            "source_rate_fifo": "mvk_compatible/core/original_mode2_command_queue.py",
        },
        "report_made_core_changes": bool(changes.get("core_code_modified", False)) if isinstance(changes, dict) else False,
        "no_network_io_or_device_commands": True,
        "all_six_source_packet_roles": {f"0x{k:08X}": v[0] for k,v in EXPECTED_DISPATCH.items()},
        "notes": [
            "QueueCommand.Cmd=1, Addr=0x0E, Data=rate: 0x0E is Addr, not Cmd",
            "The 9th SetRate word is written by Execute at 00807F52, not inside 0080937C",
            "TYPE 1 drains UInt32 words; real ADC/TACH streams are 0xFF800ADC/0xFF8001AC",
            "0xFF800C0D incoming branch parses register blocks, not a generic ACK",
            "No claim of original hardware numerical or on-wire operational parity",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="local Harness evidence JSON")
    parser.add_argument("--output", type=Path, help="optional local review JSON path")
    args = parser.parse_args()
    raw = args.evidence.read_bytes()
    if len(raw) > 4_000_000:
        parser.error("Evidence file is too large")
    evidence = json.loads(raw)
    result = review(evidence)
    formatted = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(formatted, encoding="utf-8")
    print(formatted)
    return 2 if result["source_conflict_count"] else (1 if result["provenance_gap_count"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())