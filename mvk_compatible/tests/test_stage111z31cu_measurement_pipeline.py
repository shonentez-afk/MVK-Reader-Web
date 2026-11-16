"""Offline source-driven Mode2 operator contract, no device I/O."""
import pytest

from ..core.original_measurement_pipeline import (
    ORIGINAL_MEASURE_ACTIONS, ORIGINAL_THREAD_ERRORS,
    measurement_operator_policy,original_measurement_source_summary,
)


def _policy(**overrides):
    args=dict(
        ui_mode="idle",mode2_selected=False,capture_active=False,
        technical_ui=False,native_archive_available=False,
        has_channels=False,has_values=False,
    )
    args.update(overrides)
    return measurement_operator_policy(**args)


def test_source_proof_entry_thread_timers_and_operational_controls():
    source=original_measurement_source_summary()
    assert source["entry_address"]=="00848E78"
    assert source["visible_tabs_before_tcp"]==5
    assert source["adc_count"]==8
    assert source["tach_count"]==2
    assert source["channel_buffer_bytes"]==0x200000
    assert source["tcp_port"]==10230
    assert source["timer_ms"]==20
    assert source["config_timer_ms"]==200
    assert source["connect_timeout_ms"]==1000
    assert source["read_timeout_ms"]==5000
    assert source["sample_rate_menu_item_count"]==5
    assert not source["sample_rate_menu_values_verified"]
    assert source["source_set_rate_is_device_command"]
    assert not source["safe_native_r6_1_write_command_supported"]
    assert not source["same_device_original_parity_proven"]
    assert {x[0] for x in ORIGINAL_MEASURE_ACTIONS} == {
        "bTaskConnect","bFreezeUpdate","bSampleRate",
        "bWriteTable","bWriteAdc","bWriteValues",
        "tmInterfaceUpdate",
    }
    assert {x[0] for x in ORIGINAL_THREAD_ERRORS} == {
        "closed","read_timeout","connect_timeout","network",
        "invalid_packet","command_denied","system_status",
    }


def test_core_policy_stays_in_mode2_even_without_tcp_evidence():
    x=_policy(mode2_selected=True)
    assert x.panel_visible
    assert not x.freeze_preview_enabled
    assert not x.rate_inspection_enabled
    assert not x.local_adc_enabled
    assert not x.original_set_rate_enabled
    assert not x.original_device_write_enabled


def test_live_is_display_only_freeze_with_zero_instrument_write():
    x=_policy(ui_mode="live",mode2_selected=True,
              capture_active=True,has_channels=True,has_values=True)
    assert x.panel_visible and x.freeze_preview_enabled
    assert x.rate_inspection_enabled
    assert not x.local_table_enabled
    assert not x.local_adc_enabled
    assert not x.local_values_enabled
    assert not x.receipt()["original_tmkvthread_device_writes_enabled"]
    assert x.receipt()["go_transport_read_only"]


def test_offline_export_requires_a_verified_native_archive():
    x=_policy(ui_mode="offline",native_archive_available=True,
              has_channels=True,has_values=True)
    assert not x.panel_visible
    assert x.local_table_enabled and x.local_adc_enabled
    assert x.local_values_enabled
    assert not x.freeze_preview_enabled
    y=_policy(ui_mode="offline",technical_ui=True,
              native_archive_available=False,has_channels=True,
              has_values=True)
    assert y.panel_visible
    assert y.local_adc_enabled
    assert not y.local_table_enabled
    assert not y.local_values_enabled


@pytest.mark.parametrize("key",(
    "mode2_selected","capture_active","technical_ui",
    "native_archive_available","has_channels","has_values",
))
def test_rejects_non_boolean_capture_evidence(key):
    with pytest.raises(ValueError):
        _policy(**{key:1})


def test_rejects_contradictory_native_and_ui_state():
    with pytest.raises(ValueError):
        _policy(capture_active=True,mode2_selected=False,ui_mode="live")
    with pytest.raises(ValueError):
        _policy(capture_active=True,mode2_selected=True,ui_mode="idle")
    with pytest.raises(ValueError):
        _policy(ui_mode="live",capture_active=False,mode2_selected=True)
    with pytest.raises(ValueError):
        _policy(ui_mode="measurement",mode2_selected=True)
