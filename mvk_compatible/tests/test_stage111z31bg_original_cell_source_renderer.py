"""Stage111Z31BG: original TMvkCellList case dispatch on synthetic bytes.

Tests do NOT use original BIN/IDP, device, original executable or network.
Runtime Delphi string parity remains unverified even on exact source cases.
"""
import struct
import pytest

from mvk_compatible.core.original_config_register_image import LocalRegisterImage
from mvk_compatible.core.original_cell_source_renderer import (
    SOURCE_DISPATCH_CASES, render_source_cell, render_source_section,
)


def image_with(address, payload, *, length=0x1000):
    data=bytearray(length)
    data[address*2:address*2+len(payload)]=payload
    return LocalRegisterImage.from_bytes(bytes(data))


def test_source_switch_topology_all_30_types():
    assert len(SOURCE_DISPATCH_CASES)==30
    assert SOURCE_DISPATCH_CASES[:16]==(
        1,2,3,4,6,7,8,8,9,9,10,9,5,9,9,8)
    assert SOURCE_DISPATCH_CASES[16:24]==(12,)*8
    assert SOURCE_DISPATCH_CASES[24:28]==(13,)*4
    assert SOURCE_DISPATCH_CASES[28:]==(11,10)


@pytest.mark.parametrize("type_id,number,kind,expected",(
    (1,0xFFFFFFFF,"int32","-1"),
    (2,0xFFFFFFFF,"uint32","4294967295"),
    (5,0x00000021,"set-bit-indexes","0,5"),
    (5,0,"set-bit-indexes","---"),
    (6,0x0A141E28,"ipv4-source-network-order","10.20.30.40"),
    (7,0x0A141E28,"ipv4-source-network-order","10.20.30.40"),
    (15,0xC0A80101,"ipv4-source-network-order","192.168.1.1"),
    (10,0xDEADBEEF,"hex-uint32","0xDEADBEEF"),
    (12,3661,"hms-from-uint32-seconds","01:01:01"),
    (16,0x0000000B,"lsb-first-bits-nibble-spaces","1101 "),
    (17,0x000000FF,"lsb-first-bits-nibble-spaces","1111 1111 "),
    (24,0xABCD12EF,"hex-bytes-spaced","EF "),
    (25,0xABCD12EF,"hex-bytes-spaced","EF 12 "),
    (26,0xABCD12EF,"hex-bytes-spaced","EF 12 CD "),
    (27,0xABCD12EF,"hex-bytes-spaced","EF 12 CD AB "),
    (28,0xABCD12EF,"hex-uint16","0x12EF"),
    (29,0xABCD12EF,"hex-uint32","0xABCD12EF"),
))
def test_exact_dispatched_values(type_id,number,kind,expected):
    image=image_with(0x20,struct.pack("<I",number))
    row=render_source_cell(image,0x20,type_id)
    assert row.kind==kind and row.display==expected
    assert row.source_branch_verified
    assert not row.original_runtime_text_verified
    assert not row.original_live_device_verified
    assert not row.mutable


def test_source_compact_hex_and_ascii_ansi_encoding_conservatism():
    image=image_with(0x20,bytes(range(16)))
    cell=render_source_cell(image,0x20,4)
    assert cell.kind=="hex-bytes-concatenated"
    assert cell.display=="000102030405060708090A0B0C0D0E0F"
    image=image_with(0x20,b"ACME\x00"+bytes(27))
    assert render_source_cell(image,0x20,9).display=="ACME"
    image=image_with(0x20,b"\xD0\xA0\x00"+bytes(29))
    row=render_source_cell(image,0x20,9)
    assert row.display=="—" and not row.source_branch_verified


def test_float32_exact_storage_but_delphi_text_not_claimed():
    image=image_with(0x20,struct.pack("<I",0x80000000))
    row=render_source_cell(image,0x20,0)
    assert row.kind=="float32-storage" and row.display=="0"
    assert row.source_branch_verified
    image=image_with(0x20,struct.pack("<I",0x7FC00001))
    row=render_source_cell(image,0x20,0)
    assert row.display=="NAN"
    assert row.source_branch_verified
    assert not row.original_runtime_text_verified


def test_datetime_source_branch_is_not_speculative():
    image=image_with(0x20,b"\x00"*4)
    row=render_source_cell(image,0x20,3)
    assert row.kind=="datetime-delphi-source-unresolved"
    assert row.display=="—"
    assert not row.source_branch_verified


def test_advanced_bitmask_and_missing_runtime_localization():
    image=image_with(0x20,struct.pack("<I",0x66666666))
    row=render_source_cell(image,0x20,10,advanced="modbus_endian")
    assert row.kind=="advanced-source-ID-untranslated-title"
    assert row.display=="EndianCell6"
    assert not row.source_branch_verified
    image=image_with(0x20,struct.pack("<I",0x00030000))
    row=render_source_cell(image,0x20,10,advanced="option",
                           bits=2,bit_start=16)
    assert row.display=="OptionCell3"


def test_password_source_never_leaked_even_as_hex_or_summary():
    image=image_with(0x60,b"ABCD:super-secret\x00"+bytes(46))
    row=render_source_cell(image,0x60,14,key="ConfigWifiPassword")
    assert row.kind=="sensitive-redacted"
    assert row.display=="••••••••"
    assert "secret" not in repr(row.report())
    assert "41424344" not in repr(row.report())
    rows=render_source_section(image,"ip")
    assert rows[14]["display"]=="••••••••"
    assert "secret" not in str(rows)


def test_all_15_10_88_source_cells_render_in_order():
    img=LocalRegisterImage.from_bytes(bytes(0x1200))
    assert len(render_source_section(img,"ip"))==15
    assert len(render_source_section(img,"calib"))==10
    assert len(render_source_section(img,"adc",adc=8))==11
    assert render_source_section(img,"adc",adc=8)[0]["register"]=="0x0802"


@pytest.mark.parametrize("address,type_id,kwargs",(
    (1,0,{}),(-2,0,{}),(0x10000,0,{}),
    (0,30,{}),(0,-1,{}),(0,True,{}),
    (0,0,{"bits":33}),(0,0,{"bit_start":-1}),
    (0,0,{"bits":16,"bit_start":17}),
    (0,0,{"sensitive":1}),
))
def test_bad_source_type_address_and_bit_ranges_rejected(address,type_id,kwargs):
    img=LocalRegisterImage.from_bytes(bytes(256))
    with pytest.raises(ValueError):
        render_source_cell(img,address,type_id,**kwargs)


def test_truncated_extended_cell_does_not_bleed_to_next_register():
    img=LocalRegisterImage.from_bytes(bytes(256))
    with pytest.raises(ValueError):
        render_source_cell(img,0x70,14)
