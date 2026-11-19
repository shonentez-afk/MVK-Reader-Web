"""Original TMvkCellList.GetValueText 30-type dispatch — source map, not oracle.

Three private sources were checked together: _Unit115.pas:007CE6E4,
mvk_idr(1).sqlite function/call graph, and mvkview.idp type locations.

Every original type 0..29 routes through this exact table, but those
branches call private formatting functions which still need Win32 runtime
comparison. Never replace vendor TLanguage, alarm enum, date or bitfield
by arbitrary Python formatting and label it original GetValueText.

No Delphi private source, FIR data, firmware or RAW bytes live here.
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass

SOURCE_DISPATCH="TMVKCELL_LIST_GETVALUETEXT_007CE6E4_SOURCE_MAP_V1"
# Source jump table at 007CE726 (30 type selectors) and 007CE744
# (case-index to branch address), in the original exact table order.
_TYPE_TO_CASE=(
    1,2,3,4,6,7,8,8,9,9,10,9,5,9,9,8,
    12,12,12,12,12,12,12,12,13,13,13,13,11,10,
)
_CASE_TO_BRANCH=(
    "007CE96C","007CE77C","007CE799","007CE7AC",
    "007CE7C3","007CE7F0","007CE8D4","007CE8E7",
    "007CE8FC","007CE90C","007CE91F","007CE92F",
    "007CE93F","007CE95B",
)
assert len(_TYPE_TO_CASE)==30 and len(_CASE_TO_BRANCH)==14
_HEX=re.compile(r"[0-9a-f]{8}\Z")


@dataclass(frozen=True)
class SourceGetValueTextCandidate:
    source_type: int
    original_dispatch_case: int
    original_branch_address: str
    raw_dword_le_hex: str | None
    candidate_text: str
    raw_source_f32: float | None
    source_values_available: bool
    original_delphi_text_parity_verified: bool = False
    original_tlanguage_parity_verified: bool = False


def source_getvalue_dispatch_case(source_type:int)->tuple[int,str]:
    if type(source_type) is not int or not 0<=source_type<30:
        raise ValueError("Original GetValueText requires type 0..29")
    case=_TYPE_TO_CASE[source_type]
    return case,_CASE_TO_BRANCH[case]


def source_getvalue_text_candidate(
    source_type:int, raw_le_hex:str|None,
    *,data_pointer_known_absent:bool=False,
)->SourceGetValueTextCandidate:
    """Decode *only* the source-confirmed raw numeric type-0 preview.

    Original GetValueText returns '####' when TMvkCellList.Data=nil
    (007CF4A4); an unreceived/half-received DWORD is *not* evidence
    that Delphi Data pointer is nil, so it stays '—', not '####'.
    """
    case,addr=source_getvalue_dispatch_case(source_type)
    if type(data_pointer_known_absent) is not bool:
        raise ValueError("Invalid original TMvkCellList.Data proof")
    if data_pointer_known_absent:
        if raw_le_hex is not None:
            raise ValueError("Missing source Data pointer cannot have a raw DWORD")
        return SourceGetValueTextCandidate(
            source_type,case,addr,None,"####",None,False)
    if raw_le_hex is None:
        return SourceGetValueTextCandidate(
            source_type,case,addr,None,"—",None,False)
    if not isinstance(raw_le_hex,str) or not _HEX.fullmatch(raw_le_hex):
        raise ValueError("Source GetValueText DWORD must be little-endian hex")
    raw=bytes.fromhex(raw_le_hex)
    numeric=None
    if source_type==0:
        # 007CE77C reads a Float32; the private 007B2090 applies
        # FormatSpec, locale and rounding in the ORIGINAL.
        numeric=float(struct.unpack("<f",raw)[0])
        if not math.isfinite(numeric):
            return SourceGetValueTextCandidate(
                source_type,case,addr,raw_le_hex,"—",None,False)
        shown=f"{numeric:.9g} (RAW)"
    else:
        shown=f"0x{int.from_bytes(raw,'little'):08X} (RAW type {source_type})"
    return SourceGetValueTextCandidate(
        source_type,case,addr,raw_le_hex,shown,numeric,True,
    )


def source_getvalue_router_provenance()->dict:
    return {
        "schema":SOURCE_DISPATCH,
        "original_type_count":len(_TYPE_TO_CASE),
        "original_unique_formatter_branches":len(set(_TYPE_TO_CASE)),
        "original_get_value_text_parser_1_to_1_verified":False,
        "original_tlanguage_parity_verified":False,
        "original_win32_numeric_rounding_verified":False,
        "route_table_complete_for_type_0_to_29":True,
        "supported_numeric_preview_only_type_0":True,
        "unsupported_types_remain_raw_not_fabricated":True,
    }
