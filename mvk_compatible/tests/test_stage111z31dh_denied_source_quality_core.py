"""One real denied MVK reply makes passive preview/write quality untrusted."""
from __future__ import annotations

import pytest

from ..core.original_mode2_live_health import live_transport_health
from ..core.original_connected_status import connected_system_status
from ..core.original_measurement_mode import source_connection_display
from ..core.original_live_write_stages import OriginalLiveWriteLedger
from ..core.original_live_pagefile import OriginalLiveFilePlan
from .test_stage111z31cz_source_write_stages_core import source_status, RUN


def status(*, denied=0):
    state=source_status(session=RUN,adc_samples=512,aux=1,frames=70,
                        raw=50000)
    state.update({
        "source_rx_nonempty_parameter_frames":1,
        "source_rx_ack_observed_no_command_issued":1,
        "source_rx_denied_responses":denied,
    })
    return state


def test_original_denial_makes_all_live_trust_gates_fail_closed():
    valid=status()
    good=live_transport_health(valid)
    assert not good.received_operation_denied
    assert not good.data_integrity_alert
    assert connected_system_status(valid).connection_verified
    plan=OriginalLiveFilePlan().bind_status(valid)
    writer=OriginalLiveWriteLedger()
    writer.observe(valid)
    assert writer.trustworthy
    writer.toggle("data",plan)
    assert writer.receipt()["write_data_requested"]

    refused=status(denied=1)
    health=live_transport_health(refused)
    assert health.received_operation_denied
    assert health.data_integrity_alert
    assert health.receipt()["native_operation_denied_received"]
    # Transport bytes may continue, but the original source raises on
    # DENIED. The UI status is NOT "OK" and source writing is disarmed.
    proof=connected_system_status(refused)
    assert proof.data_integrity_alert
    display=source_connection_display(
        selected=True,capture_started=True,status=refused)
    assert display.indicator=="bad"
    assert display.phase=="STREAM_ERRORS"
    with pytest.raises(ValueError, match="stale or damaged"):
        writer.observe(refused)
    assert not writer.trustworthy
    assert not writer.receipt()["write_data_requested"]
    with pytest.raises(ValueError):
        writer.toggle("data",plan)


@pytest.mark.parametrize("broken",[-1,True,"1",2.3])
def test_malformed_denial_counter_never_grants_live_quality(broken):
    suspicious=status()
    suspicious["source_rx_denied_responses"]=broken
    with pytest.raises(ValueError,match="operation-denied"):
        live_transport_health(suspicious)


def test_source_legacy_status_without_denial_counter_is_not_fake_error():
    legacy=source_status(session=RUN,adc_samples=512,frames=70,raw=50000)
    health=live_transport_health(legacy)
    assert not health.received_operation_denied
    assert not health.data_integrity_alert
