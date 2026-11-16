"""Stage111Z31CS original IDR: Mode2 shows tabs BEFORE TCP connection.

Provenance _Unit128.pas reconstructed by IDR mvkview.idp:
00848E78 -> Mode 2 -> 00846D24..5C tab visibility ->
00846D79..84 pnMeasure -> 00846DCC TMVKThread constructor.
00848B06+ Status and StatusIsError update the bottom-right indicator.
"""
from __future__ import annotations
import pytest
from ..core.original_measurement_mode import (
    source_connection_display,capture_completion_policy,SOURCE,
)
from ..core.original_runtime_tabs import (
    ORIGINAL_LIVE_VISIBLE,ORIGINAL_IDLE_VISIBLE,
    original_runtime_visible_pages,original_runtime_tab_contract,
)
from .test_stage111z31cr_connected_core import source_test_transport


def test_mode2_five_tabs_before_native_go_or_any_device_connection():
    assert ORIGINAL_LIVE_VISIBLE==(
        "PageStart","PageStatus","PageAdc","PageSpectrum","PageFile")
    assert original_runtime_visible_pages(
        has_measurement=False,measurement_requested=True,live=False
    )==ORIGINAL_LIVE_VISIBLE
    assert original_runtime_visible_pages(
        has_measurement=False,measurement_requested=False,live=False
    )==ORIGINAL_IDLE_VISIBLE
    projection=original_runtime_tab_contract(
        has_measurement=False,measurement_requested=True,live=False,
        current_page="PageStatus")
    assert projection["visible_count"]==5
    assert projection["mode2_selected_before_connection"]
    assert not projection["native_recorder_started"]
    assert not projection["device_connection_verified_by_tabs"]
    assert projection["measurement_toolbar_visible_from_source_mode2"]
    assert not projection["instrument_command_sent"]
    for invalid in (1,None,"yes"):
        with pytest.raises(ValueError):
            original_runtime_visible_pages(
                has_measurement=False,measurement_requested=invalid)


def test_source_bottom_right_waiting_good_error_and_disconnected_states():
    idle=source_connection_display(selected=False)
    assert idle.phase=="IDLE"
    assert idle.indicator=="none"
    waiting=source_connection_display(selected=True,capture_started=False)
    assert waiting.phase=="MODE2"
    assert waiting.indicator=="waiting"
    assert "Ожидание подключения" in waiting.text
    assert not waiting.transport_verified
    assert SOURCE.startswith("IDR_00848E78_")
    assert not waiting.receipt()["physical_connection_implied_by_tabs"]
    assert not waiting.receipt()["device_commands_issued"]
    started=source_connection_display(selected=True,capture_started=True)
    assert started.phase=="CONNECTING"
    assert not started.transport_verified
    assert started.indicator=="waiting"
    verified=source_connection_display(
        selected=True,capture_started=True,
        status=source_test_transport(phase="RECORDING",frames=400))
    assert verified.transport_verified
    assert verified.indicator=="good"
    assert verified.text=="Подключен к прибору"
    rejected=source_connection_display(
        selected=True,capture_started=True,
        status=source_test_transport(phase="REFUSED"))
    assert rejected.indicator=="bad"
    assert not rejected.transport_verified
    stale=source_connection_display(
        selected=True,capture_started=True,
        status=source_test_transport(stale=True))
    assert stale.indicator=="bad"
    assert not stale.transport_verified
    failed=source_connection_display(
        selected=True,capture_started=False,failure=True)
    assert failed.indicator=="bad"
    assert not failed.transport_verified


def test_missing_or_invalid_capture_evidence_never_activates_green_indicator():
    for kw in (
        dict(selected=True,capture_started=True,
             status=source_test_transport(frames=0)),
        dict(selected=True,capture_started=True,
             status=source_test_transport(phase="CONNECTING")),
    ):
        assert not source_connection_display(**kw).transport_verified
    for kw in (
        dict(selected=1),
        dict(selected=True,capture_started=1),
        dict(selected=False,capture_started=True),
        dict(selected=False,failure=True),
        dict(selected=True,status=source_test_transport()),
        dict(selected=True,capture_started=True,status={}),
    ):
        with pytest.raises(ValueError):
            source_connection_display(**kw)


@pytest.mark.parametrize(
    "exported,exit_requested,parked,expected",
    (
        (False,False,False,(True,True,False,False)),
        (False,False,True, (True,True,True,False)),
        (False,True, True, (False,False,True,False)),
        (False,True, False,(False,False,False,False)),
        (True,False,True, (False,False,False,True)),
        (True,True, True, (False,False,False,True)),
    ),
)
def test_capture_exit_restores_only_verified_offline_archive(
        exported,exit_requested,parked,expected):
    policy=capture_completion_policy(
        exported=exported,operator_exit_requested=exit_requested,
        has_parked_archive=parked)
    assert (
        policy.keep_mode2,policy.connection_error,
        policy.reopen_prior_archive,policy.accepted_new_archive)==expected
    assert not policy.receipt()["verified_connection_implied"]
    assert not policy.receipt()["device_commands_issued"]


def test_capture_exit_rejects_ambiguous_boolean_provenance():
    for key in ("exported","operator_exit_requested","has_parked_archive"):
        args=dict(exported=False,operator_exit_requested=False,
                  has_parked_archive=False)
        for bad in (None,1,"false"):
            args[key]=bad
            with pytest.raises(ValueError):
                capture_completion_policy(**args)
