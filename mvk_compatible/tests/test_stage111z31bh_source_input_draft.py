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
