"""Pure static tests. No Ghidra, instrument, network, or project source needed."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reconcile_harness_protocol_v2 import review, CORRECT_TYPES


def evidence(**updates):
    base={"registry_id":"mvk_protocol_evidence_v2","data_stream_frame":{},
          "data_stream_processing":{},"descriptor_loop":{},
          "trigger_0x3100":{},"four_mechanisms_distinguished":{"items":[]},
          "gap_analysis_vs_repo":{},"sources_used":{},"config_reads":{},"changes_made":{}}
    base.update(updates)
    return base


def test_empty_evidence_has_no_fabricated_conflicts():
    r=review(evidence())
    assert r["finding_count"]==0
    assert r["status"]=="NO_KNOWN_CONFLICTS"
    assert len(r["source_packet_roles"])==6
    assert CORRECT_TYPES[1]=="DRAIN_UINT32"


def test_detects_type1_as_adc_and_channel10_as_tach():
    report=evidence(data_stream_frame={"packet_type":1,
        "tach_branch_not_disassembled":{"target":"00808339"}})
    codes={x["code"] for x in review(report)["findings"]}
    assert {"TYPE1_NOT_SAMPLES","CHANNEL10_INVALID_NOT_TACH"}<=codes


def test_exposes_stage_and_recording_semantics_confusion():
    report=evidence(data_stream_processing={"channel_activation":{"claim":"channel0 sets +0x40=1"}},
      descriptor_loop={"count":14,"semantics":"8 ADC + 2 TACH + 4 service"},
      trigger_0x3100={"meaning_inferred":"переключатель состояния",
          "on_match":[{"action":"008085D1 цикл команд"}]})
    codes={x["code"] for x in review(report)["findings"]}
    assert {"CHANNEL0_WRITEDATA_STAGE","14_STATUSCELLS_NOT_DESCRIPTORS",
            "REGISTER3100_NOT_STAGE_TRIGGER","00806030_NOT_COMMAND_LOOP"}<=codes


def test_keeps_ack_and_eight_writer_calls_separate():
    report=evidence(four_mechanisms_distinguished={"items":[
        {"name":"successful_ack","format":"type 0x00000001"},
        {"name":"outgoing_write","format":"9+ words"}]})
    codes={x["code"] for x in review(report)["findings"]}
    assert "ACK_IS_0x10FF0" in codes
    assert "WRITER_HEADER_EIGHT" in codes


def test_local_non_git_folder_is_not_absence_of_connected_github_project():
    r=review(evidence(gap_analysis_vs_repo={"missing_in_repo":["MVK TCP"],
              "confidence":"VERIFIED_STATIC"}))
    assert {"WRONG_REPO_SCOPE","REPO_GAP_NOT_BINARY_PROOF"}<={x["code"] for x in r["findings"]}
    assert any(x.endswith("original_mode2_received_frames.py") for x in r["already_in_current_github"])


def test_provenance_limits_are_not_source_binary_conflicts():
    r=review(evidence(sources_used={"projects_7z":{"status":"NOT_USED"},
              "mvkview_idp":{"status":"METADATA_ONLY"}}))
    assert r["by_category"]=={"PROVENANCE_GAP":1,"PROVENANCE_LIMIT":1}


def test_wrong_schema_rejected():
    for bad in (None,[],{}, {"registry_id":"v1"}):
        with pytest.raises(ValueError):review(bad)


def test_reconstruct_report_keys_from_actual_user_v2_json():
    # Tests the actual evidence schema without reading any private source code.
    path=Path('/mnt/data/MVK_PROTOCOL_EVIDENCE_V2.json')
    if not path.exists():pytest.skip('User upload is only mounted in local review')
    result=review(json.loads(path.read_text(encoding='utf-8')))
    assert result["finding_count"]>=11
    assert result["by_category"]["SOURCE_CONFLICT"]>=7