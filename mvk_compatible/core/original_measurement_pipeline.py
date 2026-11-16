"""Original MVKView 1.0.47 Mode2 source-derived operator policy.

Offline evidence: private Projects.7z/_Unit128.pas and _Unit125.pas,
original mvkform.dfm, and local mvkview.idp. No source vendor assets,
device commands, credentials, captures or private paths are embedded.

A VERIFIED source action != a verified compatible hardware action.
This module centralizes the former and explicitly gates the latter.
"""
from __future__ import annotations

from dataclasses import dataclass

ORIGINAL_MODE2_ENTRY="00848E78"
ORIGINAL_MODE_DISPATCH="00846AD4"
ORIGINAL_MODE2_TABS="00846D24..00846D84"
ORIGINAL_THREAD_CONSTRUCT="00846DCC"
ORIGINAL_THREAD_EXECUTE="00807A98"
ORIGINAL_MODE_RESET="00847040"
ORIGINAL_TIMER_DISPATCH="00847248"
ORIGINAL_MEASURE_TIMER_MS=20
ORIGINAL_CONFIG_TIMER_MS=200
ORIGINAL_ADC_COUNT=8
ORIGINAL_TACH_COUNT=2
ORIGINAL_RING_CAPACITY_PER_CHANNEL_BYTES=0x200000
ORIGINAL_TRANSPORT_PORT=10230
ORIGINAL_CONNECT_TIMEOUT_MS=1000
ORIGINAL_READ_TIMEOUT_MS=5000
ORIGINAL_RATE_MENU_ITEMS=5

# Source exception types and handlers, NOT validated Native R6.1 fault
# categories. Do not infer network causality from a local JSON failure.
ORIGINAL_THREAD_ERRORS=(
    ("closed","EIdConnClosedGracefully","008088A2"),
    ("read_timeout","EIdReadTimeout","008088CE"),
    ("connect_timeout","EIdConnectTimeout","008088FA"),
    ("network","EIdException","00808923"),
    ("invalid_packet","errInvalidPacket","00807FA1"),
    ("command_denied","errOperationDenied","008080AC"),
    ("system_status","thrSystemError","00808736"),
)

# The real Delphi source sets these flags or invokes these methods.
# Current Go R6.1 remains strictly passive; writable source actions
# are NOT implemented by calling an invented native command.
ORIGINAL_MEASURE_ACTIONS=(
    ("bTaskConnect","bTaskConnectClick","00848E78","Mode2 and TMVKThread"),
    ("bFreezeUpdate","bFreezeUpdateClick","0084DEA4","FreezeUpdate flag"),
    ("bSampleRate","mRate1Click","0084DEC4","SetRate queued write"),
    ("bWriteTable","bWriteTableClick","0084E020","source TABLE file"),
    ("bWriteAdc","bWriteAdcClick","0084E914","WriteData + 10 channel masks"),
    ("bWriteValues","bWriteValuesClick","0084E988","WriteValues + selections"),
    ("tmInterfaceUpdate","tmInterfaceUpdateTimer","0084F7C8","page and toolbar refresh"),
)


@dataclass(frozen=True)
class MeasurementOperatorPolicy:
    panel_visible:bool
    freeze_preview_enabled:bool
    rate_inspection_enabled:bool
    local_table_enabled:bool
    local_adc_enabled:bool
    local_values_enabled:bool
    original_set_rate_enabled:bool=False
    original_device_write_enabled:bool=False

    def receipt(self)->dict:
        return {
            "source":"ORIGINAL_IDR_MODE2_OPERATOR_POLICY",
            "panel_visible":self.panel_visible,
            "freeze_preview_enabled":self.freeze_preview_enabled,
            "rate_read_only":True,
            "original_tmkvthread_set_rate_enabled":self.original_set_rate_enabled,
            "original_tmkvthread_device_writes_enabled":self.original_device_write_enabled,
            "go_transport_read_only":True,
            "original_signal_spectrum_numeric_parity_proven":False,
        }


def measurement_operator_policy(*,ui_mode:str,mode2_selected:bool,
        capture_active:bool,technical_ui:bool,
        native_archive_available:bool,has_channels:bool,
        has_values:bool)->MeasurementOperatorPolicy:
    """One Core policy for original visibility + actual compatible actions.

    mode2_selected is a user choice BEFORE any socket, never proof of
    actual connectivity. Offline exports require accepted immutable data.
    """
    if ui_mode not in ("idle","offline","live"):
        raise ValueError("Unknown source measurement UI mode")
    if any(type(v) is not bool for v in (
            mode2_selected,capture_active,technical_ui,
            native_archive_available,has_channels,has_values)):
        raise ValueError("Measurement evidence must use strict booleans")
    if capture_active and not mode2_selected:
        raise ValueError("Native receiver cannot precede original Mode2")
    if (ui_mode=="live") != capture_active:
        raise ValueError("Native live UI and receiver state disagree")
    offline=(ui_mode=="offline" and not mode2_selected)
    native=offline and native_archive_available
    return MeasurementOperatorPolicy(
        panel_visible=mode2_selected or capture_active or (
            offline and technical_ui),
        freeze_preview_enabled=capture_active,
        rate_inspection_enabled=capture_active or offline,
        local_table_enabled=native,
        local_adc_enabled=offline and has_channels,
        local_values_enabled=native and has_channels and has_values,
    )


def original_measurement_source_summary()->dict:
    """Safe metadata only: source-trace checkpoints and not a driver."""
    return {
        "entry_address":ORIGINAL_MODE2_ENTRY,
        "mode_dispatch_address":ORIGINAL_MODE_DISPATCH,
        "visible_tabs_before_tcp":5,
        "adc_count":ORIGINAL_ADC_COUNT,
        "tach_count":ORIGINAL_TACH_COUNT,
        "channel_buffer_bytes":ORIGINAL_RING_CAPACITY_PER_CHANNEL_BYTES,
        "timer_ms":ORIGINAL_MEASURE_TIMER_MS,
        "config_timer_ms":ORIGINAL_CONFIG_TIMER_MS,
        "tcp_port":ORIGINAL_TRANSPORT_PORT,
        "connect_timeout_ms":ORIGINAL_CONNECT_TIMEOUT_MS,
        "read_timeout_ms":ORIGINAL_READ_TIMEOUT_MS,
        "sample_rate_menu_item_count":ORIGINAL_RATE_MENU_ITEMS,
        "sample_rate_menu_values_verified":False,
        "source_command_queue_exists":True,
        "source_set_rate_is_device_command":True,
        "safe_native_r6_1_write_command_supported":False,
        "same_device_original_parity_proven":False,
    }
