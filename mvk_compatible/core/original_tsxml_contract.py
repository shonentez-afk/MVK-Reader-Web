"""Stage111Z.21: original-MVKView TSXML metadata contract (read-only).

Source-backed static facts:
  _Unit125.pas 00806A8C..00807111: per-channel TSXML writer.
  00806FF8 DataLength is TFileStream.Size in BYTES; 0080703B offset=0.
  00806FCE Single for ADC0..7; 00806F68 Byte for >=8 (Count).
  00806964..00806985: ADC gain from TMvkCellList.GetFloatByAddr(0E).
  _Unit128.pas 0084622E..0084623F StrToFloat gain to Single,
  00846516/00846522 ViewedFileIsNormalized 1/0 by fallback,
  0084655B..0084655E stored gain -> TMvkChannelStorage.FRange.
  _Unit115.pas 007D23B7..007D23E5 f32 ApplyRange multiply.

Metadata validates provenance and identifies potential decoder paths.
It does NOT prove that an archived float32 buffer is already calibrated,
infer original live channel state, nor alter its samples without a paired
original runtime reference.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import xml.etree.ElementTree as ET

import numpy as np

ORIGINAL_TSXML_SOURCE="MVKVIEW_IDR_ORIGINAL_TSXML_WRITER_AND_READER"
GAIN_SOURCE="ORIGINAL_TSXML_GAIN_FROM_CELL_ADDR_0E_STATIC_ONLY"
ORIGINAL_WRITER_FIELDS=(
    "FrequencyPerChannel","DataFileName","ChannelsQuantity",
    "ChannelNumber","ChannelFrequency","Units","RealDataType",
    "DataLength","DataOffset","InternalChannelGain"
)
_SAFE_NAME=re.compile(r"^(?:\.[\\/])?([^\\/:\x00-\x1f]+)$")


@dataclass(frozen=True)
class OriginalTsxmlContract:
    sample_rate_hz: int
    data_type: str
    sample_width_bytes: int
    data_offset_bytes: int
    data_length_bytes: int
    channel_number: int | None
    channel_units_text: str | None
    file_name_declared: str | None
    internal_gain_single: float | None
    gain_loader_branch: str
    # FRange can be inferred only at the STATIC loader assignment, never
    # as independently verified physical calibration for this user's BIN.
    original_f_range_single_candidate: float | None
    source_meta_complete: bool
    original_writer_offset_zero: bool
    original_writer_gain_addr_0e_static: bool
    original_bin_data_domain_verified: bool=False
    physical_units_verified: bool=False
    original_runtime_gain_verified: bool=False


def _one(parent: ET.Element, tag: str, *, required=False)->str | None:
    hits=parent.findall(tag)
    if len(hits)>1:
        raise ValueError(f"TSXML содержит повторяющееся поле {tag}")
    if not hits:
        if required:raise ValueError(f"В TSXML отсутствует {tag}")
        return None
    val=(hits[0].text or "").strip()
    if not val:
        if required:raise ValueError(f"TSXML содержит пустое поле {tag}")
        return None
    return val


def _whole(text:str,field:str,*,minimum=0,maximum=10**9)->int:
    if not re.fullmatch(r"[0-9]+",text):
        raise ValueError(f"TSXML {field} должен быть целым без знака")
    value=int(text)
    if not minimum<=value<=maximum:
        raise ValueError(f"TSXML {field} вне допустимого диапазона")
    return value


def inspect_original_tsxml(
    xml_bytes:bytes, *, actual_bin_filename:str,
    max_data_bytes:int=40_000_000,
) -> OriginalTsxmlContract:
    """Validate both original full CP1251 and minimal read-only TSXML schema.

    Original's DataLength is bytes, not count of float32 samples.
    DataFileName is a label only, NEVER a path to follow.
    """
    if not xml_bytes or len(xml_bytes)>64_000:
        raise ValueError("TSXML должен быть непустым файлом до 64 КБ")
    if b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
        raise ValueError("TSXML с DTD/ENTITY не поддерживается")
    try:
        root=ET.fromstring(xml_bytes)
    except (ET.ParseError,LookupError,ValueError) as exc:
        raise ValueError("TSXML: ошибка разбора XML/кодировки") from exc
    if root.tag!="MainRoot":
        raise ValueError("TSXML: ожидается MainRoot оригинального МВК")
    channels=root.findall("./Channels/Channel")
    if len(channels)!=1:
        raise ValueError("TSXML: ожидается ровно один Channels/Channel")
    channel=channels[0]
    if channel.attrib.get("Index") not in (None,"0"):
        raise ValueError("TSXML: Channel Index должен быть 0")
    quantity=_one(root,"ChannelsQuantity")
    if quantity is not None and quantity!="1":
        raise ValueError("TSXML: ChannelsQuantity должен быть 1")

    dtype=_one(channel,"RealDataType",required=True)
    if dtype not in ("Single","Byte"):
        raise ValueError("TSXML: поддержаны только исходные Single или Byte")
    width=4 if dtype=="Single" else 1
    length=_whole(_one(channel,"DataLength",required=True),"DataLength",
                  minimum=1,maximum=max_data_bytes)
    offset=_whole(_one(channel,"DataOffset",required=True),"DataOffset",
                  maximum=max_data_bytes+4096)
    if length%width:
        raise ValueError("TSXML: DataLength не кратен размеру исходного типа")
    fs=_whole(_one(channel,"ChannelFrequency",required=True),
              "ChannelFrequency",minimum=1,maximum=1_000_000)
    root_fs=_one(root,"FrequencyPerChannel")
    if root_fs is not None and _whole(root_fs,"FrequencyPerChannel",
                                      minimum=1,maximum=1_000_000)!=fs:
        raise ValueError("TSXML: FrequencyPerChannel не совпадает с ChannelFrequency")

    name=_one(root,"DataFileName")
    if name is not None:
        name_match=_SAFE_NAME.fullmatch(name)
        if not name_match or name_match.group(1)!=actual_bin_filename:
            raise ValueError(
                "TSXML: DataFileName не соответствует выбранному BIN "
                "(запрещён другой файл или каталог)")
    ch=_one(channel,"ChannelNumber")
    channel_number=(
        None if ch is None else
        _whole(ch,"ChannelNumber",minimum=1,maximum=32))
    unit=_one(channel,"Units")
    if unit is not None and (len(unit)>40 or any(ord(c)<32 for c in unit)):
        raise ValueError("TSXML: некорректные Units")
    # Original Byte counter sidecars explicitly contain Units=Count. Do not
    # assume Float32 accelerometry or reinterpret counter bytes as Single.
    if dtype=="Byte" and unit not in (None,"Count"):
        raise ValueError("TSXML: для Byte ожидались счётные Units=Count")

    gain_text=_one(channel,"InternalChannelGain")
    gain=None
    branch="FALLBACK_DEFAULTCONFIG_GAIN_MISSING_UNVERIFIED"
    f_range=None
    if gain_text is not None:
        try:unrounded=float(gain_text)
        except ValueError as exc:
            raise ValueError("TSXML: InternalChannelGain не число") from exc
        if not math.isfinite(unrounded):
            raise ValueError("TSXML: InternalChannelGain NaN/Inf")
        with np.errstate(over="ignore",under="ignore",invalid="ignore"):
            gain=float(np.float32(unrounded))
        if not math.isfinite(gain):
            raise ValueError("TSXML: InternalChannelGain вне диапазона Single")
        if gain>0:
            branch="DECLARED_POSITIVE_NO_APPLY_RANGE_SOURCE_BRANCH"
            f_range=gain
        else:
            branch="FALLBACK_DEFAULTCONFIG_RANGE_NOT_AVAILABLE"
            # Original loader may read DefaultConfig.txt, and the numeric
            # fallback value is unknown. Never multiply the BIN by zero here.
    complete=(
        all(_one(root,n) is not None for n in (
            "FrequencyPerChannel","DataFileName","ChannelsQuantity"))
        and all(_one(channel,n) is not None for n in (
            "ChannelNumber","ChannelFrequency","Units","RealDataType",
            "DataLength","DataOffset","InternalChannelGain"))
        and channel.attrib.get("Index")=="0"
    )
    return OriginalTsxmlContract(
        sample_rate_hz=fs,data_type=dtype,
        sample_width_bytes=width,
        data_offset_bytes=offset,data_length_bytes=length,
        channel_number=channel_number,channel_units_text=unit,
        file_name_declared=name,internal_gain_single=gain,
        gain_loader_branch=branch,original_f_range_single_candidate=f_range,
        source_meta_complete=complete,original_writer_offset_zero=(offset==0),
        original_writer_gain_addr_0e_static=(gain is not None),
    )
