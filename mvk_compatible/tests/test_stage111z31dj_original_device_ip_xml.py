"""Original XML uses CP1251 and edIpAddr, not machine NIC discovery."""
from __future__ import annotations
import pytest
from mvk_compatible.core.original_device_ip_settings import (
 read_original_device_address,save_compatible_device_address,startup_device_address,
)
from mvk_compatible.core.original_start_workbench import START_IP_DEFAULT


def test_read_realistic_original_cp1251_xml(tmp_path):
    xml=tmp_path/"mvkview.exe.xml"
    xml.write_bytes(('<?xml version="1.0" encoding="windows-1251"?>'
        '<Configuration><Device><Address>192.168.0.30</Address></Device>'
        '<Library><Path>Сигналы</Path></Library>'
        '<Advanced><DrawInterval>20</DrawInterval></Advanced>'
        '</Configuration>').encode("cp1251"))
    assert read_original_device_address(xml)=="192.168.0.30"
    xml.write_text('<Configuration><Device /></Configuration>',encoding="utf8")
    assert read_original_device_address(xml)==START_IP_DEFAULT
    xml.write_text('<Configuration><Device><Address>198.51.100.11</Address>'
                   '</Device></Configuration>',encoding="utf8")
    assert read_original_device_address(xml)=="198.51.100.11"


def test_settings_are_profile_isolated_and_atomic(tmp_path,monkeypatch):
    vendor=tmp_path/"mvkview.exe.xml"
    vendor.write_text('<Configuration><Device><Address>192.168.0.30</Address>'
                      '</Device></Configuration>',encoding="utf8")
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    override=save_compatible_device_address("192.168.0.42")
    assert override==tmp_path/"MVKViewCompatible"/"device.xml"
    assert read_original_device_address(override)=="192.168.0.42"
    assert read_original_device_address(vendor)=="192.168.0.30"
    assert startup_device_address()==("192.168.0.42","compatible")


@pytest.mark.parametrize("value",["127.0.0.1","0.0.0.0","192.168.0.30 ",
                                      "10.0.0.999","255.255.255.255"])
def test_invalid_operator_ip_does_not_replace_good_settings(tmp_path,value):
    dest=tmp_path/"saved.xml"
    save_compatible_device_address("192.168.0.30",dest)
    before=dest.read_bytes()
    with pytest.raises(ValueError):
        save_compatible_device_address(value,dest)
    assert dest.read_bytes()==before


def test_malformed_xml_refused_and_cannot_emit_commands(tmp_path):
    source=tmp_path/"bad.xml"
    source.write_bytes(b'<!DOCTYPE Configuration [<!ENTITY a "evil">]>'
                       b'<Configuration><Device><Address>&a;</Address></Device></Configuration>')
    with pytest.raises(ValueError,match="DTD"):
        read_original_device_address(source)
