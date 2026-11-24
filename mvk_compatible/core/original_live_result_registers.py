"""Original Mode2 PageStatus LIVE: 15 modes from real PARAM register words.

PRIVATE original source checked together:
 _Unit125.pas original TMvkCellList ADC/TACH constructors,
 _Unit128.pas original 008475F5 PageStatus 15-mode switch,
 mvkview.idp and mvk_idr.sqlite cross-indexed call graph.

All values are from Go's SINGLE receive-only RegisterImage, as exact
little-endian 32-bit words with an independent Valid bit for BOTH words.
GetValueText, control alert severity, vendor peak units, RPM and Win32
Delphi runtime/pixel parity are NOT asserted by this model. No device I/O.
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass

from .original_pagestatus_source import (
    MODE_NAMES, TACH_FIELDS, StatusTable, UNAVAILABLE,
)
from .original_status_workbench import (
    MODE_GRID, OriginalStatusProjection, SOURCE_FREQUENCIES,
)

SCHEMA="MVK_SOURCE_LIVE_PAGESTATUS_RAW_BANKS_V1"
from .original_local_tach_latch import SCHEMA as LOCAL_TACH_SCHEMA
_HEX=re.compile(r"[0-9a-f]{8}\Z")
_FLOAT_FIELD_KEYS=("bands_43_raw_f32_le","rms_24_raw_f32_le",
                   "peak_24_raw_f32_le","peak_peak_24_raw_f32_le")
_EXPECTED_COUNTS=(43,24,24,24)
MAX_U64=(1<<64)-1


def _counter(value,name):
    if type(value) is not int or not 0<=value<=MAX_U64:
        raise ValueError("Source PageStatus invalid "+name)
    return value


def _word(value,name):
    if value is None:
        return None
    if not isinstance(value,str) or not _HEX.fullmatch(value):
        raise ValueError("Source PageStatus invalid raw LE DWORD "+name)
    return value


def _word_array(value,size,name):
    if not isinstance(value,list) or len(value)!=size:
        raise ValueError("Source PageStatus wrong count "+name)
    return tuple(_word(v,name) for v in value)


def parse_live_result_registers(status:dict)->dict|None:
    """Reject partial, foreign or fabricated source bank snapshots.

    The file validator already authenticates the run identity, TCP/status
    progression and freshness. This strictly binds EVERY original register
    address range to a present, individually valid 32-bit word.
    """
    if not isinstance(status,dict):
        raise ValueError("Source PageStatus must come from a live status")
    data=status.get("source_live_page_status_banks")
    if data is None:
        return None  # old Go receiver: explicitly UNKNOWN, never invention
    if not isinstance(data,dict) or data.get("schema")!=SCHEMA:
        raise ValueError("Source PageStatus wrong register bank schema")
    accepted=_counter(data.get("accepted_param_frames"),
                      "accepted PARAM update count")
    rx=_counter(status.get("source_rx_nonempty_parameter_frames"),
                "received PARAM count")
    if accepted>rx:
        raise ValueError("Source PageStatus updates exceed received PARAM")
    socket=_counter(data.get("tcp_connection_count"),"socket number")
    if socket!=_counter(status.get("source_tcp_connection_count"),
                        "source TCP connection count"):
        raise ValueError("Source PageStatus results came from another TCP")
    if (data.get("original_get_value_text_parity_verified") is not False or
            data.get("original_delphi_runtime_parity_verified") is not False):
        raise ValueError("Source PageStatus: unverified Delphi text/runtime parity asserted")
    local_schema=data.get("source_local_tach_projection_schema")
    if local_schema not in (None,LOCAL_TACH_SCHEMA):
        raise ValueError("Source PageStatus: unknown local TACH projection")
    incoming_adc=data.get("adc")
    incoming_tach=data.get("tach")
    if (not isinstance(incoming_adc,list) or len(incoming_adc)!=8 or
            not isinstance(incoming_tach,list) or len(incoming_tach)!=2):
        raise ValueError("Source PageStatus requires all 8 ADC + 2 TACH slots")
    adcs=[]
    tachs=[]
    observed=0
    for index,raw in enumerate(incoming_adc):
        base=0x2000+index*0x200
        if (not isinstance(raw,dict) or
                type(raw.get("adc")) is not int or raw["adc"]!=index+1 or
                type(raw.get("base_word")) is not int or raw["base_word"]!=base):
            raise ValueError("Source PageStatus ADC source register base/order mismatch")
        cleaned={"adc":index+1,"base_word":base}
        for key,size in zip(_FLOAT_FIELD_KEYS,_EXPECTED_COUNTS):
            cleaned[key]=_word_array(raw.get(key),size,key)
            observed+=sum(v is not None for v in cleaned[key])
        for key,size in (("control_8_values_raw_f32_le",8),
                         ("control_8_status_raw_u32_le",8)):
            cleaned[key]=_word_array(raw.get(key),size,key)
            observed+=sum(v is not None for v in cleaned[key])
        # From source _Unit125:00804A30: six ResultAdcCellList
        # entries, including three advanced bit slices of +0x120.
        # Older Go receipts have no explicit six, and must stay UNKNOWN.
        six_raw=raw.get("result_adc_six_raw_dwords_le")
        six=(_word_array(six_raw,6,"result ADC six") if six_raw is not None
             else (None,)*6)
        cleaned["result_adc_six_raw_dwords_le"]=six
        if len(set(six[:3]))!=1:
            raise ValueError("Source PageStatus advanced ResultADC6 source words differ")
        # Only the last three are new unique words. First three
        # reference the already-counted +0x120 sensor status.
        observed+=sum(value is not None for value in six[3:])
        cleaned["sensor_status_raw_u32_le"]=_word(
            raw.get("sensor_status_raw_u32_le"),"sensor status")
        observed+=cleaned["sensor_status_raw_u32_le"] is not None
        if (six_raw is not None and
                six[0]!=cleaned["sensor_status_raw_u32_le"]):
            raise ValueError("Source PageStatus ResultADC6 sensor status overlaps incorrectly")
        adcs.append(cleaned)
    for index,raw in enumerate(incoming_tach):
        base=0x3000+index*0x100
        if (not isinstance(raw,dict) or
                type(raw.get("tach")) is not int or raw["tach"]!=index+1 or
                type(raw.get("base_word")) is not int or raw["base_word"]!=base):
            raise ValueError("Source PageStatus TACH source register base/order mismatch")
        values=_word_array(raw.get("source_field_0_2_4_6_8_fe_raw_le"),6,
                           "TACH source register fields")
        # Legacy wire +FE remains unknown. Only a source-local
        # projection with known written words can expose the live flag.
        mask=raw.get("source_local_tach_word_mask",0)
        if type(mask) is not int or not 0<=mask<=3 or (mask and local_schema!=LOCAL_TACH_SCHEMA):
            raise ValueError("Source PageStatus: invalid local TACH word mask")
        if mask and values[5] is not None:
            word=bytes.fromhex(values[5])
            if (mask&1 and word[:2] not in (b"\x00\x00",b"\x01\x00") or
                    mask&2 and word[2:]!=b"\x00\x00"):
                raise ValueError("Source PageStatus: invalid local TACH DWORD")
        if not mask:
            values=(*values[:5],None)
        observed+=sum(v is not None for v in values)
        tachs.append({"tach":index+1,"base_word":base,
                      "source_field_0_2_4_6_8_fe_raw_le":values,
                      **({"source_local_tach_word_mask":mask} if local_schema else {})})
    if accepted==0 and observed:
        raise ValueError("Source PageStatus values without a received PARAM")
    if status.get("phase") not in ("RECORDING","CONNECTING","VERIFYING","COMPLETED","REFUSED"):
        raise ValueError("Source PageStatus invalid transport phase")
    return {
        "schema":SCHEMA,
        "accepted_param_frames":accepted,
        "tcp_connection_count":socket,
        "adc":tuple(adcs),"tach":tuple(tachs),
        "known_complete_dwords":observed,
        "get_value_text_parity_verified":False,
        "original_delphi_runtime_parity_verified":False,
    }


def _raw_u32(word):
    return int.from_bytes(bytes.fromhex(word),"little") if word is not None else None


def _raw_f32(word):
    if word is None:
        return None
    value=struct.unpack("<f",bytes.fromhex(word))[0]
    if not math.isfinite(value):
        return None
    return float(value)


def _f32_text(word):
    value=_raw_f32(word)
    return f"{value:.9g} (RAW)" if value is not None else UNAVAILABLE


def _u32_text(word):
    value=_raw_u32(word)
    return f"0x{value:08X} (RAW)" if value is not None else UNAVAILABLE



def _source_ru_text(raw_le: str | None, kind: str, *,
                    advanced_kind: str | None = None,
                    bit_start: int = 0, composite: bool = False) -> str:
    """Source 007CE6E4 candidate on a VALID complete live PARAM DWORD.

    _Unit125:00805241/00805293 states AlarmState is Bits=8 Start=0;
    AlarmAlert is Bits=8 Start=8, UseCompositeTitle=1. Both use the
    same +0x132 register. This function does not infer state from AUX
    or from unseen data. All output remains Win32 Delphi CANDIDATE.
    """
    from .original_get_value_text_30 import get_value_text_30
    if raw_le is None:
        return UNAVAILABLE
    raw=bytes.fromhex(_word(raw_le,"source RU GetValueText"))
    if kind=="Float32":
        if _raw_f32(raw_le) is None:
            return UNAVAILABLE
        result=get_value_text_30(0,raw)
        return (result.text.replace(".",",") if result.available
                else UNAVAILABLE)
    if kind=="UInt32":
        result=get_value_text_30(2,raw)
        return result.text if result.available else UNAVAILABLE
    if kind=="Advanced" and advanced_kind in ("alarm_state","alarm_alert"):
        result=get_value_text_30(
            10,raw,source_locale="ru-ru",advanced_kind=advanced_kind,
            advanced_source_bits=8,advanced_source_bit_start=bit_start,
            advanced_source_composite=composite)
        return result.text if result.available else UNAVAILABLE
    raise ValueError("Source RU formatter has no proven cell type")


def source_live_status_projection(mode:int,banks:dict,*,source_ru_text:bool=False)->OriginalStatusProjection:
    """Strictly raw, validated source REGISTER values, NOT computed FFT.

    Mode0 uses the existing independent 15-system-register adapter.
    """
    if type(source_ru_text) is not bool:
        raise ValueError("Source live Russian text selection must be Boolean")
    if type(mode) is not int or not 1<=mode<=14:
        raise ValueError("Source LIVE result projection expects tcStatus 1..14")
    if not isinstance(banks,dict) or banks.get("schema")!=SCHEMA:
        raise ValueError("Source LIVE result projection requires checked banks")
    adcs=banks["adc"]
    tachs=banks["tach"]
    count=banks["known_complete_dwords"]
    if source_ru_text:
        header_note=(
            "LIVE · реальные полные PARAM DWORD из Go RegisterImage, "
            f"{count} валидных полей. Текст: исходные маршруты GetValueText "
            "и подтверждённые русские метки EXTLOCALIZATION. "
            "Это КАНДИДАТ исходного Delphi/Win32, НЕ byte parity; "
            "незавершённые/устаревшие регистры остаются «—». "
            "Порог тревоги и RPM не вычисляются.")
    else:
        header_note=(
            "LIVE · реальные PARAM DWORD из Go RegisterImage, проверен каждый "
            f"DWORD из двух принятых 16-битных слов; {count} валидных полей. "
            "Сырые Float32 и UInt32, НЕ исходный TMvkCellList.GetValueText. "
            "Порог/тревога/об/мин не интерпретируются. "
            "Исходный Win32/x87 паритет не подтверждён.")
    chart=None
    if mode==1:
        headers=("Контрольный регистр",*(f"АЦП{i}" for i in range(1,9)))
        rows=[]
        for j in range(8):
            addr=0x130+8*j
            if source_ru_text:
                rows.append((
                    f"Контроль {j+1} · Значение +0x{addr:03X}",
                    *(_source_ru_text(a["control_8_values_raw_f32_le"][j],
                                      "Float32") for a in adcs)))
                rows.append((
                    f"Контроль {j+1} · Состояние +0x{addr+2:03X}",
                    *(_source_ru_text(a["control_8_status_raw_u32_le"][j],
                                      "Advanced",advanced_kind="alarm_state",
                                      bit_start=0) for a in adcs)))
                rows.append((
                    f"Контроль {j+1} · Событие +0x{addr+2:03X}",
                    *(_source_ru_text(a["control_8_status_raw_u32_le"][j],
                                      "Advanced",advanced_kind="alarm_alert",
                                      bit_start=8,composite=True) for a in adcs)))
            else:
                rows.append((
                    f"Контроль {j+1} · value +0x{addr:03X}",
                    *(_f32_text(a["control_8_values_raw_f32_le"][j]) for a in adcs)))
                raw_status=tuple(
                    _u32_text(a["control_8_status_raw_u32_le"][j]) for a in adcs)
                rows.append((f"Контроль {j+1} · state +0x{addr+2:03X}",*raw_status))
                rows.append((f"Контроль {j+1} · alert +0x{addr+2:03X}",*raw_status))
        note=header_note+(" AlarmState: bits 0..7; AlarmAlert: bits 8..15,"
                          " составной текст через '; '. Оба читают один"
                          " полный +0x132 DWORD.")
    elif mode in (2,3,4):
        key=("rms_24_raw_f32_le","peak_24_raw_f32_le",
             "peak_peak_24_raw_f32_le")[mode-2]
        offset=(0x60,0xA0,0xE0)[mode-2]
        if source_ru_text:
            from .original_ru_csv_layout import source_ru_cell_title
        rows=tuple((
            (f"{source_ru_cell_title('BAND',i)} · +0x{offset+2*i:03X}"
             if source_ru_text else
             f"Измеренная полоса {i+1} · +0x{offset+2*i:03X}"),
            *((_source_ru_text(a[key][i],"Float32") if source_ru_text
               else _f32_text(a[key][i])) for a in adcs)
        ) for i in range(24))
        headers=("Исходное поле",*(f"АЦП{i}" for i in range(1,9)))
        note=header_note+" Названия 24 исходных полей не переведены; индекс/регистр точен."
    elif 5<=mode<=12:
        adc=mode-5
        word_array=adcs[adc]["bands_43_raw_f32_le"]
        values=tuple(_raw_f32(x) for x in word_array)
        if source_ru_text:
            from .original_ru_csv_layout import source_ru_cell_title
        rows=tuple((
            (f"{source_ru_cell_title('SPEC',i)} · +0x{2+2*i:03X}"
             if source_ru_text else
             f"{float(SOURCE_FREQUENCIES[i]):.9g} Гц · +0x{2+2*i:03X}"),
            (_source_ru_text(word_array[i],"Float32") if source_ru_text
             else _f32_text(word_array[i]))) for i in range(43))
        headers=("Полоса третьоктавы","Исходное Float32")
        if all(v is not None for v in values):
            chart=tuple(values)
        note=header_note+(
            " Все 43 реальные полосы готовы для графика." if chart is not None
            else " Не вся исходная полоса принята; график закрыт.")
    else:
        tach=mode-13
        raw=tachs[tach]["source_field_0_2_4_6_8_fe_raw_le"]
        offset=(0,2,4,6,8,0xFE)
        if source_ru_text:
            from .original_ru_csv_layout import source_ru_cell_title
        rows=tuple((
            (source_ru_cell_title("TACH",i) if source_ru_text else name),
            f"0x{0x3000+tach*0x100+offset[i]:04X}",
            (_source_ru_text(raw[i],field_type) if source_ru_text
             else (_f32_text(raw[i]) if field_type=="Float32"
                   else _u32_text(raw[i]))),
            field_type,
            unit or UNAVAILABLE,
        ) for i,(name,_original_offset,field_type,unit,_fresh) in enumerate(TACH_FIELDS))
        headers=("Оригинальный ключ","Регистр","RAW значение","Тип","Ед. по IDR")
        note=header_note+" TACH +0xFE скрыт без отдельной свежести."
    model=StatusTable(
        mode,MODE_NAMES[mode],tuple(headers),tuple(rows),note,
        chart,"SOURCE_ORIGINAL_LIVE_PARAM_REGISTER_WORDS_NOT_TEXT_PARITY")
    return OriginalStatusProjection(
        model,MODE_GRID[mode],chart is not None,None,None,None,
        provenance=("SOURCE_LIVE_8ADC_2TACH_RU_GETVALUETEXT_CANDIDATE"
                    if source_ru_text else
                    "SOURCE_LIVE_8ADC_2TACH_RAW_PARAM_REGISTER_IMAGE"),
    )
