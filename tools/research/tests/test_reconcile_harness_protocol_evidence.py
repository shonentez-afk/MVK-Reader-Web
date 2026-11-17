"""Fast synthetic regressions for third-party protocol evidence review."""
from __future__ import annotations

import unittest
from tools.research.reconcile_harness_protocol_evidence import review, EXPECTED_DISPATCH


class HarnessProtocolEvidenceTests(unittest.TestCase):
    @staticmethod
    def correct_fixture():
        return {
            "registry_id":"test",
            "wire_protocol":{
                "packet_type_dispatch":{"types":[
                    {"type_hex":f"0x{k:08X}", "name_inferred":v[0]}
                    for k,v in EXPECTED_DISPATCH.items()
                ]},
                "outgoing_command_frame":{
                    "words":[
                        {"value":"0xFF800C0D"}, {"value":"36"},
                        *({"value":"0"} for _ in range(4)),
                        {"value":"1"},{"value":"0x0002000E"},
                    ],
                    "min_frame_bytes":32,
                },
            },
            "sources_used":{"projects_7z":{"used":True}},
            "channel_processing":{"write_flags":[{"field":"thread+0x404E0"}]},
            "dfm_measure_controls":[{"handler":"tmInterfaceUpdateTimer"}],
            "changes_made":{"core_code_modified":False},
        }

    def test_source_based_correct_fixture_has_no_conflicts(self):
        verdict=review(self.correct_fixture())
        self.assertEqual(verdict["source_conflict_count"],0)
        self.assertEqual(verdict["review_status"],"NO_KNOWN_SOURCE_CONFLICTS")

    def test_harness_misidentified_packet_roles_are_rejected(self):
        data=self.correct_fixture()
        wrong={1:"DATA_STREAM",0x10FF0:"STATUS_CONFIG",
               0xFF8001AC:"REPLY_A",0xFF800ADC:"REPLY_B",
               0xFF800C0D:"REPLY_CMD"}
        for x in data["wire_protocol"]["packet_type_dispatch"]["types"]:
            key=int(x["type_hex"],16)
            if key in wrong:x["name_inferred"]=wrong[key]
        codes={x["code"] for x in review(data)["conflicts"]}
        for key in wrong:self.assertIn(f"MISLABELED_{key:08X}",codes)

    def test_nine_fixed_words_are_not_eight_header_calls(self):
        data=self.correct_fixture()
        data["wire_protocol"]["outgoing_command_frame"]["words"].insert(6,{"value":"0"})
        data["wire_protocol"]["outgoing_command_frame"]["min_frame_bytes"]=36
        codes={x["code"] for x in review(data)["conflicts"]}
        self.assertTrue({"WRITER_HEADER_WORD_COUNT","WRITER_RESERVED_ZERO_COUNT",
                         "WRITER_FUNCTION_SIZE_CONFLATED"} <= codes)

    def test_original_time_offset_timer_and_archive_provenance(self):
        data=self.correct_fixture()
        data["channel_processing"]["write_flags"]=[{"field":"thread+0x400E0"}]
        data["dfm_measure_controls"][0]["flag_field"]="+0xBD8"
        data["sources_used"]["projects_7z"]["used"]=False
        codes={x["code"] for x in review(data)["conflicts"]}
        self.assertTrue({"WRITEDATA_TIME_WRONG_OFFSET","TIMER_BODY_CONFUSION",
                         "ARCHIVE_NOT_EXAMINED"} <= codes)

    def test_missing_and_duplicate_packet_types_fail_closed(self):
        data=self.correct_fixture()
        data["wire_protocol"]["packet_type_dispatch"]["types"].pop()
        self.assertIn("PACKET_TYPES_INCOMPLETE",
                      {x["code"] for x in review(data)["conflicts"]})
        data["wire_protocol"]["packet_type_dispatch"]["types"].append(
            data["wire_protocol"]["packet_type_dispatch"]["types"][0])
        with self.assertRaises(ValueError):review(data)


if __name__=="__main__":unittest.main()