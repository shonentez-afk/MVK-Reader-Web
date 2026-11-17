"""Source-derived from local mvk_idr(1).sqlite + _Unit125/_Unit128.pas.

Check the real original Measure→selected WriteData/WriteValues chain, not
the unrelated device service/Flash operation. Synthetic authenticated
Native status only, never a connection to a real instrument.
"""
from __future__ import annotations

import pytest

from ..core.original_live_write_stages import (
 OriginalLiveWriteLedger,STAGE_IDLE,STAGE_OPEN,STAGE_STREAMING,
)
from ..core.original_live_pagefile import OriginalLiveFilePlan
from .test_stage111z31cz_source_write_stages_core import source_status
from .test_stage111z31dt_original_real_tx_core import approved_source_tx

def active_source(*,adc_samples=256,aux=1,frames=26,raw=30000,
                  values_ticks=1,sockets=1):
    p=source_status(adc_samples=adc_samples,aux=aux,frames=frames,raw=raw)
    t=approved_source_tx()
    p["read_only_no_app_payload_sent"]=False
    p["source_mode2_tx_evidence"]=t["source_mode2_tx_evidence"]
    p["source_values_ticks_address_3100"]=values_ticks
    p["source_tcp_connection_count"]=sockets
    p["source_tcp_multi_socket"]=sockets>1
    return p


def test_original_mode2_local_write_buttons_still_work_with_real_source_setrate():
    ledger=OriginalLiveWriteLedger()
    first=active_source(values_ticks=1)
    ledger.observe(first)
    assert ledger.receipt()["hardware_commands_sent"]==1
    plan=OriginalLiveFilePlan().bind_status(first)
    ledger.toggle("data",plan)
    assert ledger.data_stage==STAGE_OPEN
    ledger.toggle("values",plan)
    assert ledger.values_stage==STAGE_STREAMING
    later=active_source(adc_samples=768,aux=2,frames=90,
                        raw=92000,values_ticks=5)
    ledger.observe(later)
    assert ledger.data_stage==STAGE_STREAMING
    ledger.toggle("data",plan)
    ledger.toggle("values",plan)
    ledger.finish(accepted=True)
    receipt=ledger.receipt()
    assert receipt["hardware_commands_sent"]==1
    assert receipt["original_source_values_ticks_0x3100"]==5
    assert [w.kind for w in ledger.windows]==["data","values"]
    for w in ledger.windows:
        proof=w.receipt()
        assert proof["hardware_command_sent"] is True
        assert proof["source_setrate_commands_seen"]==1
        assert proof["original_source_values_ticks_0x3100"]["start"]==1
        assert proof["original_source_values_ticks_0x3100"]["end"]==5
        assert proof["original_tmkvthread_file_byte_parity_verified"] is False


def test_orig_writevalues_3100_not_equal_aux_tick_and_monotonic():
    ledger=OriginalLiveWriteLedger()
    first=active_source(values_ticks=0,aux=12,frames=80)
    ledger.observe(first)
    plan=OriginalLiveFilePlan().bind_status(first)
    ledger.toggle("values",plan)
    second=active_source(values_ticks=2,aux=12,frames=85,raw=33000)
    ledger.observe(second)
    ledger.toggle("values",plan)
    window=ledger.windows[0].receipt()
    assert window["original_source_values_ticks_0x3100"]=={
        "start":0,"end":2,
        "source_trigger_is_param_address_3100":True,
        "native_aux_tick_is_not_source_values_tick":True,
    }
    assert ledger.windows[0].start_aux==ledger.windows[0].end_aux==12


@pytest.mark.parametrize("mutator",[
 lambda p:p.update(read_only_no_app_payload_sent=True),
 lambda p:p.update(source_values_ticks_address_3100=10000),
 lambda p:p["source_mode2_tx_evidence"].update(source_tx_explicitly_approved=False),
])
def test_unverified_real_setrate_or_values_tick_cannot_arm_writer(mutator):
    ledger=OriginalLiveWriteLedger()
    p=active_source()
    mutator(p)
    with pytest.raises(ValueError):
        ledger.observe(p)
    assert not ledger.receipt()["has_verifiable_live_status"]


def test_original_measure_reconnect_cannot_join_local_write_windows():
    ledger=OriginalLiveWriteLedger()
    first=active_source()
    ledger.observe(first)
    plan=OriginalLiveFilePlan().bind_status(first)
    ledger.toggle("data",plan)
    new=active_source(adc_samples=512,aux=2,frames=45,raw=45000,
                      values_ticks=2,sockets=2)
    with pytest.raises(ValueError,match="separate TCP sockets"):
        ledger.observe(new)
    assert ledger.receipt()["write_data_stage"]==STAGE_IDLE
    assert not ledger.receipt()["write_data_requested"]
    assert len(ledger.windows)==0
    assert ledger.errors
