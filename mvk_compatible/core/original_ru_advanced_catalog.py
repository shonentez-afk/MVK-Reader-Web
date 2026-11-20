"""Small verified RU labels for the ten source TMvkAdvancedCell lists.

The user supplied a previously extracted original
res_10_EXTLOCALIZATION_1033.json resource. Only 41 *derived* RU labels
from its 'ru-ru' section are retained here; the resource itself, PE, IDP,
PAS and any private measurement bytes are NEVER copied into GitHub.
Source IDs and prefixes are checked against private _Unit125.pas,
mvk_idr(1).sqlite and the independent IDP tables.

DO NOT equate this label catalog with a byte-exact Win32 TLanguage
runtime: RCDATA authenticity against the running vendor EXE has not
been checked in this pass. No guessed English/other-language fallback.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .original_config_idp_tables import (
    SOURCE_SELECTOR_IDS, SOURCE_SELECTOR_PREFIXES,
)

SCHEMA="MVK_EXTLOCALIZATION_1033_RU_SOURCE_ADVANCED_41_V1"

# Names as observed in the original extracted EXTLOCALIZATION resource.
# Not a copy of full resource JSON or any operator-owned measurement.
_RU: dict[str,dict[int,str]] = {
    "num_groups": {
        0:"Одна группа в 8 каналов", 1:"Две группы по 4 канала",
    },
    "option": {
        0:"Отсутствует",1:"Малый экран",2:"Wi-Fi модуль",
        3:"Модуль индикации ВДМ82",
    },
    "wifi_mode": {0:"Отключен",1:"Клиент",2:"Точка доступа"},
    "alarm_band": {
        0:"Выключено",1:"Напряжение на датчике",
        48:"Виброускорение, Х..25 кГц",
        47:"Пик-фактор виброуск., Х..25 кГц",
    },
    "alarm_state": {
        0:"(выкл)",1:"Зеленая зона (Устар. ПО)",
        2:"Желтая зона (квитировано) (Устар. ПО)",
        3:"Красная зона (квитировано) (Устар. ПО)",
        4:"Желтая зона (Устар. ПО)",
        5:"Красная зона (Устар. ПО)",
        17:"Зеленая зона",18:"Ошибка датчика",
        19:"Ошибка конфигурации",20:"Желтая зона",
        21:"Красная зона",255:"Ошибка конф. (Устар. ПО)",
    },
    "alarm_alert": {
        1:"Ошибка датчика (Устар. ПО)",2:"Ошибка датчика",
        4:"Переход в желтую зону",8:"Переход в красную зону",
    },
    "tacho_function": {0:"Нет",1:"Квитирование"},
    "result_overload": {0:"ОК",1:"Перегрузка"},
    "result_buffers": {
        0:"ОК",1:"Идет заполнение (32 с)",
        3:"Идет заполнение (4, 32 с)",
        7:"Идет заполнение (1, 4, 32 с)",
    },
    "result_sensor_state": {
        0:"ОК",1:"Обрыв",2:"КЗ линии",3:"Неисправность",
    },
}
assert set(_RU)==set(SOURCE_SELECTOR_IDS)==set(SOURCE_SELECTOR_PREFIXES)
assert sum(len(m) for m in _RU.values())==41
for kind,items in _RU.items():
    assert tuple(items)==tuple(SOURCE_SELECTOR_IDS[kind]),kind
    assert all(isinstance(s,str) and s and
               not any(c in s for c in "|\r\n") for s in items.values())
RU_ADVANCED_CATALOG=MappingProxyType({
    kind:MappingProxyType(items.copy()) for kind,items in _RU.items()
})


def original_ru_advanced_translations(kind:str)->Mapping[str,str]:
    """Returns *only* source-attested dynamic TLanguage keys for this list.

    Explicit opt-in; unknown/non-original kinds are rejected, and the
    original GetTitleByID unknown-ID hexadecimal fallback is not changed.
    """
    if kind not in RU_ADVANCED_CATALOG:
        raise ValueError("Unknown original source Advanced selector kind")
    prefix=SOURCE_SELECTOR_PREFIXES[kind]
    return MappingProxyType({
        f"{prefix}Cell{ident}":title
        for ident,title in RU_ADVANCED_CATALOG[kind].items()
    })


def original_ru_advanced_provenance()->dict:
    return {
        "schema":SCHEMA,
        "source_selector_list_count":len(_RU),
        "source_localized_advanced_id_count":41,
        "source_dynamic_lookup_keys_verified":True,
        "source_locale":"ru-ru",
        "original_resource_rerendered_in_vendor_win32_process":False,
        "original_pe_rcdata_byte_parity_verified":False,
        "other_locales_verified":False,
        "private_resource_json_embedded":False,
        "instrument_measurement_bytes_embedded":False,
    }
