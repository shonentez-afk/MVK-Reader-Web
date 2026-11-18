"""Physical Ethernet on one PC: no Wi-Fi/VPN, no guess, no device TCP."""
import json
import subprocess

import pytest

from mvk_live_standalone import ethernet as eth


def _entry(ip="192.168.10.101",index=12,name="Ethernet",prefix=24):
    return dict(Name=name,InterfaceIndex=index,IPv4=ip,PrefixLength=prefix)


def test_one_physical_ethernet_ipv4_is_selected_without_network():
    nic=eth.parse_windows_ethernet_json(json.dumps([_entry()]))
    assert nic.name=="Ethernet"
    assert nic.if_index==12
    assert nic.ipv4=="192.168.10.101"
    assert nic.prefix_length==24
    assert "192.168.10.101/24" in nic.description


def test_none_and_multiple_ipv4_fail_closed_instead_of_wifi_or_vpn():
    with pytest.raises(ValueError,match="Нет активного"):
        eth.parse_windows_ethernet_json("[]")
    with pytest.raises(ValueError,match="несколько"):
        eth.parse_windows_ethernet_json(json.dumps([
            _entry(),_entry(ip="192.168.10.102",index=12)]))
    with pytest.raises(ValueError,match="несколько"):
        eth.parse_windows_ethernet_json(json.dumps([
            _entry(),_entry(ip="10.0.3.15",index=17,name="Ethernet 2")]))


@pytest.mark.parametrize("invalid",[
    "169.254.1.10","127.0.0.1","0.0.0.0","224.0.0.1",
    "255.255.255.255","999.1.1.1","192.168.010.11",
])
def test_unusable_addresses_rejected(invalid):
    with pytest.raises(ValueError):
        eth.parse_windows_ethernet_json(json.dumps([_entry(ip=invalid)]))


def test_no_silent_fallback_from_invalid_os_data():
    with pytest.raises(ValueError):
        eth.parse_windows_ethernet_json('{"IPv4":"192.168.10.101"}')
    with pytest.raises(ValueError):
        eth.parse_windows_ethernet_json("not json")
    with pytest.raises(ValueError):
        eth.parse_windows_ethernet_json(json.dumps([_entry(index=0)]))
    with pytest.raises(ValueError):
        eth.parse_windows_ethernet_json(json.dumps([_entry(prefix=0)]))
    with pytest.raises(ValueError):
        eth.parse_windows_ethernet_json(json.dumps([_entry(name="")]))


def test_powershell_invocation_is_read_only_and_has_timeout(monkeypatch):
    seen=[]
    class Completed:
        returncode=0
        stdout=json.dumps([_entry()]).encode("utf-8")
    def fake_run(args,**kw):
        seen.append((args,kw))
        return Completed()
    monkeypatch.setattr(eth.sys,"platform","win32")
    monkeypatch.setattr(subprocess,"run",fake_run)
    nic=eth.discover_single_wired_ethernet()
    assert nic.ipv4=="192.168.10.101"
    assert len(seen)==1
    argv,opts=seen[0]
    assert argv[:3]==["powershell.exe","-NoProfile","-NonInteractive"]
    assert opts["capture_output"] and opts["timeout"]<=10
    command=argv[-1]
    assert "Get-NetAdapter" in command and "-Physical" in command
    assert "Get-NetIPAddress" in command and "AddressFamily IPv4" in command
    assert "[int]$_.ifType -eq 6" in command  # physical Ethernet, NOT Wi-Fi
    assert not any(word in command for word in (
        "New-NetIPAddress","Set-NetIPAddress","Remove-NetIPAddress",
        "Enable-NetAdapter","Disable-NetAdapter","Test-NetConnection",
        "Invoke-WebRequest","Start-Process"
    ))


def test_non_windows_or_adapter_error_does_not_connect(monkeypatch):
    monkeypatch.setattr(eth.sys,"platform","linux")
    with pytest.raises(ValueError,match="Windows"):
        eth.discover_single_wired_ethernet()
    monkeypatch.setattr(eth.sys,"platform","win32")
    def fake_timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired("powershell.exe",10)
    monkeypatch.setattr(subprocess,"run",fake_timeout)
    with pytest.raises(ValueError,match="сетевые карты"):
        eth.discover_single_wired_ethernet()
