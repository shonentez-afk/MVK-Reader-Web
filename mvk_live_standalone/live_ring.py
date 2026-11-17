"""Bounded per-ADC display buffers inspired by CortexTrace's SPSC architecture.

The verified Native R6.1 preview loader is the sole producer. This module
does not open TCP sockets, modify the 2^21 Go rings or reapply calibration.
The uint64 capture counter prevents duplicate frame insertion and fake time.
Each read is an isolated copy suitable for asynchronous FFT processing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

CAPACITY = 262144
DOMAIN = "CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32"
UINT32 = 1 << 32


@dataclass
class ChannelBuffer:
    number: int
    capacity: int

    def __post_init__(self) -> None:
        self._data = np.empty(self.capacity, dtype="<f4")
        self.rate_hz: int = 0
        self.next_device_index: int | None = None
        self.end: int = 0  # uint64 count within the session, not device index
        self.available: int = 0
        self.last_sha: str = ""
        self.lost_samples: int = 0
        self.resets: int = 0

    def latest(self, count: int) -> np.ndarray:
        """Ordered independent copy; refuse insufficient real samples."""
        if not isinstance(count, int) or count < 1 or count > self.available:
            raise ValueError("Not enough contiguous, validated ADC samples")
        start = (self.end - count) % self.capacity
        if start + count <= self.capacity:
            return self._data[start:start + count].copy()
        n = self.capacity - start
        return np.concatenate((self._data[start:], self._data[:count-n]))

    def _append(self, values: np.ndarray, end: int) -> None:
        n = len(values)
        assert 0 < n <= self.capacity
        start = (end-n) % self.capacity
        first = min(n, self.capacity-start)
        self._data[start:start+first] = values[:first]
        if n > first:
            self._data[:n-first] = values[first:]
        self.end = end
        self.available = min(self.capacity, self.available+n)

    def ingest(self, channel: Any) -> bool:
        """Consume a validated Native ZIP channel, appending only new samples.

        load_live_preview() is responsible for SHA, session, domain, absolute
        device cursor, rate, frame integrity and freshness validation.
        """
        samples = np.asarray(channel.samples)
        total = channel.captured_samples
        rate = channel.rate_hz
        next_index = channel.next_index
        digest = channel.sha256
        if (
            type(total) is not int or total < len(samples) or total >= (1 << 64)
            or type(rate) is not int or rate < 1 or rate > 1_000_000
            or type(next_index) is not int or not 0 <= next_index < UINT32
            or samples.ndim != 1 or not 0 < len(samples) <= self.capacity
            or not np.all(np.isfinite(samples))
            or not isinstance(digest, str) or len(digest) != 64
        ):
            raise ValueError("Unverified or inconsistent Native channel receipt")
        if self.available and total == self.end:
            if next_index != self.next_device_index:
                raise ValueError("Same Native counter but different device index")
            if digest == self.last_sha:
                return False
            # The operator may raise FFT N while no new packet arrives.
            # A longer verified IPC window at the SAME end is legitimate
            # only if its overlap is byte-for-byte identical to our history.
            overlap=min(self.available,len(samples))
            if not np.array_equal(self.latest(overlap),samples[-overlap:]):
                raise ValueError("Same Native counter but different data")
            if len(samples)<=self.available:
                return False
            self.available=0
            self._append(np.asarray(samples,dtype="<f4"),total)
            self.last_sha=digest
            return True
        if self.available and total < self.end:
            raise ValueError("Native capture counter regressed within session")
        delta = total-self.end if self.available else len(samples)
        # Missing previews, device cursor gaps and rate changes invalidate the
        # old contiguous history; restart with only real samples in this ZIP.
        discontinuity = self.available and (
            (total-self.end > len(samples))
            or (self.next_device_index is not None and
                ((self.next_device_index + total-self.end) % UINT32 != next_index))
            or self.rate_hz != rate
        )
        if discontinuity:
            self.lost_samples += max(0, total-self.end-len(samples))
            self.available = 0
            self.resets += 1
            delta = len(samples)
        if not self.available:
            delta = len(samples)
        self._append(np.asarray(samples[-delta:],dtype="<f4"),total)
        self.rate_hz = rate
        self.next_device_index = next_index
        self.last_sha = digest
        return True


class VerifiedLiveRing:
    """Eight independent calibrated ADC display rings; TACH remains in Go.

    Do not copy CortexTrace's single shared cursor: each MVK channel may have
    a distinct device sample position and sample rate.
    """

    def __init__(self, *, capacity: int = CAPACITY) -> None:
        if type(capacity) is not int or capacity < 1 or capacity > CAPACITY:
            raise ValueError("Invalid display ring capacity")
        self.capacity = capacity
        self.session_id: str | None = None
        self.channels: dict[int,ChannelBuffer] = {}

    def clear(self) -> None:
        self.session_id = None
        self.channels.clear()

    def channel(self, number: int) -> ChannelBuffer | None:
        return self.channels.get(number)

    def ingest_preview(self, preview: Any) -> set[int]:
        if (not isinstance(preview.session_id,str) or not preview.session_id
                or preview.input_domain != DOMAIN or preview.provisional is not True
                or not isinstance(preview.channels,dict)):
            raise ValueError("Only provenance-verified calibrated Native previews accepted")
        if self.session_id is not None and self.session_id != preview.session_id:
            self.clear()
        self.session_id = preview.session_id
        updated: set[int] = set()
        for number,ch in preview.channels.items():
            if type(number) is not int or not 1<=number<=8 or ch.number!=number:
                raise ValueError("Invalid ADC number")
            state=self.channels.get(number)
            if state is None:
                state=ChannelBuffer(number,self.capacity)
                self.channels[number]=state
            if state.ingest(ch):
                updated.add(number)
        return updated
