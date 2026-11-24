"""Source Mode2 live-presentation gate; read-only verified stream only.

The original TMVKThread GUI timer cannot authenticate Native R6.1's
asynchronously emitted Qt status/preview signals. This gate prevents an old
preview (even one with a valid ZIP SHA) from reappearing after TCP failure,
stream corruption, a session switch, or the operator's Stop request.
It does not send commands or claim Delphi numerical parity.
"""
from __future__ import annotations

from dataclasses import dataclass

from .native_r6_live_preview import LivePreview
from .original_source_ring_receipt import (
    source_live_range_matches,TACH_DOMAIN,source_channel_epoch,
    source_epoch_recovery_pending,source_epoch_recovery_possible,
)
import numpy as np
from .original_sample_cursor32 import u32_preview_bounds,u32_matches_go_status
from .original_connected_status import connected_system_status

SOURCE = "STAGE111Z31DB_SOURCE_MODE2_LIVE_PREVIEW_GATE"


@dataclass(frozen=True)
class LivePreviewDecision:
    allowed: bool
    reason: str
    phase: str

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "allow_source_live_preview": self.allowed,
            "phase": self.phase,
            "reason": self.reason,
            "only_verified_same_native_run": True,
            "original_delphi_live_parity_verified": False,
            "device_commands_sent": False,
        }


def gate_live_preview(status: dict | None, preview: LivePreview | None, *,
                      stop_requested: bool = False) -> LivePreviewDecision:
    """Validate real-time presentation AFTER the Native ZIP/status validators.

    A verified preview file by itself is not evidence that the current
    capture is still receiving healthy frames. Check the latest status
    again at the MainWindow slot, after any queued stop/error Qt signals.
    Older sparse test status receipts cannot authorize live samples.
    """
    deny = lambda reason, phase: LivePreviewDecision(False, reason, phase)
    if type(stop_requested) is not bool:
        raise ValueError("Stop request must be a Boolean")
    if stop_requested:
        return deny("Остановка приёма запрошена", "STOPPING")
    if not isinstance(preview, LivePreview):
        return deny("Нет проверенного окна отсчётов", "NO_PREVIEW")
    if status is None:
        return deny("Нет действительного статуса текущего приёмника", "NO_STATUS")
    try:
        proof = connected_system_status(status)
    except (ValueError, TypeError, KeyError):
        return deny("Статус Native не прошёл проверку", "REJECTED")
    phase = proof.transport_phase
    if not proof.connection_verified or phase != "RECORDING":
        return deny("Нет подтверждённого действующего потока", phase)
    recovery = source_epoch_recovery_pending(status)
    # A renewed, independently bounded source ring may be viewed even
    # though global Native sequence counters retain a prior Fs/socket gap.
    # Faults, unverified windows and historical nonfinite ADC still fail closed.
    scoped = (recovery and source_epoch_recovery_possible(status)
              and preview.source_ring_provenance_verified is True
              and proof.native_invalid_frames == 0 and proof.native_nonfinite_samples == 0
              and not proof.source_system_error_observed)
    if (proof.stream_silent or (proof.data_integrity_alert and not scoped)
            or (recovery and not scoped)):
        return deny("Поток остановлен или содержит ошибки", "STREAM_ERRORS")
    if status.get("capture_only") is not False:
        return deny("Нет подтверждённого потока Float32", "CAPTURE_ONLY")
    if (not isinstance(status.get("session_id"), str) or
            preview.session_id != status["session_id"]):
        return deny("Данные принадлежат другому сеансу", "FOREIGN_RUN")
    if (type(preview.frames_decoded) is not int or
            type(preview.raw_bytes) is not int or
            preview.frames_decoded < 0 or preview.raw_bytes < 0 or
            preview.frames_decoded > status["frames_decoded"] or
            preview.raw_bytes > status["raw_bytes"]):
        return deny("Окно новее проверенного TCP-статуса", "COUNTER_MISMATCH")
    channels = status.get("channels")
    if not isinstance(channels, list) or len(channels) != 10:
        return deny("Нет подтверждённых десяти каналов", "CHANNEL_MISMATCH")
    if not isinstance(preview.channels, dict) or not preview.channels:
        return deny("Нет измеренных АЦП", "NO_CHANNEL")
    for number, ch in preview.channels.items():
        if type(number) is not int or not 1 <= number <= 10 or ch.number != number:
            return deny("Нарушен порядок АЦП", "CHANNEL_MISMATCH")
        is_tach=number>=9
        if is_tach and (preview.input_domain!=TACH_DOMAIN or
                preview.source_ring_provenance_verified is not True or
                ch.samples.dtype!=np.dtype("u1") or ch.source_range_state is not None or
                ch.source_f_range_single!=1.0):
            return deny("TACH requires verified source Byte storage","CHANNEL_MISMATCH")
        if not is_tach and preview.input_domain==TACH_DOMAIN:
            return deny("ADC cannot read TACH Byte storage","CHANNEL_MISMATCH")
        wire_factor=4 if is_tach else 1
        source = channels[number - 1]
        rates = source.get("sample_rates_hz")
        samples = source.get("samples")
        if (source.get("channel") != number or source.get("type") != ("TACH" if is_tach else "ADC")
                or type(samples) is not int or samples < 0
                or not isinstance(rates, list) or ch.rate_hz not in rates
                or type(ch.first_index) is not int
                or type(ch.next_index) is not int
                or samples*wire_factor<len(ch.samples)
                or not u32_preview_bounds(
                    ch.first_index,ch.next_index,len(ch.samples))):
            return deny("Нарушены исходные границы или частота АЦП",
                        "CHANNEL_MISMATCH")
        # Unlike the forensic Native preview, the original Delphi
        # TMvkChannelStorage does NOT record packets discarded by
        # MvkSampleRate mismatch or FreezeUpdate. A valid preview ZIP
        # can still contain those excluded samples: wait until its ENTIRE
        # selected window follows the last excluded native sample.
        source_gate=(status.get("source_original_receive_gate")
                     if status.get("source_original_receive_gate_verified") is True
                     else None)
        full_ring=(status.get("source_original_storage")
                   if status.get("source_original_storage_verified") is True
                   else None)
        # Original GetSignal AND GetSpectrum read the accepted FRxPos
        # ring, never the Native all-TCP counter after FreezeUpdate.
        # Source provenance is an explicit SHA-verified local IPC fact;
        # sample count NEVER identifies it. Short windows can be just
        # 32768 elements even though source ring has 2**21 capacity.
        from_source_ring=(preview.source_ring_provenance_verified is True)
        if from_source_ring and full_ring is None:
            return deny("Отсутствует проверенное исходное 2M кольцо",
                        "SOURCE_RING_UNVERIFIED")
        if not from_source_ring and len(ch.samples)>262144:
            return deny("Длинное окно не из проверенного кольца Go",
                        "SOURCE_RING_UNVERIFIED")
        if from_source_ring:
            row=full_ring["channels"][number-1]
            try:
                epoch=source_channel_epoch(status,row)
            except (ValueError,KeyError,TypeError):
                return deny("Неподтверждённая эпоха кольца", "SOURCE_RING_STALE")
            if (epoch!=ch.source_epoch or
                    (recovery and epoch is None) or
                    (epoch is not None and (ch.captured_samples is None or
                     ch.captured_samples-len(ch.samples)<epoch["start_pos_64"]))):
                return deny("Исходное окно из прошлой TCP/Fs эпохи",
                            "SOURCE_RING_STALE")
            if (recovery and (source_gate is None or
                    source_gate["selected_rate_hz"]!=ch.rate_hz or
                    (not is_tach and (ch.source_range_state or {}).get(
                        "socket_attempt")!=epoch["socket_attempt"]))):
                return deny("Нет актуального выбранного Fs/Range",
                            "SOURCE_RING_STALE")
            valid_domain=(row.get("input_domain")==TACH_DOMAIN and
                row.get("sample_width_bytes")==1 if is_tach else
                source_live_range_matches(row,preview.input_domain,
                    ch.source_f_range_single,ch.source_range_state))
            if (source_gate is not None and source_gate["freeze_update"] or
                    not valid_domain or
                    row.get("last_sample_rate_hz",ch.rate_hz)!=ch.rate_hz or
                    ch.captured_samples is None or
                    ch.captured_samples<len(ch.samples) or
                    ch.captured_samples>row["rx_pos_64"] or
                    ch.captured_samples-len(ch.samples)<
                    row["first_readable_pos_64"]):
                return deny("Исходный длинный сигнал больше не находится "
                            "в подтверждённом кольце", "SOURCE_RING_STALE")
            status_count=row["rx_pos_64"]
            status_index=row["next_device_sample_index"]
            if is_tach:
                if (type(status_index) is not int or
                        ch.captured_samples%4 or
                        (status_count-ch.captured_samples)%4):
                    return deny("TACH Byte/word cursor mismatch","SOURCE_INDEX_MISMATCH")
                status_index=(status_index*4)&0xffffffff
        else:
            if source_gate is not None:
                admitted=source_gate["channels"][number-1]
                last_excluded=admitted["last_skipped_native_samples"]
                if (last_excluded and
                        (ch.captured_samples is None or
                         ch.captured_samples<len(ch.samples) or
                         ch.captured_samples-len(ch.samples)<last_excluded)):
                    return deny(
                        "Окно содержит отсчёты, исключённые исходным "
                        "MvkSampleRate/FreezeUpdate",
                        "SOURCE_STORAGE_EXCLUDED")
            status_count=samples
            status_index=source.get("next_sample_index")
        # Original source SampleHeader.Index is absolute and uint32;
        # local Native.Samples or original ring FRxPos are independent
        # uint64 counters. Only the matched provenance is compared.
        if not u32_matches_go_status(
                ch.next_index,status_index,status_samples=status_count,
                window_samples=len(ch.samples),
                captured_samples=ch.captured_samples):
            return deny("Абсолютный индекс АЦП не подтверждён Go",
                        "SOURCE_INDEX_MISMATCH")
    return LivePreviewDecision(True, "Подтверждённый Native preview",
                               "RECORDING")
