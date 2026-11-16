"""Stage111Z31DI: real source 14 StatusCells, Valid not FF sentinel.

The original IDP address sequence occurs exactly once in the private IDP;
the original source _Unit125.pas indexes StatusCells[0..13] with 008D3068.
No private IDP/SQLite/raw assets are embedded in this source.
"""
from __future__ import annotations

from copy import deepcopy
import pytest

from ..core.original_mode2_status_cells import (
    SOURCE_INDEX_ADDR, SOURCE_INDEX_LABEL, SOURCE_ORIGINAL_UNKNOWN,
    SOURCE_STATUS_FIELD, OriginalStatusCellsEvidence, parse_source_cells,
    source_status_cell0_error,
)
from ..core.original_mode2_runtime_trace import OriginalMode2RuntimeTrace
from ..core.original_mode2_live_health import live_transport_health
from ..core.original_connected_status import connected_system_status
from ..core.original_measurement_mode import source_connection_display
from ..core.original_live_write_stages import OriginalLiveWriteLedger
from ..core.original_live_pagefile import OriginalLiveFilePlan
from .test_stage111z31cz_source_write_stages_core import source_status, RUN
from .test_stage111z26_native_live_status import fixture_state, now
from ..core.native_r6_live_status import validate_live_status


def source_cells(*,updates=None):
    updates=updates or {}
    return [
        {"index":i,"register_address":addr,"valid":i in updates,
         "value_uint32":updates.get(i)}
        for i,addr in enumerate(SOURCE_INDEX_ADDR)
    ]


def with_cells(*,updates=None,params=1,frames=70,adc=512,aux=1):
    x=source_status(session=RUN,adc_samples=adc,aux=aux,frames=frames,
                    raw=50000+frames)
    x.update({
        "source_rx_nonempty_parameter_frames":params,
        "source_rx_ack_observed_no_command_issued":0,
        "source_rx_denied_responses":0,
        SOURCE_STATUS_FIELD:source_cells(updates=updates),
    })
    return x


def test_source_idp_14_exact_addresses_names_and_original_unsigned_unknown():
    assert SOURCE_INDEX_ADDR==(
        0x1006,0x1038,0x1030,0x1032,0x2120,0x2320,0x2520,
        0x2720,0x2920,0x2B20,0x2D20,0x2F20,0x3004,0x3104)
    assert len(SOURCE_INDEX_LABEL)==14
    assert SOURCE_INDEX_LABEL[:4]==("Система","Загрузка","*SPORT","*SPI")
    assert SOURCE_ORIGINAL_UNKNOWN==0xFFFFFFFF
    assert SOURCE_ORIGINAL_UNKNOWN>0  # original unsigned JBE does not skip
    empty=OriginalStatusCellsEvidence().receipt()
    assert empty["source_status_cells_valid_count"]==0
    assert not empty["source_stage3_condition_from_observed_register"]
    assert empty["source_statuscells0_uint32"] is None
    assert empty["source_status_cells"][0]["value_hex"] is None


def test_go_readonly_cell0_known_zero_unknown_and_positive_differ():
    x=with_cells(updates=None)
    assert parse_source_cells(x)[0].valid is False
    assert not source_status_cell0_error(x)
    assert not live_transport_health(x).source_system_error_observed
    zero=with_cells(updates={0:0})
    assert parse_source_cells(zero)[0].valid
    assert not source_status_cell0_error(zero)
    assert not live_transport_health(zero).data_integrity_alert
    nonzero=with_cells(updates={0:0x80,2:5,13:0xFFFFFFFF})
    records=parse_source_cells(nonzero)
    assert records[0].value==0x80
    assert records[13].valid and records[13].value==SOURCE_ORIGINAL_UNKNOWN
    assert source_status_cell0_error(nonzero)
    health=live_transport_health(nonzero)
    assert health.source_system_error_observed
    assert health.data_integrity_alert
    proof=connected_system_status(nonzero)
    assert proof.source_system_error_observed
    assert len(proof.rows)==15
    assert all(value=="—" for _,value in proof.rows)
    assert proof.receipt()["original_device_system_fields_proven"]==0
    display=source_connection_display(
        selected=True,capture_started=True,status=nonzero)
    assert display.phase=="SYSTEM_ERROR"
    assert display.indicator=="bad"


@pytest.mark.parametrize("mutator",[
    lambda x: x[SOURCE_STATUS_FIELD].pop(),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"index":1}),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"register_address":0x1007}),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"valid":True}),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"value_uint32":0}),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"valid":1}),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"valid":True,"value_uint32":-1}),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"valid":True,"value_uint32":True}),
    lambda x: x[SOURCE_STATUS_FIELD][0].update({"valid":True,"value_uint32":0x100000000}),
    lambda x: x.update({"source_rx_nonempty_parameter_frames":0}) or
              x[SOURCE_STATUS_FIELD][0].update({"valid":True,"value_uint32":5}),
    lambda x: x.pop("source_rx_denied_responses"),
])
def test_source_status_cell_json_rejects_missing_fake_or_misaddressed_words(
        mutator):
    x=with_cells()
    mutator(x)
    with pytest.raises(ValueError):
        parse_source_cells(x)


def test_sticky_source_stage3_condition_uses_real_valid_word_not_ff_init():
    proof=OriginalStatusCellsEvidence()
    proof.observe_native(with_cells())
    assert proof.receipt()["source_status_cells_valid_count"]==0
    stage0=proof.observe_native(with_cells(updates={0:0},params=2,frames=71))
    assert stage0["source_statuscells0_register_valid"]
    assert stage0["source_statuscells0_uint32"]==0
    assert not stage0["source_system_error_latched_until_new_capture"]
    stage3=proof.observe_native(with_cells(updates={0:7},params=3,frames=72))
    assert stage3["new_source_system_error_from_go_register"]
    assert stage3["source_stage3_condition_from_observed_register"]
    assert stage3["source_system_error_latched_until_new_capture"]
    again=proof.observe_native(with_cells(updates={0:0},params=4,frames=73))
    assert not again["source_stage3_condition_from_observed_register"]
    assert again["source_system_error_latched_until_new_capture"]
    assert not again["new_source_system_error_from_go_register"]
    assert not again["original_tmkvthread_stage3_actually_observed"]


def test_system_cells_never_drop_valid_or_change_without_param():
    proof=OriginalStatusCellsEvidence()
    proof.observe_native(with_cells(updates={0:8},params=1,frames=70))
    with pytest.raises(ValueError,match="rolled back"):
        proof.observe_native(with_cells(updates=None,params=2,frames=71))
    with pytest.raises(ValueError,match="without any new PARAM"):
        proof.observe_native(with_cells(updates={0:9},params=1,frames=71))
    with pytest.raises(ValueError,match="disappeared"):
        proof.observe_native(source_status(session=RUN,frames=72,raw=50075))


def test_mode2_source_stage3_blocks_offline_setrate_and_validated_writer():
    x=with_cells(updates={0:0x100},params=1,frames=80,aux=2)
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.native_started()
    assert len(trace.command_model.pending)==1
    receipt=trace.observe_native(x)
    assert receipt["mode2_phase"]=="SYSTEM_ERROR"
    assert receipt["original_stage3_system_error_condition_latched"]
    assert receipt["original_status_cells_14"]["source_statuscells0_uint32"]==256
    assert len(trace.command_model.pending)==1
    assert receipt["source_initial_rate_write_calls_dry_run"] is None
    assert receipt["hardware_commands_sent"]==0
    writer=OriginalLiveWriteLedger()
    with pytest.raises(ValueError,match="stale or damaged"):
        writer.observe(x)
    assert not writer.trustworthy
    assert receipt["original_delphi_stage3_physically_verified"] is False


def test_stage1_setrate_dryrun_when_real_system_status_zero_and_no_denied():
    x=with_cells(updates={0:0},params=1,frames=80,aux=2)
    trace=OriginalMode2RuntimeTrace()
    trace.enter_mode2()
    trace.native_started()
    read=trace.observe_native(x)
    assert read["mode2_phase"]=="RECORDING"
    assert not read["original_stage3_system_error_condition_latched"]
    assert len(trace.command_model.taken)==1
    assert read["source_initial_rate_write_calls_dry_run"] is not None
    assert read["source_initial_rate_write_calls_dry_run"][
        "write_argument_uint32_hex"][-1]=="0x00010000"
    assert read["hardware_commands_sent"]==0


def test_native_live_status_rejects_fake_cells_and_detects_real_system_fault():
    x=fixture_state()
    x.update({
        "source_rx_nonempty_parameter_frames":1,
        "source_rx_ack_observed_no_command_issued":0,
        "source_rx_denied_responses":0,
        SOURCE_STATUS_FIELD:source_cells(updates={0:2}),
    })
    assert x["frames_decoded"]>=1
    accepted=validate_live_status(x,expected_run=x["session_id"],now=now())
    assert accepted["source_system_error_observed"]
    assert accepted["quality_alert"]
    bad=deepcopy(x)
    bad[SOURCE_STATUS_FIELD][0]["valid"]=False
    with pytest.raises(ValueError):
        validate_live_status(bad,expected_run=bad["session_id"],now=now())
