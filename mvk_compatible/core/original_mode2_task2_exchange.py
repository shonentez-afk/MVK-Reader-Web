"""Autonomous TMVKThread Task=2 exchange replay. NO HARDWARE ACCESS.

Source (PRIVATE _Unit125.pas, read directly):
  00807BC2 -> 00807CE0: Stage=0, new TCP client; connected != ready.
  00807E8F -> 00807F67: while Stage=1, dequeue ONE TList command
                        BEFORE the next incoming ReadUInt32.
  0080937C: eight little-endian Indy WriteUInt32 calls; for rate
            command 00807F52 writes ninth Data word.
  0080807B: incoming ACK logs operation success but Task=2 does NOT
            change Stage or correlate this response with SetRate.
  008080AC: incoming DENIED raises errOperationDenied.
  0080839E -> 00808617: nonempty valid PARAM changes Stage0->1.
  00808238 -> 0080828C: sample-rate mismatch or FreezeUpdate skips
                        ProcessBufferChunk, not incoming TCP bytes.
  008089A3 -> 00808B0E: Task2 error resets Stage0; first attempt
                        unconditionally enqueues SetRate, then backoff.

This is an executable source semantics model for tests and independent
clients. It does not create a socket, timer, QProcess or Go recorder;
receipt never claims physical source measurement or successful command ACK.
"""
from __future__ import annotations

from .original_mode2_command_queue import (
    OriginalMode2CommandQueue, OriginalMode2FaultRoutes, RATE_ADDRESS,
    RATE_COMMAND, SOURCE_EXCEPTION_ROUTES, SOURCE_INTERNAL_ERROR_ROUTES,
)
from .original_mode2_rate_menu_source import (
    SOURCE_DEFAULT_MENU_TAG, validate_original_rate_tag,
)
from .original_mode2_received_frames import (
    OriginalSourceReadFramer, OriginalSourceRxError,
    OriginalSourceOperationDenied,
)
from .original_mode2_retry_timing import OriginalSourceRetryPlan
from .original_mode2_wire_word_candidate import plan_verified_source_rate_command

SOURCE = "IDR_00807BC2_00807F52_TASK2_OFFLINE_EXCHANGE"
HISTORY_LIMIT = 64


class OriginalTask2OfflineExchange:
    """Deterministic source Task2 exchange with NO outgoing device I/O."""

    def __init__(self):
        self.queue = OriginalMode2CommandQueue()
        self.faults = OriginalMode2FaultRoutes()
        self.retry_plan = OriginalSourceRetryPlan()
        self.receiver = OriginalSourceReadFramer(
            source_rate_tag=SOURCE_DEFAULT_MENU_TAG)
        self.started = False
        self.connected = False
        self.connection_phase = "IDLE"
        self.stopped = False
        self.freeze_update = False
        self.seen_ack = 0
        self.seen_deny = 0
        self.sent_calls_offline = 0
        self._history: list[dict] = []
        self._events_total = 0
        self.last_source_error: str | None = None

    def _remember(self, name: str, **details):
        self._events_total += 1
        self._history.append({
            "event": name,
            "ordinal": self._events_total,
            **details,
        })
        if len(self._history) > HISTORY_LIMIT:
            del self._history[:-HISTORY_LIMIT]

    def start(self):
        """Original post-TMVKThread.Create mRate1Click(Items[0])."""
        if self.started or self.stopped:
            raise ValueError("Source Task2 already started or terminated")
        self.started = True
        # Source Thread.Execute starts a Connect attempt while Stage0.
        # This phase must exist independently of an accepted TCP socket.
        self.connection_phase = "CONNECTING"
        self.queue.set_rate(SOURCE_DEFAULT_MENU_TAG)
        self._remember("SOURCE_MODE2_MRATE1CLICK", tag=SOURCE_DEFAULT_MENU_TAG)
        return self.receipt()

    def tcp_connected_in_offline_model(self):
        if (not self.started or self.stopped or self.connected or
                self.connection_phase!="CONNECTING"):
            raise ValueError("Cannot simulate source TCP connection")
        self.connected = True
        self.connection_phase = "CONNECTED"
        # Each new TCP client begins with Stage0 and a new receive framer;
        # the TList queue persists over source reconnect attempts.
        self.receiver = OriginalSourceReadFramer(
            source_rate_tag=self.queue.source_rate_code)
        self.receiver.freeze(self.freeze_update)
        self.retry_plan.connected()
        self.last_source_error = None
        self._remember("SOURCE_TCP_CONNECTED_STAGE0")
        return self.receipt()

    def begin_next_retry_attempt(self):
        """Simulate end of source waiting/sleep, without a timer or TCP."""
        if (not self.started or self.stopped or self.connected or
                self.connection_phase!="WAITING_RETRY"):
            raise ValueError("No source Task2 retry is waiting")
        self.connection_phase="CONNECTING"
        self._remember("SOURCE_RETRY_ATTEMPT_BEGINS_OFFLINE")
        return self.receipt()

    def select_original_rate(self, rate_tag: int):
        validate_original_rate_tag(rate_tag)
        if not self.started or self.stopped:
            raise ValueError("Cannot change rate outside modeled Task2")
        command = self.queue.set_rate(rate_tag)
        self.receiver.set_rate_after_original_menu_click(rate_tag)
        self._remember(
            "SOURCE_MRATE1CLICK",
            tag=rate_tag, command_queued=command is not None)
        return self.receipt()

    def set_freeze(self, frozen: bool):
        if type(frozen) is not bool or not self.started or self.stopped:
            raise ValueError("Source FreezeUpdate requires modeled Task2")
        self.freeze_update = frozen
        self.receiver.freeze(frozen)
        self._remember("SOURCE_FREEZE_UPDATE_CLICK", value=frozen)
        return self.receipt()

    def before_next_source_read(self):
        """One original FIFO send at Stage=1, but only in a dry-run ledger."""
        if not self.connected or self.stopped:
            raise ValueError("No modeled source connection")
        command=self.queue.take_one(self.receiver.stage)
        if command is None:
            return None
        plan=plan_verified_source_rate_command(command)
        event=plan.receipt()
        event["source_queue_ordinal"]=command.ordinal
        event["source_tcp_bytes_physically_sent"]=False
        self.sent_calls_offline += 1
        self._remember("SOURCE_WRITE_UINT32_DRY_RUN",
                       ordinal_in_queue=command.ordinal,
                       words=len(plan.all_words),
                       value=command.data)
        return event

    def receive(self, chunk: bytes):
        """Process only source-supported incoming frames, never send a reply."""
        if not self.connected or self.stopped:
            raise ValueError("Modeled Source TCP must be connected first")
        try:
            frames=self.receiver.feed(chunk)
        except OriginalSourceOperationDenied:
            self.seen_deny+=1
            self._source_failure("operation_denied", internal=True)
            raise
        except OriginalSourceRxError:
            self._source_failure("invalid_packet", internal=True)
            raise
        for f in frames:
            if f.kind=="ACK_OBSERVED":
                self.seen_ack+=1
                # Source 0080807B for Task2 logs; does not set Stage2.
                self._remember("SOURCE_INCOMING_ACK_UNATTRIBUTED")
            elif f.kind=="PARAM" and f.register_block_count:
                self._remember("SOURCE_RECEIVED_PARAM_STAGE1",
                               register_blocks=f.register_block_count)
            elif f.kind in ("ADC","TACH"):
                self._remember("SOURCE_BUFFER_CHUNK",
                               channel=f.channel,
                               processed=f.processed)
            elif f.kind=="UNKNOWN_DRAIN":
                self._remember("SOURCE_UNKNOWN_PACKET_DRAINED")
        return frames

    def _source_failure(self, kind: str, *, internal: bool):
        if self.stopped or self.connection_phase not in ("CONNECTING","CONNECTED"):
            raise ValueError("Source Task2 failure without an attempt")
        if internal:
            if kind not in SOURCE_INTERNAL_ERROR_ROUTES:
                raise ValueError("Not a source internal failure")
            self.faults.record_source_internal_error(kind)
        else:
            if kind not in SOURCE_EXCEPTION_ROUTES:
                raise ValueError("Unverified source network failure")
            self.faults.record_source_exception(kind)
        self.connected=False
        self.connection_phase="WAITING_RETRY"
        self.last_source_error=kind
        # On source network exception the old Client is freed, stage is
        # reset, TList remains. 008089D8 invokes 00809364 directly
        # on initial PauseValue<26: source code does NOT test duplicates.
        self.receiver.stage=0
        step=self.retry_plan.after_failure()
        if step.source_requeues_set_rate:
            self.queue.queue_command(
                RATE_COMMAND,RATE_ADDRESS,self.queue.source_rate_code)
        self._remember("SOURCE_TASK2_ERROR_RETRY_PLAN",
                       fault=kind, wait_ms=step.local_wait_ms,
                       source_queued_rate=step.source_requeues_set_rate)
        return step

    def source_transport_failure(self, kind: str):
        """SOURCE typed exception, never inferred from a Go JSON field."""
        return self._source_failure(kind,internal=False)

    def stop(self):
        if self.stopped:
            return self.receipt()
        self.stopped=True
        self.connected=False
        self.connection_phase="STOPPED"
        self.queue.shutdown()
        self.faults.finish()
        self._remember("SOURCE_OPERATOR_STOP")
        return self.receipt()

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "model_only": True,
            "source_task": 2,
            "source_started": self.started,
            "source_tcp_connected_simulated": self.connected,
            "source_connection_phase_simulated": self.connection_phase,
            "source_connect_timeout_can_fail_before_tcp": True,
            "original_stage_simulated": self.receiver.stage,
            "original_sample_rate_tag": self.queue.source_rate_code,
            "freeze_update_processing_simulated": self.freeze_update,
            "buffer_chunks_processed_simulated":
                self.receiver.source_data_processed,
            "buffer_chunks_drained_simulated":
                self.receiver.source_data_drained,
            "source_acks_observed_unattributed": self.seen_ack,
            "source_denied_exceptions_simulated": self.seen_deny,
            "source_dry_run_write_call_plans": self.sent_calls_offline,
            "source_retry": self.retry_plan.receipt(),
            "command_list": self.queue.receipt(),
            "source_faults": self.faults.receipt(),
            "last_source_error": self.last_source_error,
            "source_stopped": self.stopped,
            "history_total": self._events_total,
            "last_source_events": tuple(self._history[-12:]),
            "real_native_go_packets_changed": False,
            "physical_tcp_client_created": False,
            "original_setrate_ack_proven": False,
            "original_hardware_parity_verified": False,
            "device_commands_sent": 0,
        }
