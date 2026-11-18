"""Source TMVKThread rate and FreezeUpdate contract from three originals.

These tests never attach to an instrument or authorize hardware SetRate.
"""
from copy import deepcopy
import pytest

from mvk_compatible.core.original_receive_gate_receipt import (
    SCHEMA,validate_original_receive_gate_receipt,
)
from mvk_compatible.core.original_source_ring_receipt import (
    validate_original_storage_receipt,
)
from .test_stage111z31fi_original_ring_receipt import ring_fixture


def source_fixture():
    ring,channels=ring_fixture()
    for ch in channels:
        ch["frames"]=ch["samples"]//256
    rows=[]
    for i,ch in enumerate(channels):
        count=ch["samples"]*(4 if i>=8 else 1)
        rows.append({
            "channel":i+1,"accepted_elements":count,
            "rate_skipped_elements":0,"freeze_skipped_elements":0,
            "rate_skipped_frames":0,"freeze_skipped_frames":0,
            "last_skipped_native_samples":0,
        })
    proof={
        "schema":SCHEMA,"initial_thread_rate_hz":777,
        "source_initial_menu_rate_hz":65536,"selected_rate_hz":65536,
        "source_menu_selected":True,"physical_setrate_not_inferred":True,
        "freeze_update":False,"selection_changes":1,"freeze_changes":0,
        "original_delphi_parity_verified":False,"channels":rows,
    }
    return proof,ring,channels


def test_exact_tmvkthread_777_to_source_menu_65536_without_tx():
    gate,ring,channels=source_fixture()
    received=validate_original_receive_gate_receipt(gate,channels)
    assert received["initial_thread_rate_hz"]==777
    assert received["source_initial_menu_rate_hz"]==65536
    assert received["physical_setrate_not_inferred"]
    assert not received["original_delphi_parity_verified"]
    assert validate_original_storage_receipt(ring,channels,received)


def test_original_freeze_receipt_explains_real_unstored_tcp_words():
    gate,ring,channels=source_fixture()
    # The first 512 native words were admitted to the original channel,
    # the following 256 were read from TCP but never written to storage.
    i=0
    native=channels[i]["samples"]
    gate["channels"][i]["freeze_skipped_elements"]=256
    gate["channels"][i]["freeze_skipped_frames"]=1
    gate["channels"][i]["last_skipped_native_samples"]=native
    gate["channels"][i]["accepted_elements"]=native-256
    gate["freeze_update"]=True
    gate["freeze_changes"]=1
    row=ring["channels"][i]
    row["rx_pos_64"]=native-256
    row["available_elements"]=native-256
    row["next_device_sample_index"]-=256
    approved=validate_original_receive_gate_receipt(gate,channels)
    assert approved["channels"][0]["last_skipped_native_samples"]==native
    assert validate_original_storage_receipt(ring,channels,approved)
    # This exact mismatch would previously be called a fake Go device
    # index even though Source FreezeUpdate intentionally stopped writing.
    with pytest.raises(ValueError,match="device index"):
        validate_original_storage_receipt(ring,channels)


@pytest.mark.parametrize("mutator",[
    lambda g,c:g.update(initial_thread_rate_hz=0),
    lambda g,c:g.update(selected_rate_hz=777),
    lambda g,c:g.update(source_initial_menu_rate_hz=32768),
    lambda g,c:g.update(physical_setrate_not_inferred=False),
    lambda g,c:g.update(original_delphi_parity_verified=True),
    lambda g,c:g.update(freeze_update=1),
    lambda g,c:g["channels"][0].update(accepted_elements=1),
    lambda g,c:g["channels"][0].update(rate_skipped_elements=-1),
    lambda g,c:g["channels"][8].update(freeze_skipped_elements=2),
    lambda g,c:g["channels"][0].update(last_skipped_native_samples=123),
    lambda g,c:g["channels"][0].update(rate_skipped_frames=1),
    lambda g,c:g["channels"][0].update(channel=10),
])
def test_unsupported_original_gate_receipt_is_rejected(mutator):
    gate,ring,channels=source_fixture()
    mutator(gate,channels)
    with pytest.raises(ValueError):
        validate_original_receive_gate_receipt(gate,channels)


def test_multiple_freeze_cycles_do_not_claim_contiguous_original_window():
    gate,ring,channels=source_fixture()
    native=channels[0]["samples"]
    gate["channels"][0].update(
        accepted_elements=native-512,freeze_skipped_elements=512,
        freeze_skipped_frames=2,last_skipped_native_samples=native-512)
    gate["freeze_changes"]=4
    row=ring["channels"][0]
    row.update(rx_pos_64=native-512,
               available_elements=native-512,
               sequence_gaps=2,
               next_device_sample_index=row["next_device_sample_index"]-512)
    assert validate_original_storage_receipt(
        ring,channels,validate_original_receive_gate_receipt(gate,channels))
