"""BQ: source-format PageConfig local Load -> typed Edit -> Save -> Reload.

Offline only: no private originals, no device, no calibration or network.
Source from IDR TMvkCellList.SaveValuesToFile / LoadValuesFromFile.
"""
import hashlib
import pytest

from ..core.original_config_local_workflow import (
    OriginalLocalConfigWorkspace,SOURCE)
from ..core.original_config_input_draft import SourceInputRejected
from ..core.original_config_readonly import inspect_original_local_config


def _source(tmp_path):
    root=tmp_path/"local_source.txt"
    sub=tmp_path/"sub.cfg"
    sub.write_text(
        "; original ADC1 cells\n"
        "+0x0100\n0x0002 F:1.25\n0x0062 F:2.50\n",
        encoding="utf-8")
    root.write_text(
        "; source-compatible synthetic file with a bounded include\n"
        "0x0004 D:16909060\n0x000A D:502\n0x0020 F:2.5\n"
        "0x0060 S:synthetic-opaque-string\n"
        "@sub.cfg\n",encoding="utf-8")
    return root,sub


def test_real_source_load_edit_save_reload_exact_raw_format_all_three_pages(tmp_path):
    source,include=_source(tmp_path)
    a_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    b_sha=hashlib.sha256(include.read_bytes()).hexdigest()
    w=OriginalLocalConfigWorkspace.load(source)
    assert w.describe()["source"]==SOURCE
    assert w.current.value(0x0162).formatted=="F:2.50"
    assert w.changed_count==0
    w=w.edit_field("ip",3,"503")
    w=w.edit_field("calib",0,"3.5")
    w=w.edit_field("adc",0,"1.75",adc=1)
    w=w.edit_alarm(1,1,"yellow_threshold","4.50")
    assert w.changed_count==4
    assert w.original.value(0x000A).formatted=="D:502"
    assert w.current.value(0x000A).formatted=="D:503"
    assert w.current.value(0x0020).formatted=="F:3.5"
    assert w.current.value(0x0102).formatted=="F:1.75"
    assert w.current.value(0x0162).formatted=="F:4.50"
    assert w.current.value(0x0060).literal=="synthetic-opaque-string"
    report=w.describe()
    assert "synthetic-opaque-string" not in repr(report)
    assert not report["hardware_write_enabled"]
    assert not report["local_original_changed"]
    out=tmp_path/"new_local_config.cfg"
    result=w.save_as(out)
    assert result["local_source_file_created"]
    assert result["source_loader_roundtrip_verified"]
    assert result["saved_cells"]==len(w.current.cells)
    assert result["edited_cells"]==4
    assert result["saved_sha256"]==hashlib.sha256(out.read_bytes()).hexdigest()
    assert result["device_commands_or_calibration_executed"] is False
    assert not result["original_live_device_config_verified"]
    assert not result["original_delphi_bytes_and_codepage_verified"]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==a_sha
    assert hashlib.sha256(include.read_bytes()).hexdigest()==b_sha
    assert b"+0x0000" in out.read_bytes()
    assert b"@sub.cfg" not in out.read_bytes()  # flatten source includes
    confirmed=inspect_original_local_config(out)
    assert tuple((x.address,x.formatted) for x in confirmed.cells)==tuple(
        (x.address,x.formatted) for x in w.current.cells)
    reopened=OriginalLocalConfigWorkspace.load(out)
    assert not reopened.changed
    assert reopened.current.value(0x0162).formatted=="F:4.50"
    reverted=w.discard_changes()
    assert reverted.changed_count==0
    assert reverted.current.value(0x000A).formatted=="D:502"
    assert reverted.current.value(0x0162).formatted=="F:2.50"


def test_draft_validation_and_password_protection_no_modification(tmp_path):
    source,_=_source(tmp_path)
    w=OriginalLocalConfigWorkspace.load(source)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    wrong=[
        ("ip",3,"0",None,"ctTooSmall"),
        ("ip",3,"65536",None,"ctTooBig"),
        ("ip",3,"wrong",None,"ctInvalidFormat"),
        ("ip",14,"a-secret",None,"ctProtectedValue"),
        ("ip",13,"SOME-SSID",None,"ctProtectedValue"),
        ("adc",0,"-2",1,"ctTooSmall"),
    ]
    for section,row,text,adc,message in wrong:
        with pytest.raises(SourceInputRejected,match=message):
            w.edit_field(section,row,text,adc=adc)
    with pytest.raises(SourceInputRejected,match="ctNoEntrySupported"):
        w.edit_alarm(1,2,"yellow_threshold","5.1")
    with pytest.raises(ValueError):
        w.edit_field("adc",0,"2")
    assert w.changed_count==0
    assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
    assert "a-secret" not in repr(w.describe())


def test_never_overwrite_original_or_changed_includes_or_existing_file(tmp_path):
    source,include=_source(tmp_path)
    w=OriginalLocalConfigWorkspace.load(source).edit_field("ip",3,"505")
    with pytest.raises(ValueError,match="NEW local"):
        w.save_as(source)
    dest=tmp_path/"existing.txt"
    dest.write_text("must stay untouched",encoding="utf-8")
    with pytest.raises(ValueError,match="NEW local"):
        w.save_as(dest)
    assert dest.read_text()=="must stay untouched"
    include.write_text(include.read_text()+";changed\n",encoding="utf-8")
    with pytest.raises(ValueError,match="changed since opening"):
        w.save_as(tmp_path/"new.cfg")
    assert not (tmp_path/"new.cfg").exists()


def test_source_cells_are_immutable_until_local_editor_commit(tmp_path):
    source,_=_source(tmp_path)
    w=OriginalLocalConfigWorkspace.load(source)
    draft=w.edit_field("ip",3,"502")  # identical original literal
    assert not draft.changed
    assert draft.current.value(0x000A).formatted=="D:502"
    draft=draft.edit_field("ip",3,"504")
    assert draft.changed
    draft=draft.edit_field("ip",3,"502")
    assert not draft.changed
    assert w.current.value(0x000A).formatted=="D:502"
