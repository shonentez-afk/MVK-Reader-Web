"""Stage111Z31CR: connected LIVE source layout and real user captions.

The user's screenshot of the running original showed five root pages,
15 PageStatus sub-tabs, 15 TStatusList values and five pnMeasure controls.
Native read-only capture reports TRANSPORT, not vendor system registers.
"""
from __future__ import annotations

import pytest
from ..core.original_connected_status import (
    SYSTEM_STATUS_KEYS,SYSTEM_STATUS_HEADERS,connected_system_status,UNKNOWN,
)
from ..core.original_pagestatus_source import ORIGINAL_OPERATOR_STATUS_TABS
from ..core.original_runtime_tabs import (
    ORIGINAL_IDLE_VISIBLE,ORIGINAL_ARCHIVE_VISIBLE,ORIGINAL_LIVE_VISIBLE,
    original_runtime_tab_contract,original_runtime_visible_pages,
)
from ..core.native_r6_live_status import SCHEMA
from ..core.original_ui_form_contract import ORIGINAL_ROOT_PAGES


def source_test_transport(*,phase="RECORDING",frames=8,stale=False):
    return {"schema":SCHEMA,"read_only_no_app_payload_sent":True,
            "phase":phase,"frames_decoded":frames,"snapshot_stale":stale,
            "elapsed_seconds":20.0,"raw_bytes":8192,
            "invalid_frames":0,"aux4700_updates":0}


def test_exact_five_connected_root_tabs_in_source_order_without_developer_pages():
    assert ORIGINAL_IDLE_VISIBLE==("PageStart",)
    assert ORIGINAL_ARCHIVE_VISIBLE==(
        "PageStart","PageAdc","PageSpectrum")
    assert ORIGINAL_LIVE_VISIBLE==(
        "PageStart","PageStatus","PageAdc","PageSpectrum","PageFile")
    assert original_runtime_visible_pages(
        has_measurement=False,live=True)==ORIGINAL_LIVE_VISIBLE
    assert original_runtime_visible_pages(
        has_measurement=True,live=True)==ORIGINAL_LIVE_VISIBLE
    receipt=original_runtime_tab_contract(
        has_measurement=True,live=True,current_page="PageStatus")
    assert receipt["connected_original_five_tabs"]
    assert receipt["visible_count"]==5
    assert not receipt["original_runtime_reachability_parity_verified"]
    assert not receipt["instrument_command_sent"]
    assert tuple(p.fallback_title_ru for p in ORIGINAL_ROOT_PAGES if
                 p.object_name in ORIGINAL_LIVE_VISIBLE)==(
        "Задачи","Расчетные данные","Временной сигнал",
        "Спектр","Параметры записи")
    assert len(ORIGINAL_ROOT_PAGES)==7
    for bad in (None,1,"yes"):
        with pytest.raises(ValueError):
            original_runtime_visible_pages(
                has_measurement=False,live=bad)
    assert original_runtime_visible_pages(
        has_measurement=True,live=False)==ORIGINAL_ARCHIVE_VISIBLE


def test_original_connected_status_has_all_15_visible_caption_tabs_and_rows():
    assert ORIGINAL_OPERATOR_STATUS_TABS==(
        "Состояние системы","Контроль",
        "Все каналы (СКЗ)","Все каналы (пик)",
        "Все каналы (пик-пик)",
        *(f"АЦП {i}" for i in range(1,9)),
        "Тахометр 1","Тахометр 2",
    )
    assert SYSTEM_STATUS_HEADERS==("Наименование параметра","Значение")
    assert len(SYSTEM_STATUS_KEYS)==15
    idle=connected_system_status()
    assert len(idle.rows)==15
    assert idle.rows[0]==("Серийный номер устройства",UNKNOWN)
    assert idle.rows[-1]==("Число активных клиентов Modbus",UNKNOWN)
    assert all(value==UNKNOWN for _,value in idle.rows)
    receipt=idle.receipt()
    assert receipt["original_device_system_fields_proven"]==0
    assert receipt["transport_frames"] is None
    assert not receipt["connected_readonly_transport_verified"]
    assert not receipt["original_modbus_or_device_commands_issued"]


def test_readonly_transport_never_becomes_vendor_modbus_counter_or_dsp_md5():
    good=connected_system_status(source_test_transport(frames=100))
    assert good.connection_verified
    assert good.frame_count==100
    assert all(value==UNKNOWN for _,value in good.rows)
    assert good.rows[10][0]=="Счетчик процедур расчета"
    assert good.rows[11][0]=="Счетчик запросов Modbus"
    assert good.rows[12][0]=="Последний адрес Modbus"
    assert good.rows[5][0]=="MD5 внутреннего ПО DSP"
    assert not connected_system_status(
        source_test_transport(phase="CONNECTING")).connection_verified
    assert not connected_system_status(
        source_test_transport(stale=True)).connection_verified
    assert not connected_system_status(
        source_test_transport(frames=0)).connection_verified
    for raw in (
        {},{"schema":"untrusted"},{"schema":SCHEMA,"phase":"RECORDING"},
        source_test_transport()|{"read_only_no_app_payload_sent":False},
        source_test_transport()|{"frames_decoded":"100"},
        source_test_transport()|{"snapshot_stale":1},
        source_test_transport()|{"phase":"UPLOAD"},
    ):
        with pytest.raises(ValueError):
            connected_system_status(raw)
