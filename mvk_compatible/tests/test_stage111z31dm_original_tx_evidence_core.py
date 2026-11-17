"""Go sender-opportunity proof is independent of actual physical TX."""
from __future__ import annotations
import pytest
from ..core.original_mode2_transmit_evidence import (
    FIELD, validate_original_task2_tx,
)
from ..core.original_mode2_status_cells import SOURCE_INDEX_ADDR,SOURCE_STATUS_FIELD
from .test_stage111z31cz_source_write_stages_core import source_status,RUN


def snapshot(value=0,param=1,capture_only=False):
    p=source_status(session=RUN,adc_samples=512,aux=2,frames=80,raw=50000)
    known=param>0 and value is not None
    p.update({
        "source_rx_nonempty_parameter_frames":param,
        "source_rx_ack_observed_no_command_issued":0,
        "source_rx_denied_responses":0,
        SOURCE_STATUS_FIELD:[
            {"index":i,"register_address":addr,
             "valid":i==0 and known,
             "value_uint32":value if i==0 and known else None}
            for i,addr in enumerate(SOURCE_INDEX_ADDR)],
    })
    p["capture_only"]=capture_only
    seen=param>0
    zero=known and value==0
    p[FIELD]={
        "source_original_writer_present":True,
        "source_stage1_nonempty_param_observed":seen,
        "source_system_status0_valid_zero":zero,
        "source_setrate_candidate_after_param":seen and zero and not capture_only,
        "source_go_device_app_bytes_sent":0,
        "source_setrate_frame_size_bytes":36,
        "original_source_command_physically_verified":False,
    }
    return p


def test_source_real_param_zero_error_allows_only_candidate_not_tx():
    r=validate_original_task2_tx(snapshot())
    assert r.source_send_candidate and r.producer_sent_bytes==0
    assert not r.receipt()["original_delphi_command_physically_observed"]
    assert r.receipt()["source_setrate_36_bytes_lab_recovered"]


@pytest.mark.parametrize("value,param,capture_only",[
    (None,1,False),(7,1,False),(0,0,False),(0,1,True),
])
def test_no_fake_send_when_system_unknown_error_no_param_or_bad_capture(value,param,capture_only):
    r=validate_original_task2_tx(snapshot(value,param,capture_only))
    assert not r.source_send_candidate
    assert r.producer_sent_bytes==0


@pytest.mark.parametrize("key,value",[
    ("source_original_writer_present",False),
    ("source_stage1_nonempty_param_observed",False),
    ("source_system_status0_valid_zero",False),
    ("source_setrate_candidate_after_param",False),
    ("source_go_device_app_bytes_sent",36),
    ("source_setrate_frame_size_bytes",32),
    ("original_source_command_physically_verified",True),
])
def test_go_tx_receipt_cannot_forge_commands_or_param_preconditions(key,value):
    p=snapshot()
    p[FIELD][key]=value
    with pytest.raises(ValueError):
        validate_original_task2_tx(p)


def test_older_original_passive_go_receipts_remain_compatible():
    p=snapshot()
    del p[FIELD]
    assert validate_original_task2_tx(p) is None
