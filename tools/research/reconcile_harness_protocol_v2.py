#!/usr/bin/env python3
"""Read-only audit of Harness MVK_PROTOCOL_EVIDENCE_V2.json against original code.

Source provenance: operator-supplied original mvkview.idp header checksum,
Projects.7z/_Unit125.pas and mvk_idr(1).sqlite metadata. No original source
or instrument data is stored in this file. The validator is a regression
alert, not a live decompiler or packet parser.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any

CORRECT_TYPES = {
    0x00000001: "DRAIN_UINT32", 0x00010FF0: "OPERATION_SUCCESS",
    0x00010FFF: "OPERATION_DENIED", 0xFF8001AC: "TACH_DATA",
    0xFF800ADC: "ADC_DATA", 0xFF800C0D: "PARAM_REGISTER_BLOCKS",
}
KNOWN_MODULES = (
    "mvk_compatible/core/original_mode2_received_frames.py",
    "mvk_compatible/core/original_mode2_status_cells.py",
    "mvk_compatible/core/original_mode2_command_queue.py",
    "mvk_compatible/core/original_mode2_wire_word_candidate.py",
    "mvk_compatible/core/original_mode2_task2_exchange.py",
)


def review(evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("Expected JSON object")
    if evidence.get("registry_id") != "mvk_protocol_evidence_v2":
        raise ValueError("Expected mvk_protocol_evidence_v2")
    findings: list[dict[str, Any]] = []
    def note(code: str, field: str, actual: Any, correction: str,
             source: str, kind: str="SOURCE_CONFLICT"):
        findings.append({"code":code,"field":field,"reported":actual,
                         "correction":correction,"source":source,"category":kind})

    fr=evidence.get("data_stream_frame",{})
    if fr.get("packet_type")==1:
        note("TYPE1_NOT_SAMPLES","data_stream_frame.packet_type",1,
             "0x00000001 drains remaining UInt32; 0xFF800ADC ADC and 0xFF8001AC TACH enter 0080816B",
             "_Unit125.pas:00808022-00808076,008080EB-0080816B")
    if fr.get("tach_branch_not_disassembled",{}).get("target")=="00808339":
        note("CHANNEL10_INVALID_NOT_TACH","data_stream_frame.tach_branch_not_disassembled",
             fr["tach_branch_not_disassembled"],
             "00808339 raises errInvalidPacket for channel>=10; TACH indices are 8/9, see 00808251",
             "_Unit125.pas:008081AA-008081AE,00808251,00808339-00808394")

    ch=evidence.get("data_stream_processing",{})
    if "channel_activation" in ch:
        note("CHANNEL0_WRITEDATA_STAGE","data_stream_processing.channel_activation",
             ch["channel_activation"].get("claim"),
             "Field thread+0x40 is WriteDataStage; channel 0 makes recording 0->1, not connection readiness",
             "_Unit125.pas:00808291-008082AA",kind="SEMANTIC_QUALIFIER")

    desc=evidence.get("descriptor_loop",{})
    meaning=str(desc.get("semantics", ""))
    if desc.get("count")==14 and ("8 ADC" in meaning or "8+2+4" in meaning):
        note("14_STATUSCELLS_NOT_DESCRIPTORS","descriptor_loop.semantics",meaning,
             "Loop updates fourteen StatusCells (indices 0..13) for EACH received register block, not fourteen packet descriptors",
             "_Unit125.pas:00805D08-00805ECA,0080857C-0080859A; data 008D3068")

    trigger=evidence.get("trigger_0x3100",{})
    tmeaning=str(trigger.get("meaning_inferred", ""))
    if any(v in tmeaning for v in ("переключатель состояния", "завершение передачи параметров", "Stage")):
        note("REGISTER3100_NOT_STAGE_TRIGGER","trigger_0x3100.meaning_inferred",tmeaning,
             "0x3100 triggers a VALUES-CSV row only when ValuesFile exists and two tach state comparisons; Stage0->1 uses 00808617",
             "_Unit125.pas:008085A5-008085DD,008066F0,00808617")
    acts=trigger.get("on_match",[])
    if any("цикл команд" in str(x.get("action", "")) for x in acts if isinstance(x,dict)):
        note("00806030_NOT_COMMAND_LOOP","trigger_0x3100.on_match",acts,
             "00806030 compares/updates two tach states in the register image (no QueueCommand or Write)",
             "_Unit125.pas:00806030-008060AB,008085C2-008085DD")

    mechanisms=evidence.get("four_mechanisms_distinguished",{}).get("items",[])
    for i,item in enumerate(mechanisms):
        if not isinstance(item,dict):continue
        name=item.get("name")
        if name=="successful_ack" and "0x00000001" in str(item.get("format", "")):
            note("ACK_IS_0x10FF0",f"four_mechanisms_distinguished.items[{i}]",item,
                 "0x00010FF0 is success ACK; 0x00000001 is drain-only",
                 "_Unit125.pas:00808060-0080809D")
        if name=="outgoing_write" and "9+" in str(item.get("format", "")):
            note("WRITER_HEADER_EIGHT",f"four_mechanisms_distinguished.items[{i}]",item,
                 "0080937C emits eight WriteUInt32 calls; queued SetRate adds a ninth Data call in Execute at 00807F52",
                 "_Unit125.pas:0080937C-008093FD,00807F52")

    gap=evidence.get("gap_analysis_vs_repo",{})
    missing=gap.get("missing_in_repo",[])
    if missing:
        note("WRONG_REPO_SCOPE","gap_analysis_vs_repo.missing_in_repo",missing,
             "Local MVK_Reader_Web folder is not GitHub research branch; source protocol and Qt implementations are already present in working branch",
             "GitHub research/stage111-mvkview-desktop-20261029 / "+KNOWN_MODULES[0])
    if gap.get("confidence")=="VERIFIED_STATIC":
        note("REPO_GAP_NOT_BINARY_PROOF","gap_analysis_vs_repo.confidence","VERIFIED_STATIC",
             "Binary disassembly does not prove absence of code in a repository not searched on GitHub",
             "GitHub branch inspection")

    config=evidence.get("config_reads",{}).get("by_mode",[])
    if config:
        note("CONFIG_TASK_UI_MAPPING_OPEN","config_reads.by_mode","mode 3/4 register maps",
             "Task register blocks are statically visible, but associate UI handlers only by tracing 00846AD4 and actual constructor Task; ConfigIP button requests UI mode4, which is not automatically identical to thread Task4",
             "_Unit128.pas:00848E6C,00846AD4,00846DCC; _Unit125.pas:00807CFA-00807DCF",
             kind="REQUIRES_TRACE")

    source=evidence.get("sources_used",{})
    archive=source.get("projects_7z",{})
    if archive.get("status")=="NOT_USED":
        note("MISSING_ARCHIVE_CROSSCHECK","sources_used.projects_7z",archive,
             "The Harness agent did not use Projects.7z; independent review confirmed six PAS/DFM hashes against SQLite",
             "Projects.7z + mvk_idr(1).sqlite/source_files",kind="PROVENANCE_GAP")
    idp=source.get("mvkview_idp",{})
    if idp.get("status")=="METADATA_ONLY":
        note("IDP_SCOPE_LIMITED","sources_used.mvkview_idp",idp.get("status"),
             "IDP checksum/header verified; IDP internal objects and RTTI are not independently decoded",
             "mvkview.idp SHA256 77e59f98...; SQLite meta.idp_header",kind="PROVENANCE_LIMIT")

    changes=evidence.get("changes_made",{})
    return {
        "schema":"MVK_HARNESS_PROTOCOL_V2_SOURCE_REVIEW_V1",
        "input_registry_id": evidence.get("registry_id"),
        "status":"CORRECTION_REQUIRED" if findings else "NO_KNOWN_CONFLICTS",
        "finding_count":len(findings),
        "by_category":{key:sum(x["category"]==key for x in findings)
                       for key in sorted({x["category"] for x in findings})},
        "findings":findings,
        "source_packet_roles":{f"0x{k:08X}":v for k,v in CORRECT_TYPES.items()},
        "already_in_current_github":list(KNOWN_MODULES),
        "source_recording_field": "TMVKThread.WriteDataStage at +0x40",
        "stage0_to_1_at":"00808617 (nonempty valid PARAM, NOT 0x3100-specific)",
        "values_tick_at":"008085A5 / 008066F0 when ValuesFile exists",
        "harness_code_changed": bool(changes.get("repo_code_modified",False)),
        "safe": "static-only; no packet transmission, process attachment, instrument or private files",
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("input",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if a.input.stat().st_size>4_000_000: p.error("Large evidence file")
    evidence=json.loads(a.input.read_text(encoding="utf-8"))
    result=review(evidence)
    serial=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if a.output:a.output.write_text(serial,encoding="utf-8")
    print(serial)
    return 2 if result["status"]!="NO_KNOWN_CONFLICTS" else 0

if __name__=="__main__":raise SystemExit(main())