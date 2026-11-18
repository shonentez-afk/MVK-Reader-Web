"""Source Task2 Stage0/1/3 and DENIED: pure Core regression evidence."""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from mvk_compatible.core.original_task2_stage_receipt import (
    SCHEMA,validate_original_task2_stage,
)

def evidence(*,stage=0,last=0,connected=True,params=0,valid=False,
             status0=None,fault=False,denied=0,end="",disconnected=False):
    status=dict(source_rx_nonempty_parameter_frames=params,
                source_rx_ack_observed_no_command_issued=0,
                source_rx_denied_responses=denied)
    proof=dict(schema=SCHEMA,task=2,source_stage=stage,
               last_live_stage=last,socket_connected=connected,
               source_socket_attempts=1,
               nonempty_param_since_connect=params,
               source_system_status0_valid=valid,
               source_system_status0_uint32=status0,
               original_unobserved_ff_sentinel_risk=connected and params>0 and not valid,
               system_error_latched=fault,observed_ack_frames=0,
               observed_denied_frames=denied,
               disconnected=disconnected,last_end_reason=end,
               original_delphi_thread_parity_verified=False,
               device_command_sent_by_lifecycle=False)
    status["source_original_task2_stage"]=proof
    cells=(SimpleNamespace(valid=valid,value=status0),)
    return status,cells

def test_real_param_not_full_calibration_triggers_task2_stage1():
    status,cells=evidence(stage=1,last=1,params=1)
    doc=validate_original_task2_stage(status,cells)
    assert doc["source_stage"]==1
    assert doc["original_unobserved_ff_sentinel_risk"]
    assert doc["source_system_status0_uint32"] is None
    assert doc["source_backed_not_actual_delphi"]

def test_real_status0_error_latches_stage3_after_followup_zero():
    status,cells=evidence(stage=3,last=3,params=2,valid=True,status0=0,fault=True)
    result=validate_original_task2_stage(status,cells)
    assert result["system_error_latched"] and result["source_stage"]==3

def test_source_denied_in_passive_task2_closes_stage_but_preserves_provenance():
    status,cells=evidence(stage=0,last=1,connected=False,
                          disconnected=True,params=1,valid=True,status0=0,
                          denied=1,end="SOURCE_OPERATION_DENIED")
    result=validate_original_task2_stage(status,cells)
    assert result["last_live_stage"]==1
    assert result["observed_denied_frames"]==1
    assert result["disconnected"]
    assert not result["device_commands_sent_by_lifecycle"]

def test_source_reconnect_starts_stage0_without_stale_param():
    status,cells=evidence(stage=0,last=0,params=0)
    status["source_rx_nonempty_parameter_frames"]=27
    status["source_original_task2_stage"]["source_socket_attempts"]=2
    assert validate_original_task2_stage(status,cells)["source_stage"]==0

@pytest.mark.parametrize("change",[
    lambda s:s["source_original_task2_stage"].update(source_stage=2),
    lambda s:s["source_original_task2_stage"].update(original_delphi_thread_parity_verified=True),
    lambda s:s["source_original_task2_stage"].update(device_command_sent_by_lifecycle=True),
    lambda s:s["source_original_task2_stage"].update(nonempty_param_since_connect=10),
    lambda s:s["source_original_task2_stage"].update(source_system_status0_valid=True),
    lambda s:s["source_original_task2_stage"].update(original_unobserved_ff_sentinel_risk=False),
    lambda s:s["source_original_task2_stage"].update(disconnected=True),
    lambda s:s["source_original_task2_stage"].update(source_socket_attempts=-1),
    lambda s:s["source_original_task2_stage"].update(last_end_reason="../escape"),
])
def test_forged_stage_receipt_is_rejected(change):
    status,cells=evidence(stage=1,last=1,params=1)
    change(status)
    with pytest.raises(ValueError):
        validate_original_task2_stage(status,cells)
