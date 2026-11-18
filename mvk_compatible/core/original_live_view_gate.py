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
    if proof.stream_silent or proof.data_integrity_alert:
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
        if type(number) is not int or not 1 <= number <= 8 or ch.number != number:
            return deny("Нарушен порядок АЦП", "CHANNEL_MISMATCH")
        source = channels[number - 1]
        rates = source.get("sample_rates_hz")
        samples = source.get("samples")
        if (source.get("channel") != number or source.get("type") != "ADC"
                or type(samples) is not int or samples < 0
                or not isinstance(rates, list) or ch.rate_hz not in rates
                or type(ch.first_index) is not int
                or type(ch.next_index) is not int
                or samples<len(ch.samples)
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
        # Original source SampleHeader.Index is absolute; the JSON
        # "samples" above counts ONLY bytes captured during this session.
        # The previous <= samples test rejected valid late-attach windows.
        source_end=source.get("next_sample_index")
        if not u32_matches_go_status(
                ch.next_index,source_end,status_samples=samples,
                window_samples=len(ch.samples),
                captured_samples=ch.captured_samples):
            return deny("Абсолютный индекс АЦП не подтверждён Go",
                        "SOURCE_INDEX_MISMATCH")
    return LivePreviewDecision(True, "Подтверждённый Native preview",
                               "RECORDING")
