"""Delphi MVKView Mode2 connection state independent of UI navigation.

IDR project mvkview.idp / extracted _Unit128.pas:
  bTaskConnectClick 00848E78 sets Mode 2
  00846D24..00846D5C shows PageStatus/Adc/Spectrum/File
  00846D79..00846D84 shows pnMeasure
  00846DCC creates TMVKThread AFTER those transitions
  00848B06..00848BC9 paints thread.Status/StatusIsError
No device command, port probe, or assumed original thread status.
"""
from __future__ import annotations

from dataclasses import dataclass
from .original_connected_status import connected_system_status

SOURCE="IDR_00848E78_00846D24_00846DCC_00848B06"


@dataclass(frozen=True)
class SourceConnectionDisplay:
    selected:bool
    capture_started:bool
    transport_verified:bool
    text:str
    indicator:str
    phase:str

    def receipt(self):
        return {
            "source":SOURCE,
            "mode2_entered":self.selected,
            "native_capture_started":self.capture_started,
            "verified_readonly_transport":self.transport_verified,
            "original_tmkvthread_status_values_recovered":False,
            "physical_connection_implied_by_tabs":False,
            "device_commands_issued":False,
        }


def source_connection_display(*,selected:bool,capture_started:bool=False,
        status:dict|None=None,failure:bool=False,
        stop_requested:bool=False)->SourceConnectionDisplay:
    if (type(selected) is not bool or type(capture_started) is not bool
            or type(failure) is not bool or type(stop_requested) is not bool):
        raise ValueError("Source Mode2/state arguments must be booleans")
    if capture_started and not selected:
        raise ValueError("Recorder cannot precede Mode2 selection")
    if status is not None and not capture_started:
        raise ValueError("Unstarted recorder cannot report Native status")
    if stop_requested and (not selected or not capture_started):
        raise ValueError("Source stop requires an active selected Mode2 capture")
    if not selected:
        if failure:
            raise ValueError("Idle state cannot inherit connection error")
        return SourceConnectionDisplay(
            False,False,False,"Нет подключения к прибору","none","IDLE")
    if failure:
        return SourceConnectionDisplay(
            True,capture_started,False,
            "Ошибка соединения с прибором","bad","ERROR")
    if stop_requested:
        # A queued Go status cannot restore a green 'connected' lamp
        # after the operator already requested graceful termination.
        return SourceConnectionDisplay(
            True,True,False,"Завершение приёма","waiting","STOPPING")
    if not capture_started:
        return SourceConnectionDisplay(
            True,False,False,
            "Ожидание подключения к прибору","waiting","MODE2")
    if status is None:
        return SourceConnectionDisplay(
            True,True,False,
            "Ожидание данных прибора","waiting","CONNECTING")
    proof=connected_system_status(status)
    if proof.stream_silent:
        return SourceConnectionDisplay(
            True,True,False,
            "Нет новых данных прибора","bad","SILENT")
    if proof.connection_verified and proof.data_integrity_alert:
        return SourceConnectionDisplay(
            True,True,True,
            "Ошибки входного потока","bad","STREAM_ERRORS")
    if proof.connection_verified:
        return SourceConnectionDisplay(
            True,True,True,
            "Подключен к прибору","good",proof.transport_phase)
    if proof.transport_phase=="REFUSED":
        return SourceConnectionDisplay(
            True,True,False,
            "Ошибка соединения с прибором","bad","REFUSED")
    if status["snapshot_stale"]:
        return SourceConnectionDisplay(
            True,True,False,
            "Нет актуальных данных прибора","bad","STALE")
    if proof.transport_phase=="VERIFYING":
        return SourceConnectionDisplay(
            True,True,False,
            "Проверка записи","waiting","VERIFYING")
    if proof.transport_phase=="COMPLETED":
        return SourceConnectionDisplay(
            True,True,False,
            "Запись завершена · проверка архива","waiting","COMPLETED")
    return SourceConnectionDisplay(
        True,True,False,
        "Ожидание данных прибора","waiting",proof.transport_phase)


@dataclass(frozen=True)
class CaptureCompletionPolicy:
    """Compatible archive provenance after Native capture ends.

    This is a Qt/Core safety policy, NOT an undocumented original
    TMVKThread/device command. A verified archived ZIP may be reopened,
    but a failed connection must never be shown as a successful one.
    """
    keep_mode2:bool
    connection_error:bool
    reopen_prior_archive:bool
    accepted_new_archive:bool

    def receipt(self):
        return {
            "source":"COMPATIBLE_NATIVE_CAPTURE_ARCHIVE_RECOVERY",
            "keep_original_mode2_tabs":self.keep_mode2,
            "verified_connection_implied":False,
            "reopen_only_previously_verified_archive":self.reopen_prior_archive,
            "accepted_new_export":self.accepted_new_archive,
            "device_commands_issued":False,
        }


def capture_completion_policy(*,exported:bool,
        operator_exit_requested:bool,has_parked_archive:bool)->CaptureCompletionPolicy:
    """Do not lose a verified offline session on Mode2 or failed TCP.

    Mode2 remains visible on a failed connection until the operator
    explicitly exits; a successful export leaves Mode2 and is accepted
    only by the existing archiveReady -> OfflineSession.open flow.
    """
    if any(type(v) is not bool for v in (
            exported,operator_exit_requested,has_parked_archive)):
        raise ValueError("Capture completion evidence must be booleans")
    return CaptureCompletionPolicy(
        keep_mode2=not exported and not operator_exit_requested,
        connection_error=not exported and not operator_exit_requested,
        reopen_prior_archive=not exported and has_parked_archive,
        accepted_new_archive=exported,
    )
