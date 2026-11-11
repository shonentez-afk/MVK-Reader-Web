"""Stage111Z31BD original IDR config text, 8x8x8 and TLanguage tests.

All local files below fabricated; original private IDP/PAS/DFM remain local.
"""
from pathlib import Path
import pytest

from mvk_compatible.core.original_config_readonly import (
    SOURCE, FIELDS, UNKNOWN, alarm_config_register, alarm_live_status_register,
    inspect_original_local_config, empty_original_config_inspection,
)
from mvk_compatible.core.original_language_source import (
    ALL_SOURCE_KEYS, SOURCE_KEY_SET, source_localize,
)


def test_full_alarm_register_domain_and_unique_status_addresses():
    addrs=set()
    states=set()
    for adc in range(1,9):
        for slot in range(1,9):
            status=alarm_live_status_register(adc,slot)
            assert status not in states
            states.add(status)
            assert status==0x2000+(adc-1)*0x200+0x130+(slot-1)*8
            for key,_,delta in FIELDS:
                reg=alarm_config_register(adc,slot,key)
                assert reg==0x100+(adc-1)*0x100+0x60+(slot-1)*0x10+delta
                assert reg not in addrs
                addrs.add(reg)
    assert len(addrs)==512
    assert len(states)==64
    assert min(addrs)==0x160 and max(addrs)==0x8DE
    assert min(states)==0x2130 and max(states)==0x2F68
    for adc,slot,field in ((0,1,"parameter_id"),(9,1,"parameter_id"),
                           (1,0,"parameter_id"),(1,9,"parameter_id"),
                           (True,1,"parameter_id"),(1,1,"bad")):
        with pytest.raises(ValueError):
            alarm_config_register(adc,slot,field)


def test_original_0x_save_format_includes_and_readonly_provenance(tmp_path):
    (tmp_path/"child.txt").write_text(
        "; included base inherited from parent\n"
        "0x0064 F:3.500 ; red threshold\n"
        "0x0066 D:2 ; up-delay\n",encoding="utf-8")
    p=tmp_path/"original_config.txt"
    p.write_text(
        "; resembles original TMvkCellList.SaveValuesToFile\n"
        "+0x0100\n"
        "0x0060 D:44 ; param index (unverified)\n"
        "0x0062 F:2.500 ; yellow threshold\n"
        "@child.txt\n"
        "+0x0200\n"
        "0x0060 D:6 ; next ADC, not original live verified\n"
        "0x0000 H:0012 ; other basic register, unknown semantics\n",
        encoding="utf-8")
    doc=inspect_original_local_config(p)
    assert doc.source==SOURCE
    assert len(doc.cells)==6
    assert len(doc.file_digests)==2
    assert doc.value(0x160).formatted=="D:44"
    assert doc.value(0x162).formatted=="F:2.500"
    assert doc.value(0x164).formatted=="F:3.500"
    assert doc.value(0x166).formatted=="D:2"
    assert doc.value(0x260).formatted=="D:6"
    assert doc.value(0x200).formatted=="H:0012"
    assert len(doc.other_raw_rows())==1
    assert doc.other_raw_rows()[0].address==0x200
    assert len(doc.channel_rows())==8
    assert doc.channel_rows()[0]["known_alarm_cells_in_file"]==4
    assert doc.channel_rows()[1]["known_alarm_cells_in_file"]==1
    assert len(doc.alarm_rows())==64
    assert doc.alarm_rows()[0]["fields"]["parameter_id"]["raw_value"]=="D:44"
    assert doc.alarm_rows()[0]["fields"]["red_threshold"]["raw_value"]=="F:3.500"
    assert doc.alarm_rows()[0]["raw_source_status_address"]=="0x2130"
    assert doc.alarm_rows()[1]["fields"]["parameter_id"]["raw_value"]==UNKNOWN
    assert doc.alarm_rows()[8]["fields"]["parameter_id"]["raw_value"]=="D:6"
    report=doc.report()
    assert report["alarm_registers_present"]==5
    assert report["alarm_registers_expected"]==512
    assert report["parsed_cells"]==6
    assert report["channels"]==8 and report["slots_per_channel"]==8
    assert report["original_live_device_config_verified"] is False
    assert report["original_config_write_roundtrip_verified"] is False
    assert report["device_actions_allowed"] is False
    assert "filename" in report["file_digests"][0]
    assert "path" not in str(report)
    assert str(tmp_path) not in str(report)


def test_empty_source_is_512_unknown_fields_not_guessed_live():
    d=empty_original_config_inspection()
    assert not d.cells and not d.file_digests
    assert d.report()["alarm_registers_present"]==0
    assert len(d.alarm_rows())==64
    assert all(cell["raw_value"]==UNKNOWN
               for row in d.alarm_rows()
               for cell in row["fields"].values())
    assert all(not row["device_config_verified"] for row in d.channel_rows())


@pytest.mark.parametrize("lines",[
    "0x0001 F:1.0\n",  # odd source register address
    "+0x0001\n0x0000 F:1.0\n",
    "+0xFFFE\n0x0002 F:1.0\n",
    "0x0000 :0.1\n",
    "0x0000 bad\n",
    "not-a-hex F:1\n",
    "0x0060 D:1\n0x0060 D:2\n",
    "@../secret.txt\n",
    "@/tmp/test.txt\n",
    "@c:\\windows\\hosts\n",
    "@wrong.dat\n",
    "@self.txt\n",
    "0x0060 D:1\n0x0062\n",
])
def test_bad_untrusted_config_format_fails_closed(tmp_path,lines):
    p=tmp_path/"self.txt"
    p.write_text(lines,encoding="utf-8")
    with pytest.raises((OSError,ValueError)):
        inspect_original_local_config(p)


def test_symlink_and_config_mutation_cannot_be_accepted(tmp_path):
    original=tmp_path/"real.txt"
    original.write_text("0x0060 D:1\n",encoding="utf-8")
    link=tmp_path/"via.txt"
    try:link.symlink_to(original)
    except OSError:pytest.skip("Creating test symlink unavailable")
    with pytest.raises(ValueError):
        inspect_original_local_config(link)


def test_no_invented_vendor_translation_values():
    assert len(ALL_SOURCE_KEYS)==191
    assert len(SOURCE_KEY_SET)==191
    for key in ("AlarmBand","AlarmRedThr","ConfigADC","xConfigCh",
                "ctInvalidFormat","errProtectedValue","ConfigWifiSSID"):
        row=source_localize(key)
        assert row.key==key and row.known_source_key
        assert row.original_translation_verified is False
        assert row.display
    assert source_localize("AlarmRedThr").display=="Красный порог"
    assert source_localize("ConfigWifiSSID").display=="ConfigWifiSSID"
    with pytest.raises(KeyError):
        source_localize("InventedRussianTranslation")
