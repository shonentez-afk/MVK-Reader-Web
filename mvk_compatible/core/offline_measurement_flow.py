"""Stage111Z31BC: one source-backed offline measurement flow for 4 pages.

The SAME verified OfflineSession or DirectBinSession is the source for
PageFile, PageAdc, PageSpectrum and PageStatus. Session/channel/tick are
explicit; no duplicated calculations, guessed ADC, AUX, tach, physical
calibration or original-runtime-equivalence flags.

The coordinator is a UI-independent, immutable selection, not a new
DSP/FFT implementation. Existing proven Native R6.1/IDR candidate math is
called unchanged. All user-owned BIN/ZIP/TSXML stay on the operator disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import math
import numbers

import numpy as np

from .offline_export import OfflineSession
from .direct_bin_session import DirectBinSession
from .original_pagestatus_source import source_pagestatus_table
from .storage_f_range_idr_candidate import DOMAIN_CALIBRATED_BIN

SOURCE = "MVKVIEW_OFFLINE_MEASUREMENT_FLOW_STAGE111Z31BC"
SOURCE_ZIP = "VERIFIED_NATIVE_R6_ZIP_VALUES_WITH_OPTIONAL_AUX"
SOURCE_BIN = "LOCAL_SINGLE_BIN_TSXML_WITHOUT_DSP"
MAX_SAMPLE_COUNT = 10_000_000


def _integer(name, value, low, high):
    if (isinstance(value, bool) or not isinstance(value, numbers.Integral)
            or not low <= int(value) <= high):
        raise ValueError(f"{name}: expected integer {low}..{high}")
    return int(value)


@dataclass(frozen=True)
class OfflineMeasurementFlow:
    """An explicit selected channel/tick over ONE locally verified session.

    A source session is never serialized by this object. Changing a
    channel/tick returns a NEW flow; old measurements cannot be imported
    into a new session by accidental mutable context reuse.
    """
    session: OfflineSession = field(repr=False, compare=False)
    channel: int = 1
    tick_index: int = 0

    def __post_init__(self):
        if type(self.session) not in (OfflineSession, DirectBinSession):
            raise ValueError("Only checked MVK offline session types are supported")
        if (type(self.session.serial) is not str
                or not self.session.serial
                or type(self.session.updates) is not int
                or not 1 <= self.session.updates <= 1_000_000):
            raise ValueError("Malformed verified session identity")
        _integer("channel", self.channel, 1, 8)
        if self.channel not in self.available_channels:
            raise ValueError("Selected channel is absent in this measurement")
        _integer("tick_index", self.tick_index, 0, self.session.updates - 1)
        if self.direct_bin and self.tick_index != 0:
            raise ValueError("BIN/TSXML provides no separately verified DSP ticks")

    @property
    def direct_bin(self) -> bool:
        return type(self.session) is DirectBinSession

    @property
    def available_channels(self) -> tuple[int, ...]:
        if self.direct_bin:
            return self.session.available_channels
        return tuple(range(1, 9))

    @classmethod
    def bind(cls, session: OfflineSession, *,
             channel: int | None = None, tick_index: int | None = None):
        if type(session) not in (OfflineSession, DirectBinSession):
            raise ValueError("Expected verified native ZIP or original BIN/TSXML")
        channels = session.available_channels if type(session) is DirectBinSession else tuple(range(1, 9))
        if not channels:
            raise ValueError("A measurement with zero ADC channels cannot be displayed")
        return cls(
            session=session,
            channel=channels[0] if channel is None else channel,
            tick_index=(session.updates - 1 if tick_index is None else tick_index),
        )

    def select(self, *, channel: int | None = None,
               tick_index: int | None = None):
        return replace(
            self,
            channel=self.channel if channel is None else channel,
            tick_index=self.tick_index if tick_index is None else tick_index,
        )

    def require_session(self, session: OfflineSession):
        if session is not self.session:
            raise ValueError("Unrelated sessions must never share a screen result")

    def samples(self):
        """Delegate verified bytes; no gain, resampling, FFT or data copy."""
        src, fs, audit, label = self.session.samples(self.channel)
        if (not isinstance(src, np.ndarray) or src.ndim != 1
                or src.dtype.kind != "f"
                or src.itemsize != 4
                or not 1 <= len(src) <= MAX_SAMPLE_COUNT
                or not bool(np.isfinite(src).all())
                or not isinstance(fs, numbers.Real)
                or not math.isfinite(float(fs)) or float(fs) <= 0):
            raise ValueError("Source samples do not match checked Single input")
        if type(label) is not str or not label:
            raise ValueError("Missing original channel data label")
        return src, fs, audit, label

    def source_record(self) -> dict:
        """Cross-screen provenance, never an exported raw signal or file path.

        The underlying session.samples() revalidates source SHA/TSXML
        before this record can be accepted. No inferred calibration or DSP.
        """
        src, fs, audit, label = self.samples()
        if self.direct_bin:
            source = next((e for e in self.session.channel_files
                           if e.adc == self.channel), None)
            if source is None:
                raise ValueError("Channel does not exist in selected BIN group")
            fingerprint = source.bin_sha256
            if (not isinstance(audit, dict)
                    or audit.get("physical_units_verified") is not False):
                raise ValueError("BIN physical calibration cannot be asserted")
        else:
            if not isinstance(audit, dict):
                raise ValueError("Native ZIP audit record missing")
            manifest = audit.get("output_file_sha256")
            if not isinstance(manifest, dict):
                raise ValueError("Native ZIP verified file digest missing")
            fingerprint = manifest.get(label)
            if not isinstance(fingerprint, str):
                raise ValueError("Native ZIP channel digest missing")
        if (len(fingerprint) != 64
                or any(c not in "0123456789abcdefABCDEF" for c in fingerprint)):
            raise ValueError("Unverified source BIN digest")
        return {
            "source": SOURCE,
            "measurement_kind": SOURCE_BIN if self.direct_bin else SOURCE_ZIP,
            "serial": self.session.serial,
            "available_channels": list(self.available_channels),
            "selected_channel": self.channel,
            "selected_dsp_tick_index": None if self.direct_bin else self.tick_index,
            "dsp_values_available": not self.direct_bin,
            "raw_aux_values_available_only_if_authenticated": True,
            "physical_calibration_original_runtime_verified": False,
            "physical_units_unverified_for_direct_bin": self.direct_bin,
            "original_runtime_parity_verified": False,
            "data_file_label": label,  # filename only, NEVER absolute path
            "source_bin_sha256": fingerprint.lower(),
            "sample_count": int(len(src)),
            "sample_rate_hz": float(fs),
            "fft_or_signal_recomputed_by_flow": False,
            "source_identity_not_crossed": True,
        }

    def status_snapshot(self) -> dict | None:
        """Only actual source verified native ZIP VALUES/AUX tick.

        A stand-alone BIN/TSXML has NO original AUX/VALUES/TACH and must
        show the source "unavailable" layout, not invented readings.
        """
        if self.direct_bin:
            return None
        data = self.session.calculations(self.tick_index)
        if (not isinstance(data, dict)
                or data.get("serial") != self.session.serial
                or data.get("tick") != self.tick_index
                or data.get("source") != "MVK_DSP"
                or not isinstance(data.get("channels"), list)
                or len(data["channels"]) != 8
                or any(x.get("channel") != i for i, x in enumerate(
                    data["channels"], 1))):
            raise ValueError("DSP values do not belong to this session and tick")
        return data

    def status_table(self, mode: int):
        return source_pagestatus_table(mode, self.status_snapshot())

    def waveform(self, start_s: float, seconds: float,
                 mode: str = "acdc", *, points: int = 4000,
                 display_order: str = "chronological") -> dict:
        return self.session.waveform(
            self.channel, start_s, seconds, mode,
            points, display_order)

    def envelope(self, code: int, start_s: float, seconds: float,
                 profile, *, display_order: str = "chronological") -> dict:
        return self.session.envelope(
            self.channel, code, start_s, seconds, profile,
            display_order=display_order)

    def spectrum(self, n_fft: int = 65536, mode: int = 1,
                 start_s: float | None = None, max_hz: float = 10000.,
                 max_points: int = 5000, backend: str = "idr_float32",
                 *, f_range: float | None = None,
                 input_domain: str = DOMAIN_CALIBRATED_BIN) -> dict:
        return self.session.spectrum(
            self.channel, n_fft, mode, start_s, max_hz, max_points, backend,
            f_range=f_range, input_domain=input_domain)

    def spectrum_envelope(self, code: int, n_fft: int, profile,
                          *, end_s: float | None = None,
                          mode: int = 1, backend: str = "idr_float32",
                          f_range: float | None = None,
                          input_domain: str = DOMAIN_CALIBRATED_BIN) -> dict:
        return self.session.spectrum_envelope(
            self.channel, code, n_fft, profile,
            end_s=end_s, mode=mode, backend=backend, f_range=f_range,
            input_domain=input_domain)
