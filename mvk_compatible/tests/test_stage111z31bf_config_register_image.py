"""Stage111Z31BF local synthetic register-image source regression.

Never uses original IDP/BIN/device; all byte payloads fabricated.
"""
import hashlib
import struct

import pytest

from mvk_compatible.core.original_config_register_image import (
    MAX_LOCAL_REGISTER_IMAGE_BYTES, SOURCE_ENUM_CONSTRUCTORS,
    LocalRegisterImage, extract_source_advanced_bits,
)


def put_u32(buf, address, value):
    struct.pack_into("<I", buf, 2*address, value)


def test_source_word_to_byte_address_and_channel_offsets():
    payload=bytearray(0x900*2+4)
    # Address 0x0102 starts at BYTE offset 0x0204, not 0x0102.
    put_u32(payload,0x0102,0x3F800000)
    put_u32(payload,0x0802,0x40200000)
    put_u32(payload,0x000C,0x66666666)
    put_u32(payload,0x0100+0x3E,2)
    image=LocalRegisterImage.from_bytes(bytes(payload))
    assert image.read_u32(0x0102)==0x3F800000
    assert image.read_f32(0x0102)==1.0
    assert image.read_f32(0x0802)==2.5
    assert image.read_u32(0x000C)==0x66666666
    assert image.preview_source_field("adc",0,adc=8)["float32"]=="2.5"
    endian=image.preview_source_field("ip",4)
    assert endian["interpretation"]=="SOURCE_ADVANCED_ID"
    assert endian["advanced_source_title"]=="EndianCell6"
    assert not endian["original_translation_verified"]
    hf=image.preview_source_field("adc",4,adc=1)
    assert hf["advanced_source_title"]=="10 кГц"
    report=image.report()
    assert report["sha256"]==hashlib.sha256(payload).hexdigest()
    assert report["original_register_addr_to_byte_offset"]=="address * 2"
    assert report["snapshot_is_live_device_verified"] is False
    assert report["device_writes_allowed"] is False
    assert "data" not in repr(image) # prevent accidental raw dump


def test_float32_raw_bits_not_recomputed_and_unknown_type_not_guessed():
    payload=bytearray(512)
    put_u32(payload,0x20,0x80000000) # exact -0.0 bit pattern
    put_u32(payload,0x04,0x01020304) # source IPv4 type, not decoded
    image=LocalRegisterImage.from_bytes(bytes(payload))
    info=image.preview_source_field("calib",0)
    assert image.read_u32(0x20)==0x80000000
    assert info["raw_u32"]=="0x80000000"
    assert info["interpretation"]=="SOURCE_FLOAT32_STORAGE"
    ip=image.preview_source_field("ip",0)
    assert ip["interpretation"]=="UNKNOWN_FORMAT"
    assert ip["raw_u32"]=="0x01020304"
    assert "ipv4" not in repr(ip).lower()
    put_u32(payload,0x22,0x7FC00001)
    img=LocalRegisterImage.from_bytes(bytes(payload))
    assert img.preview_source_field("calib",1)["float32"]=="non-finite"


def test_source_wifi_password_never_leaks_from_local_register_blob():
    raw=bytearray(512)
    raw[0x60*2:0x60*2+16]=b"ultra-private-key"
    img=LocalRegisterImage.from_bytes(bytes(raw))
    result=img.preview_source_field("ip",14)
    assert result["raw_value"]=="REDACTED"
    assert "private" not in repr(result)
    assert "raw_u32" not in result
    ssid=img.preview_source_field("ip",13)
    assert ssid["raw_value"]=="NOT_DECODED"


def test_source_bitfield_32_bit_and_zero_mask_edge_cases():
    raw=0xDEADBEEF
    assert extract_source_advanced_bits(raw,0,0)==raw
    assert extract_source_advanced_bits(raw,32,0)==raw
    assert extract_source_advanced_bits(0xAA55,4,4)==0x5
    assert extract_source_advanced_bits(0xFFFFFFFF,3,29)==7
    assert extract_source_advanced_bits(0xFFFFFFFF,1,31)==1
    for a,b,c in ((-1,1,0),(2**32,1,0),(True,1,0),
                  (0,33,0),(0,8,25),(0,4,-1),(0,4,32),
                  (0,True,0),(0,1,False)):
        with pytest.raises(ValueError):
            extract_source_advanced_bits(a,b,c)


def test_bounded_explicit_raw_input_denies_unsupported_images():
    for raw in (None,bytearray(4),b"ab",b"abcdz",
                bytes(MAX_LOCAL_REGISTER_IMAGE_BYTES+2)):
        with pytest.raises(ValueError):
            LocalRegisterImage.from_bytes(raw)
    img=LocalRegisterImage.from_bytes(bytes(512))
    for address in (-2,1,0x10000,True,"0x10",256):
        with pytest.raises(ValueError):
            img.read_u32(address)
    for section,row,adc in (("ip",15,None),("calib",-1,None),
                            ("adc",0,9),("bad",0,None)):
        with pytest.raises((ValueError,IndexError)):
            img.preview_source_field(section,row,adc=adc)


def test_generated_source_enum_ids_not_fabricated():
    by_key={e.kind:e for e in SOURCE_ENUM_CONSTRUCTORS}
    assert {k:v.source_entry_count for k,v in by_key.items()}=={
        "num_groups":2,"option":4,"wifi_mode":3,"alarm_band":4}
    assert all(not item.source_ids_recovered for item in by_key.values())
    assert all(not item.uses_composite for item in by_key.values())
