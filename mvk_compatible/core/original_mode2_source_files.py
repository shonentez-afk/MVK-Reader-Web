"""Source-backed PageFile output and TSXML schema for original Mode2.

Source triangulation (private, NOT shipped): mvkview.idp +
Projects.7z (_Unit114/_Unit115/_Unit125/_Unit128.pas, mvkform.dfm) +
mvk_idr(1).sqlite. _Unit125:00806A8C writes TSXML on file close;
00809475 writes channel filenames; 00809880 writes VALUES-yyyy...csv.
These functions do NOT overwrite original RAW and cannot certify missing
operator UI metadata, the original Win32 timestamp or GetValueText.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
import math
import re

_ALLOWED_RATES=frozenset((512,2048,8192,32768,65536))
_SOURCE_NAME_TSFORMAT="%Y-%m-%d--%H-%M-%S"
_XML_ENCODING="windows-1251"
# Original sub_007B1FA4 admits Cyrillic U+0410..U+044F and safe
# punctuation, not only ASCII. Do not confuse valid Russian device labels
# with unsafe directory traversal.
_SAFE_PATH=re.compile(r"[A-Za-z0-9_\-. #$()А-Яа-я]{1,240}\Z")
# _Unit114.pas:007B1FA4; last branch admits Cyrillic U+0410..U+044F.
_ALLOWED_OLD_PUNCT=frozenset(" #$()-")


def delphi_file_part(value:str)->str:
    """Replicate character filtering, *not* an invented filesystem slug.

    Every disallowed UTF-16 code unit becomes underscore, as in
    sub_007B1FA4. It intentionally replaces dots and underscores.
    Never pass an untrusted root/path into this source filename formatter.
    """
    if not isinstance(value,str) or len(value)>180:
        raise ValueError("Original PageFile name text is missing/oversized")
    result=[]
    for ch in value:
        cp=ord(ch)
        result.append(ch if (
            ch in _ALLOWED_OLD_PUNCT or
            "0"<=ch<="9" or "A"<=ch<="Z" or "a"<=ch<="z" or
            0x410<=cp<=0x44F
        ) else "_")
    return "".join(result)


def source_data_filename(*, device:str, channel_label:str,
                         when:datetime, user_prefix:str="")->str:
    """Original 00809557..008095D1 pattern.

    Form chooses a prefix and a displayed device name and the appends
    a channel label + local yyyy-mm-dd--hh-nn-ss. Caller MUST supply
    real values from PageFile; these are not guessed from an IP.
    """
    if not isinstance(when,datetime) or when.tzinfo is None:
        raise ValueError("Original timestamp needs an explicit timezone")
    device_part=delphi_file_part(device)
    channel_part=delphi_file_part(channel_label)
    prefix_part=delphi_file_part(user_prefix)
    if not device_part or not channel_part:
        raise ValueError("Original PageFile device/channel label absent")
    name=(prefix_part+device_part+"-"+channel_part+"-"+
          when.strftime(_SOURCE_NAME_TSFORMAT)+".bin")
    if len(name)>240 or "/" in name or "\\" in name:
        raise ValueError("Source PageFile basename too long")
    return name


def source_values_filename(*, prefix:str, when:datetime)->str:
    if not isinstance(when,datetime) or when.tzinfo is None:
        raise ValueError("Original VALUES time needs a timezone")
    token=delphi_file_part(prefix)
    if not token:
        raise ValueError("Original VALUES prefix unavailable")
    return token+"VALUES-"+when.strftime(_SOURCE_NAME_TSFORMAT)+".csv"


def _xml_text(value:str)->str:
    if not isinstance(value,str) or len(value)>250 or any(
            ord(c)<32 for c in value):
        raise ValueError("Original TSXML invalid device/channel/units text")
    if "&" in value or "<" in value or ">" in value:
        # Delphi emits names without XML escaping (an original edge bug).
        # We do NOT write malformed XML; reject such unverified names.
        raise ValueError("Original TSXML unsafe unescaped name")
    value.encode("cp1251")
    return value


def _rate(value:int)->int:
    if type(value) is not int or value not in _ALLOWED_RATES:
        raise ValueError("Unverified original sample frequency")
    return value


def _float_text(value:float)->str:
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError("Invalid original gain/FRange")
    # Delphi writes Float32 textual gain through _Unit114:007B2090.
    # Deterministic decimal fallback is a STRUCTURAL reproduction only.
    return format(float(value),".9g")


def build_original_tsxml_compatible(
        *, channel:int, binary_basename:str,
        size_bytes:int, rate_hz:int, local_time:datetime,
        device_label:str, channel_label:str,
        adc_units:str|None=None, adc_gain:float|None=None,
)->tuple[bytes,dict]:
    """Original TSXML field order / type / byte-length / timing semantics.

    Returns portable Windows-1251 bytes and a mandatory limitations
    receipt. Never reports exact original Delphi byte parity.
    """
    if type(channel) is not int or not 1<=channel<=10:
        raise ValueError("Source TSXML channel must be ADC1..8 or TACH1..2")
    if (not isinstance(binary_basename,str) or
            not _SAFE_PATH.fullmatch(binary_basename) or
            binary_basename.startswith(".") or ".." in binary_basename or
            not binary_basename.endswith(".bin")):
        raise ValueError("Source TSXML must reference an existing local BIN")
    if type(size_bytes) is not int or size_bytes<0 or size_bytes>2**32:
        raise ValueError("Source TSXML length unavailable")
    tach=channel>=9
    if not tach and size_bytes%4:
        raise ValueError("Source ADC Float32 payload truncated")
    rate=_rate(rate_hz)
    if not isinstance(local_time,datetime) or local_time.tzinfo is None:
        raise ValueError("Missing original TSXML local time")
    label=_xml_text(device_label)+"-"+_xml_text(channel_label)
    if tach:
        if adc_gain is not None or adc_units is not None:
            raise ValueError("TACH uses original fixed Byte/Count/1 metadata")
        datatype="Byte"; units="Count";gain=1.0;unit_known=True;gain_known=True
    else:
        datatype="Single"
        units=_xml_text(adc_units) if adc_units is not None else ""
        gain=_float_text(adc_gain) if adc_gain is not None else "1"
        if isinstance(gain,float):gain=_float_text(gain)
        unit_known=adc_units is not None
        gain_known=adc_gain is not None
    gain_text=_float_text(gain) if isinstance(gain,(int,float)) else gain
    ms=(Decimal(size_bytes)*Decimal(1000)/
        (Decimal(rate)*(Decimal(1) if tach else Decimal(4))))
    duration=format(ms.quantize(Decimal("0.01"),rounding=ROUND_HALF_EVEN),"f")
    # Actual original String.DateTime calls FormatDateTime on the local
    # machine clock. Capture-end UTC is NOT an interchangeable source.
    # The caller must carry which timestamp it supplied in provenance.
    stamp=local_time.strftime("%m/%d/%Y %I:%M:%S %p")
    body=[
        '<?xml version="1.0" encoding="windows-1251"?>',
        "<MainRoot>",
        f"<DateTime>{stamp}</DateTime>",
        "<Culture>en-US</Culture>",
        '<From Units="ms">0</From>',
        f'<To Units="ms">{duration}</To>',
        "<ChannelsQuantity>1</ChannelsQuantity>",
        f"<FrequencyPerChannel>{rate}</FrequencyPerChannel>",
        f"<DataFileName>.\\{binary_basename}</DataFileName>",
        "<Channels>",
        '  <Channel Index="0">',
        f"    <ChannelName>{label}</ChannelName>",
        f"    <ChannelNumber>{channel}</ChannelNumber>",
        f"    <ChannelFrequency>{rate}</ChannelFrequency>",
        f"    <Units>{units}</Units>",
        f"    <RealDataType>{datatype}</RealDataType>",
        f"    <DataLength>{size_bytes}</DataLength>",
        "    <DataOffset>0</DataOffset>",
        f"    <InternalChannelGain>{gain_text}</InternalChannelGain>",
        "  </Channel>",
        "</Channels>",
        "</MainRoot>",
    ]
    encoded=("\r\n".join(body)+"\r\n").encode("cp1251")
    ET.fromstring(encoded)
    return encoded,{
        "source":"IDR_00806A8C_TMVKTHREAD_TXML_SCHEMA",
        "channel":channel,"bytes":size_bytes,"rate_hz":rate,
        "duration_ms":duration,"real_data_type":datatype,
        "channel_units":units,"gain_text":gain_text,
        "units_from_original_cell_text_verified":unit_known,
        "gain_from_original_frange_verified":gain_known,
        "original_file_naming_verified":False,
        "original_runtime_clock_verified":False,
        "original_delphi_tsxml_byte_parity_verified":False,
        "source_xml_structure_and_byte_length_verified":True,
        "sha256":sha256(encoded).hexdigest(),
    }


def write_verified_source_tsxml_sidecars(
        target:Path|str, *, live_proof:dict,
        source_run_end_utc:str,
        window_options:dict[int,object]|None=None,
)->list[dict]:
    """One SIDE-CAR per independently verified on-receive Go file.

    No unknown name/units/gain is silently treated as proved; they
    remain marked incomplete and are never called original Delphi XML.
    Sidecars live only in a NEW local export directory.
    """
    folder=Path(target)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Local source TSXML export folder missing")
    if not isinstance(live_proof,dict) or not isinstance(
            live_proof.get("verified_channel_files"),list):
        raise ValueError("Source TSXML needs independent live Go gate proof")
    if window_options is not None and not isinstance(window_options,dict):
        raise ValueError("Original PageFile TSXML options map invalid")
    window_options=window_options or {}
    when=datetime.fromisoformat(source_run_end_utc.replace("Z","+00:00"))
    if when.tzinfo is None:
        raise ValueError("Missing timezone for Go capture-end time")
    emitted=[]
    for proof in live_proof["verified_channel_files"]:
        if not isinstance(proof,dict):
            raise ValueError("Invalid checked Go file")
        name=proof["name"]
        size=proof["bytes"]
        channel=proof["channel"]
        number=proof.get("window",1 if not window_options else None)
        if type(number) is not int or not 1<=number<=8:
            raise ValueError("Original source TSXML missing Go DATA window")
        opts=window_options.get(number)
        if opts is not None and (
                type(getattr(opts,"write_tsxml",None)) is not bool or
                type(getattr(opts,"use_custom_name",None)) is not bool):
            raise ValueError("Original TSXML PageFile options invalid")
        if opts is not None and not opts.write_tsxml:
            emitted.append({
                "name":name,"channel":channel,"window":number,
                "sidecar_created":False,
                "reason":"ORIGINAL_XML_CHECKBOX_OFF",
                "source_pagefile_checkbox_snapshot_verified":True})
            continue
        rates=proof.get("verified_packet_rates_hz")
        if not isinstance(rates,list) or len(rates)!=1:
            # Original format has a SINGLE frequency per file; a
            # rate transition must never be misrepresented by one Fs.
            emitted.append({
                "name":name,"channel":channel,"sidecar_created":False,
                "reason":"MULTIPLE_OR_UNKNOWN_SOURCE_FS"})
            continue
        path=folder/name
        if (path.is_symlink() or not path.is_file() or
                path.stat().st_size!=size or
                sha256(path.read_bytes()).hexdigest()!=proof["sha256"]):
            raise ValueError("Selected native Go file changed before TSXML")
        kind=("ADC" if channel<=8 else "TACH")
        label=f"{kind}{channel if channel<=8 else channel-8}"
        custom=bool(opts is not None and opts.use_custom_name
                    and isinstance(getattr(opts,"custom_name",None),str)
                    and opts.custom_name.strip())
        device=opts.custom_name.strip() if custom else "MVK"
        xml,details=build_original_tsxml_compatible(
            channel=channel,binary_basename=name,size_bytes=size,
            rate_hz=rates[0],local_time=when,
            device_label=device,channel_label=label)
        sidecar=name+".tsxml"
        sidecar_path=folder/sidecar
        with sidecar_path.open("xb") as dest:
            dest.write(xml)
        emitted.append({
            "name":sidecar,"channel":channel,"sidecar_created":True,
            "bytes":len(xml),"timestamp_source":"GO_CAPTURE_END_UTC_NOT_DELPHI_LOCAL",
            "source_pagefile_checkbox_snapshot_verified":opts is not None,
            "source_pagefile_xml_requested":(
                opts.write_tsxml if opts is not None else None),
            "device_name_source":("OPERATOR_CBFILEMVKNAME" if custom
                                  else "PROVISIONAL_MVK_DEVICE_NAME"),
            "channel_name_source":"PROVISIONAL_ADC_TACH_LABEL",
            "source_raw_sha256":live_proof["source_raw_sha256"],
            **details,
        })
    return emitted
