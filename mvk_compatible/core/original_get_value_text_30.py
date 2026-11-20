"""Source-mapped TMvkCellList.GetValueText 30 types, unit metadata, Advanced.

Portable CANDIDATE only. Based on private _Unit114:007B2090, 007B2224,
007B22E4, 007B2390, 007B2428, 007B27CC, 007B28F8, 007B29D4,
007B2D98; _Unit115:007CE6E4, 007CF2FC, 007CF3A8, 007CF4A4,
007D0808; _Unit125:00804A30, 00804DEC, 00805040, 008053B8.
Layout/width corroborated with mvkview.idp and mvk_idr(1).sqlite.
Private source files and original TLanguage RCDATA are not distributed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import math
import struct
from typing import Mapping

from .original_config_idp_tables import (
    SOURCE_BYTES_PER_TYPE, source_type_description,
    SOURCE_SELECTOR_IDS, SOURCE_SELECTOR_PREFIXES,
)

SCHEMA = "MVK_SOURCE_GETVALUETEXT_30_FORMATTER_CANDIDATE_V1"
# _Unit115:007CE718/007CE71F, 30 exact source type indices.
TYPE_TO_CASE = (
    1,2,3,4,6,7,8,8,9,9,10,9,5,9,9,8,
    12,12,12,12,12,12,12,12,13,13,13,13,11,10,
)
CASE_BRANCH = (
    "007CE96C", "007CE77C", "007CE799", "007CE7AC",
    "007CE7C3", "007CE7F0", "007CE8D4", "007CE8E7",
    "007CE8FC", "007CE90C", "007CE91F", "007CE92F",
    "007CE93F", "007CE95B",
)
# _Unit125:0080250C constructs TLanguage keys Prefix+"Cell"+ID.
# GetTitleByID returns a hexadecimal parenthesized ID when unmapped.
ADVANCED = {
    "result_overload": ("Overload", (0,1), 0,1),
    "result_buffers": ("Buffers", (0,1,3,7), 4,3),
    "result_sensor_state": ("SensorState", (0,1,2,3), 10,2),
}
# Actual GetUnits is string stored in the cell at +0x1C (_Unit115:7CF2FC).
# _Unit125 constructor contains these literal Pascal strings; captions
# and language keys (TLanguage) are independent of units.
RESULT_UNITS = ("","","","В","м/с2","")
BAND_UNITS = ("м/с2","мм/с","мкм")
TACH_UNITS = ("Гц","Гц","","","","")
assert len(TYPE_TO_CASE)==len(SOURCE_BYTES_PER_TYPE)==30


@dataclass(frozen=True)
class SourceTextCandidate30:
    source_type: int
    source_case: int
    source_branch: str
    source_width_bytes: int
    text: str
    available: bool
    source_route_verified: bool = True
    original_win32_delphi_text_verified: bool = False
    original_tlanguage_verified: bool = False
    original_ansi_byte_parity_verified: bool = False


def live_get_units(group: str, index: int) -> str:
    if type(index) is not int or index < 0:
        raise ValueError("Invalid source GetUnits index")
    if group=="SPEC" and index<43:
        return "м/с2"
    if group=="RESULT" and index<6:
        return RESULT_UNITS[index]
    if group=="BAND" and index<24:
        return BAND_UNITS[index%3]
    if group=="TACH" and index<6:
        return TACH_UNITS[index]
    raise ValueError("Source GetUnits group/cell invalid")


def source_advanced_id(raw_uint32: int, kind: str) -> int:
    if type(raw_uint32) is not int or not 0<=raw_uint32<=0xffffffff:
        raise ValueError("Source Advanced requires one UInt32")
    if kind not in ADVANCED:
        raise ValueError("Unknown original Advanced cell kind")
    _,_,start,width=ADVANCED[kind]
    return (raw_uint32>>start)&((1<<width)-1)


def source_advanced_title_candidate(
    raw_uint32: int, kind: str, translations: Mapping[str,str] | None = None,
) -> str:
    """GetTitleByID structural result; no fabricated TLanguage originals.

    A local map may contain keys produced by source 0080250C; its values
    remain unverified until its authentic RCDATA provenance is established.
    """
    _,_,start,width=ADVANCED[kind]
    return source_advanced_title_by_source_list(
        raw_uint32,kind,bits=width,bit_start=start,
        composite=False,translations=translations)




def source_advanced_title_by_source_list(
    raw_uint32: int, selector_kind: str, *, bits: int,
    bit_start: int, composite: bool = False,
    translations: Mapping[str,str] | None = None,
) -> str:
    """Source TMvkAdvancedCell.GetTitleByID for ALL known original lists.

    _Unit115:007CF4F6 extracts source Bits/BitStart. _Unit115:007D0808
    handles simple lookup or UseCompositeTitle: match each ID when
    (ID & requested)==ID, join with '; ', return '---' if none.
    This is a structural candidate until the authentic RCDATA is present.
    """
    if type(raw_uint32) is not int or not 0<=raw_uint32<=0xffffffff:
        raise ValueError("Advanced source requires UInt32")
    if selector_kind not in SOURCE_SELECTOR_IDS:
        raise ValueError("Unknown original Advanced selector list")
    if (type(bits) is not int or type(bit_start) is not int
            or not 0<=bits<=32 or not 0<=bit_start<=31
            or (bits>0 and bits+bit_start>32)):
        raise ValueError("Advanced source bit field outside DWORD")
    if type(composite) is not bool:
        raise ValueError("Advanced composite flag must be Boolean")
    if translations is not None and not isinstance(translations,Mapping):
        raise ValueError("Untrusted local Advanced translations must be mapping")
    selected=((raw_uint32>>bit_start)&((1<<bits)-1)) if bits else raw_uint32
    prefix=SOURCE_SELECTOR_PREFIXES[selector_kind]
    ids=SOURCE_SELECTOR_IDS[selector_kind]
    def title(ident:int)->str:
        key=f"{prefix}Cell{ident}"
        label=translations.get(key) if translations is not None else None
        if label is None:
            return f"UNRESOLVED_ADVANCED_ID_{ident}"
        if (not isinstance(label,str) or not label or
                len(label)>2048 or any(ch in label for ch in "\r\n|")):
            raise ValueError("Unsafe local TLanguage title")
        return label
    if composite:
        parts=[title(ident) for ident in ids if (ident&selected)==ident]
        return "; ".join(parts) if parts else "---"
    if selected not in ids:
        return f"(0x{selected:08X})"
    return title(selected)

def _float32(raw: bytes, digits: int) -> str:
    """Delphi 007B2090 source *algorithm*, not certified FormatFloat.

    Source starts with 0., Float32-absolute multiplication by 10 until
    10^(digits-1), adding a decimal zero each time. It then FormatFloat's
    that pattern and trims trailing zeroes and the separator. Decimal's
    ties-even emulates a candidate Win32 rounding policy; exact x87
    FormatFloat/Win32 locale still require paired dynamic verification.
    """
    u=struct.unpack("<I",raw)[0]
    if u&0x7f800000==0x7f800000 and u&0x007fffff:
        return "NAN"
    x=struct.unpack("<f",raw)[0]
    if not math.isfinite(x):
        return "UNKNOWN_NONFINITE"
    if not x or digits<1:
        return "0"
    a=abs(x)
    places=0
    threshold=float(10**(digits-1))
    while a<threshold:
        a=struct.unpack("<f",struct.pack("<f",a*10.0))[0]
        places+=1
        if places>100:
            raise ValueError("Source float32 exponent overflow")
    with localcontext() as ctx:
        ctx.prec=200
        q=Decimal(1).scaleb(-places)
        d=Decimal.from_float(x).quantize(q,rounding=ROUND_HALF_EVEN)
        shown=format(d,"f")
    if "." in shown:
        shown=shown.rstrip("0").rstrip(".")
    return "0" if shown=="-0" else shown


def get_value_text_30(
    source_type: int, raw: bytes | None, *,
    format_spec: int = 4, data_pointer_known_absent: bool = False,
    windows_total_timezone_bias_minutes: int | None = None,
    windows_ansi_code_page: str | None = None,
    advanced_kind: str | None = None,
    local_advanced_translations: Mapping[str,str] | None = None,
    source_locale: str | None = None,
    advanced_source_bits: int | None = None,
    advanced_source_bit_start: int = 0,
    advanced_source_composite: bool = False,
) -> SourceTextCandidate30:
    """All 30 original type-to-formatter routes, source-sized and safe.

    Source 007CF3A8 passes FormatSpec=4. Unsupported language/Win32
    conditions remain UNKNOWN rather than guessed or default-zeroed.
    '####' is reserved for proven TMvkCellList.Data=nil, NOT stale TCP.
    """
    if type(source_type) is not int or not 0<=source_type<30:
        raise ValueError("Original GetValueText type must be 0..29")
    if type(format_spec) is not int or not 1<=format_spec<=16:
        raise ValueError("Source numeric formatter spec must be 1..16")
    if type(data_pointer_known_absent) is not bool:
        raise ValueError("Data pointer proof must be Boolean")
    if advanced_kind is not None and (
            source_type!=10 or advanced_kind not in SOURCE_SELECTOR_IDS):
        raise ValueError("Only source type 10 has a supported Advanced list")
    if source_locale is not None and (
            source_type!=10 or advanced_kind is None):
        raise ValueError("Source RU locale can only render an Advanced type-10 cell")
    if source_locale is not None and source_locale!="ru-ru":
        raise ValueError("Only the source-extracted ru-ru Advanced locale is available")
    if source_locale is not None and local_advanced_translations is not None:
        raise ValueError("Specify source locale OR external translations, never both")
    if source_locale=="ru-ru":
        from .original_ru_advanced_catalog import original_ru_advanced_translations
        local_advanced_translations=original_ru_advanced_translations(advanced_kind)
    if advanced_kind in ADVANCED and (advanced_source_bits is not None or
                                     advanced_source_bit_start!=0 or
                                     advanced_source_composite):
        raise ValueError("Known source Result Advanced fields fix Bits/Start and are not composite")
    if advanced_kind is None and (
            advanced_source_bits is not None or advanced_source_bit_start!=0 or
            advanced_source_composite):
        raise ValueError("Non-Advanced cell cannot set source Advanced bit metadata")
    if advanced_kind is not None and advanced_kind not in ADVANCED and (
            advanced_source_bits is None):
        raise ValueError("Other source Advanced lists require explicit Bits/Start")
    case=TYPE_TO_CASE[source_type]
    size=SOURCE_BYTES_PER_TYPE[source_type]
    def result(text:str, available:bool=True)->SourceTextCandidate30:
        return SourceTextCandidate30(source_type,case,CASE_BRANCH[case],
                                     size,text,available)
    if data_pointer_known_absent:
        if raw is not None:
            raise ValueError("Nil source Data pointer cannot hold raw bytes")
        return result("####",False)
    if raw is None:
        return result("UNKNOWN",False)
    if type(raw) is not bytes or len(raw)!=size:
        raise ValueError("Source cell requires the exact original type width")
    value=struct.unpack("<I",raw[:4])[0]
    if case==1:
        return result(_float32(raw[:4],format_spec))
    if case==2:
        return result(str(struct.unpack("<i",raw[:4])[0]))
    if case==3:
        return result(str(value))
    if case==4:
        if (type(windows_total_timezone_bias_minutes) is not int or
                not -1440<=windows_total_timezone_bias_minutes<=1440):
            return result("UNKNOWN_WIN32_TIMEZONE",False)
        stamp=(datetime(1970,1,1,tzinfo=timezone.utc)+
               timedelta(seconds=value)-
               timedelta(minutes=windows_total_timezone_bias_minutes))
        return result(stamp.strftime("%Y-%m-%d %H:%M:%S"))
    if case==5:
        return result(f"{value//3600:02d}:{(value//60)%60:02d}:{value%60:02d}")
    if case==6:
        return result(raw.hex().upper())
    if case==7:
        bits=[str(i) for i in range(32) if value&(1<<i)]
        return result(",".join(bits) if bits else "---")
    if case==8:
        return result(".".join(str((value>>k)&0xff) for k in (24,16,8,0)))
    if case==9:
        # _Unit114:007B2D98 uses @UStrFromChar per input ANSI byte, not UTF-8.
        data=raw.split(b"\x00",1)[0]
        if any(b>=128 for b in data):
            if windows_ansi_code_page not in ("cp1251","cp1252"):
                return result("UNKNOWN_WIN32_ANSI_CODEPAGE",False)
            return result(data.decode(windows_ansi_code_page))
        return result(data.decode("ascii"))
    if case==10:
        if advanced_kind in ADVANCED:
            return result(source_advanced_title_candidate(
                value,advanced_kind,local_advanced_translations))
        if advanced_kind is not None:
            return result(source_advanced_title_by_source_list(
                value,advanced_kind,bits=advanced_source_bits,
                bit_start=advanced_source_bit_start,
                composite=advanced_source_composite,
                translations=local_advanced_translations))
        return result(f"0x{value:08X}")
    if case==11:
        return result(f"0x{value&0xffff:04X}")
    if case==12:
        width=4*(source_type-16+1)
        return result("".join(
            ("1" if value&(1<<i) else "0")+(" " if i%4==3 else "")
            for i in range(width)))
    if case==13:
        count=source_type-24+1
        return result("".join(f"{b:02X} " for b in raw[:count]))
    raise AssertionError("Source switch case unexpectedly unmapped")


def source_getvalue_30_provenance() -> dict:
    return {
        "schema":SCHEMA,
        "original_type_count":30,
        "source_used_formatter_branches":len(set(TYPE_TO_CASE)),
        "source_type_widths_verified_from_idp":True,
        "source_get_units_from_list_metadata":True,
        "advanced_local_resource_required_for_original_titles":True,
        "original_ru_advanced_labels_from_extracted_resource":41,
        "original_ru_advanced_selector_lists":10,
        "original_delphi_compatibility_verified":False,
        "original_win32_formatfloat_verified":False,
        "original_ansi_csv_byte_parity_verified":False,
    }
