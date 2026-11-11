"""Stage111Z31BH: source InputValue local draft/validation regression.

All synthetic register images. No original process, device, Qt or disk write.
"""
from __future__ import annotations

import hashlib
import struct
import pytest

from mvk_compatible.core.original_config_input_draft import (
    SOURCE, SOURCE_INPUT_CASES, SOURCE_BOUND_TYPES, SOURCE_DISPATCH_SHA256,
    SourceInputRejected, LocalConfigDraft, encode_source_text,
    source_type_for_raw_format,
)
from mvk_compatible.core.original_config_register_image import LocalRegisterImage


@pytest.fixture
def image():
    return LocalRegisterImage.from_bytes(bytes(0x1200))


def assert_reject(key, thunk):
    with pytest.raises(SourceInputRejected) as caught:
        thunk()
    assert caught.value.source_key == key
    assert str(caught.value) == key


def test_original_30_type_input_dispatch_separate_from_getvaluetext():
    expected=(1,2,3,0,0,0,5,5,7,7,11,7,4,8,8,6,
              9,9,9,9,9,9,9,9,10,10,10,10,11,11)
    assert SOURCE_INPUT_CASES == expected
    assert hashlib.sha256(bytes(expected)).hexdigest() == SOURCE_DISPATCH_SHA256
    assert SOURCE_BOUND_TYPES == frozenset((0,1,2,5,10,*range(16,30)))
    # Unsupported textual entry types must not be guessed from the display table.
    for type_id in (3,4,5):
        assert_reject("ctNoEntrySupported",lambda t=type_id:
                      encode_source_text(t,"10"))


def test_original_float32_bounds_and_unchanged_caller_image(image):
    draft=LocalConfigDraft.from_local_image(image)
    valid=draft.preview_text("adc",0,"1.25",adc=1)
    assert valid.as_local_image().read_f32(0x102)==1.25
    assert image.read_u32(0x102)==0
    assert not draft.patches and len(valid.patches)==1
    assert valid.patches[0].payload==struct.pack("<f",1.25)
    assert valid.summary()["original_input_was_modified"] is False
    assert valid.summary()["device_write_allowed"] is False
    assert valid.summary()["disk_write_performed"] is False
    assert_reject("ctTooSmall",lambda:
                  draft.preview_text("adc",0,"0",adc=1))
    assert_reject("ctTooBig",lambda:
                  draft.preview_text("adc",0,"1000001",adc=1))
    for s in ("nan","inf","1e999","foo","1,5"):
        assert_reject("ctInvalidFormat",lambda text=s:
                      draft.preview_text("adc",0,text,adc=1))


def test_source_unsigned_port_bounds_and_protection(image):
    draft=LocalConfigDraft.from_local_image(image)
    assert draft.preview_text("ip",3,"65535").as_local_image().read_u32(
        0x0a)==65535
    assert_reject("ctTooSmall",lambda: draft.preview_text("ip",3,"0"))
    assert_reject("ctTooBig",lambda: draft.preview_text("ip",3,"65536"))
    assert_reject("ctTooBig",lambda: draft.preview_text("ip",3,"-1"))
    assert_reject("ctProtectedValue",lambda:
                  draft.preview_text("ip",3,"1000",protected=True))
    assert_reject("ctInvalidFormat",lambda: draft.preview_text("ip",3,"+"))
    assert_reject("ctInvalidFormat",lambda: draft.preview_text("ip",3,"4294967295"))
    assert len(draft.patches)==0


@pytest.mark.parametrize("text,expect",[
    ("10.20.30.40",0x0A141E28),
    ("192.168.1.1",0xC0A80101),
    ("0.0.0.0",0),
    ("255.255.255.255",0xFFFFFFFF),
])
def test_ipv4_source_32bit_storage(image,text,expect):
    draft=LocalConfigDraft.from_local_image(image)
    assert draft.preview_text("ip",0,text).as_local_image().read_u32(4)==expect
    assert draft.preview_text("ip",8,text).as_local_image().read_u32(0x44)==expect


@pytest.mark.parametrize("bad",[
    "256.0.0.1","1.2.3","1.2.3.4.5","-1.2.3.4",
    "192.168.1.a","1. 2.3.4","127.0.0.999","1,2,3,4",
])
def test_ipv4_malformed_source_rejected(image,bad):
    assert_reject("ctInvalidFormat",lambda:
                  LocalConfigDraft.from_local_image(image).preview_text("ip",0,bad))


def test_netmask_original_source_prefix_validation(image):
    draft=LocalConfigDraft.from_local_image(image)
    assert draft.preview_text("ip",1,"255.255.255.0").as_local_image().read_u32(6)==0xFFFFFF00
    assert draft.preview_text("ip",9,"255.255.0.0").as_local_image().read_u32(0x46)==0xFFFF0000
    for bad in ("0.0.0.0","255.255.255.255","255.0.255.0","0.255.255.0"):
        assert_reject("ctInvalidFormat",lambda s=bad:
                      draft.preview_text("ip",1,s))


def test_advanced_id_separate_original_inputvalue_overload(image):
    draft=LocalConfigDraft.from_local_image(image)
    done=draft.preview_advanced_id("ip",4,0x66666666)
    assert done.as_local_image().read_u32(0x0C)==0x66666666
    assert done.patches[0].mode=="advanced-id"
    # Important source subtlety: original doesn't verify membership after
    # checking the selector pointer and cell type.
    unknown=draft.preview_advanced_id("ip",4,0xDEADBEEF)
    assert unknown.as_local_image().read_u32(0x0C)==0xDEADBEEF
    assert_reject("ctInvalidCellType",lambda:
                  draft.preview_advanced_id("ip",0,1))
    assert_reject("ctProtectedValue",lambda:
                  draft.preview_advanced_id("ip",4,1,protected=True))
    assert_reject("ctInvalidFormat",lambda:
                  draft.preview_advanced_id("ip",4,True))
    assert_reject("ctInvalidFormat",lambda:
                  draft.preview_advanced_id("ip",4,2**32))
    assert_reject("ctInvalidFormat",lambda:
                  draft.preview_advanced_id("ip",4,-1))


def test_source_text_hex_and_ascii_ssid_capacity(image):
    draft=LocalConfigDraft.from_local_image(image)
    assert draft.preview_text("ip",4,"0x99999999").as_local_image().read_u32(0x0C)==0x99999999
    assert draft.preview_text("adc",4,"0x00000002",adc=1).as_local_image().read_u32(0x13E)==2
    ssid=draft.preview_text("ip",13,"SSID-A")
    assert ssid.as_local_image().data[0x50*2:0x50*2+7]==b"SSID-A\x00"
    assert len(ssid.patches[0].payload)==32
    assert_reject("ctProtectedValue",lambda:
                  draft.preview_text("ip",14,"Do-not-write-this-password"))
    assert "Do-not-write-this-password" not in repr(draft.summary())
    assert_reject("ctInvalidFormat",lambda:
                  draft.preview_text("ip",13,"Русская сеть"))
    assert_reject("ctInvalidFormat",lambda:
                  draft.preview_text("ip",4,"0x100000000"))


def test_bitfield_input_and_numeric_enum_stay_explicitly_distinct():
    assert encode_source_text(16,"1010") == struct.pack("<I",5)
    assert encode_source_text(17,"1111 0000") == struct.pack("<I",15)
    assert encode_source_text(24,"0xAB") == struct.pack("<I",0xab)
    assert encode_source_text(29,"0xDEADBEEF") == struct.pack("<I",0xDEADBEEF)
    for text in ("1012","", "1"*33):
        assert_reject("ctInvalidFormat",lambda s=text:
                      encode_source_text(16,s))


def test_immutable_draft_patch_replacement_and_hash_receipts(image):
    draft=LocalConfigDraft.from_local_image(image)
    first=draft.preview_text("ip",3,"502")
    second=first.preview_text("ip",3,"503")
    assert len(first.patches)==len(second.patches)==1
    assert first.as_local_image().read_u32(0x0A)==502
    assert second.as_local_image().read_u32(0x0A)==503
    assert draft.original.sha256 == image.sha256
    assert image.read_u32(0x0A)==0
    assert first.summary()["preview_image_sha256"] != second.summary()["preview_image_sha256"]
    assert first.summary()["source"]==SOURCE
    assert not any(v for k,v in first.summary().items()
                   if k in ("disk_write_performed","device_write_allowed"))


def test_addressing_and_untrusted_input_fail_closed():
    short=LocalConfigDraft.from_local_image(
        LocalRegisterImage.from_bytes(bytes(64)))
    assert_reject("ctInvalidAddress",lambda:
                  short.preview_text("ip",13,"SSID"))
    img=LocalRegisterImage.from_bytes(bytes(0x1200))
    draft=LocalConfigDraft.from_local_image(img)
    for section,row,adc in (
        ("wrong",0,None),("adc",0,None),("adc",0,9),
        ("ip",15,None),("calib",-1,None)
    ):
        with pytest.raises((ValueError,SourceInputRejected)):
            draft.preview_text(section,row,"1",adc=adc)
    assert_reject("ctIndexOutOfBounds",lambda:
                  draft.preview_text("ip",True,"1"))


def test_raw_format_source_uses_first_matching_type_and_colon():
    assert source_type_for_raw_format("f")==0
    assert source_type_for_raw_format("v")==6
    assert source_type_for_raw_format("h")==10  # 28/29 are later aliases
    assert source_type_for_raw_format("b")==16  # 17..23 are later aliases
    assert source_type_for_raw_format("p")==14
    for letter in ("F","D","!","?", "", "ff"):
        assert_reject("ctInvalidFormat",lambda c=letter:
                      source_type_for_raw_format(c))


def test_raw_loader_preview_reuses_source_converter_without_bounds(image):
    draft=LocalConfigDraft.from_local_image(image)
    f32=draft.preview_raw_format(0x20,"f:2.5")
    assert f32.as_local_image().read_f32(0x20)==2.5
    assert f32.patches[0].mode=="raw-format"
    # Original InputValueRaw intentionally bypasses SetBounds and cell
    # protection. Unlike original, this PREVIEW has no write capability.
    raw=draft.preview_raw_format(0x0A,"w:0")
    assert raw.as_local_image().read_u32(0x0A)==0
    assert raw.summary()["device_write_allowed"] is False
    assert raw.summary()["disk_write_performed"] is False
    ip=draft.preview_raw_format(4,"v:10.20.30.40")
    assert ip.as_local_image().read_u32(4)==0x0A141E28
    hx=draft.preview_raw_format(0x20,"h:0xFEAABBCC")
    assert hx.as_local_image().read_u32(0x20)==0xFEAABBCC
    bits=draft.preview_raw_format(0x20,"b:1001")
    assert bits.as_local_image().read_u32(0x20)==9


def test_raw_text_input_source_gates_sensitive_and_bad_format(image):
    draft=LocalConfigDraft.from_local_image(image)
    for text in ("f", "f 1.5", "F:1.5", "D:44", "!:test", "x:5"):
        assert_reject("ctInvalidFormat",lambda v=text:
                      draft.preview_raw_format(0x20,v))
    for addr in (0x60,0x62,0x7E):
        assert_reject("ctProtectedValue",lambda a=addr:
                      draft.preview_raw_format(a,"h:0x1"))
    assert_reject("ctInvalidAddress",lambda:
                  draft.preview_raw_format(1,"f:1"))
    assert_reject("ctInvalidAddress",lambda:
                  draft.preview_raw_format(0xFFFE,"f:1"))


def test_original_raw_and_typed_field_alias_is_rejected(image):
    draft=LocalConfigDraft.from_local_image(image)
    typed=draft.preview_text("ip",3,"502")
    assert_reject("ctInvalidCellType",lambda:
                  typed.preview_raw_format(0x0A,"w:100"))
    raw=draft.preview_raw_format(0x0A,"w:123")
    assert_reject("ctInvalidCellType",lambda:
                  raw.preview_text("ip",3,"502"))
