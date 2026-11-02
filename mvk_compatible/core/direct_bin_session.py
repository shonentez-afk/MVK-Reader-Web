"""Stage111Z.16: direct LOCAL BIN + TSXML read-only session (no R6.1 ZIP).

Supported ONLY when the companion TSXML explicitly describes one little-
endian IEEE754 Single channel, with a verified byte offset/length and an
integer sample rate. Does NOT decode arbitrary native MVK BIN formats or
infer physical calibration. Such files fail closed instead of being
silently interpreted as floats.

The optional same-named MVK...-ADC1..8 group can be opened together,
strictly requiring the same instrument/time stem. Nothing in this module
connects to a device, internet, cloud, or writes a measurement file.
No AUX/VALUES/third-octave DSP results are manufactured.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

import numpy as np

from .offline_export import (
    BIN_NAME_RE, MAX_BIN_SAMPLES, OfflineSession, VERSION,
    waveform_for_zip, spectrum_for_zip,
)
from .storage_f_range_idr_candidate import DOMAIN_CALIBRATED_BIN
from .original_tsxml_contract import (
    OriginalTsxmlContract,inspect_original_tsxml,ORIGINAL_TSXML_SOURCE,
)

MAX_TSXML_BYTES = 64_000
_MAX_BIN_BYTES = MAX_BIN_SAMPLES * 4
_CHANNEL_NAME = re.compile(
    r"^(MVK\d+)-ADC([1-8])-(\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2})\.bin$"
)
PROVENANCE = "LOCAL_DIRECT_BIN_TSXML_SINGLE_UNVERIFIED_CALIBRATION"


@dataclass(frozen=True)
class DirectBinChannel:
    adc: int
    bin_path: Path
    tsxml_path: Path
    sample_rate_hz: int
    data_offset_bytes: int
    data_length_bytes: int
    bin_sha256: str
    tsxml_sha256: str
    source_metadata: OriginalTsxmlContract


def _checked_file(path: Path, *, limit: int, what: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{what}: нужен обычный локальный файл, не ссылка")
    size = path.stat().st_size
    if not 1 <= size <= limit:
        raise ValueError(f"{what}: недопустимый размер файла")
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError(f"{what}: файл изменился во время чтения")
    return data


def _sidecar_for_bin(bin_path: Path) -> Path:
    # Both conventions occur in local measurement collections:
    # "record.bin.tsxml" or "record.tsxml".
    options = (bin_path.with_name(bin_path.name + ".tsxml"),
               bin_path.with_suffix(".tsxml"))
    existing = [p for p in options if p.exists() or p.is_symlink()]
    if len(existing) != 1:
        raise ValueError(
            "Для прямого BIN нужна ровно одна парная TSXML: "
            "имя.bin.tsxml или имя.tsxml"
        )
    return existing[0]


def _bin_from_selection(selected: Path) -> Path:
    suffix = selected.suffix.lower()
    if suffix == ".bin":
        return selected
    if suffix == ".tsxml":
        if selected.name.lower().endswith(".bin.tsxml"):
            return selected.with_name(selected.name[:-6])
        return selected.with_suffix(".bin")
    raise ValueError("Выберите локальный BIN или соответствующий TSXML")


def _inspect_channel(bin_file: Path, adc: int | None) -> DirectBinChannel:
    # Original IDR TSXML writer emits full CP1251 metadata, including
    # DataFileName and ChannelNumber. Check these against the selected BIN
    # so same-size files cannot be silently paired with wrong sidecars.
    sidecar = _sidecar_for_bin(bin_file)
    xml = _checked_file(sidecar, limit=MAX_TSXML_BYTES, what="TSXML")
    contract = inspect_original_tsxml(
        xml, actual_bin_filename=bin_file.name,max_data_bytes=_MAX_BIN_BYTES)
    if contract.data_type=="Byte":
        # Source _Unit125 (00806F68) writes Byte for tachometer/count
        # channels. Never reinterpret those counts as Float32 acceleration
        # and never synthesize a 1-channel FFT on integer counter bytes.
        raise ValueError(
            "Оригинальный BIN имеет RealDataType=Byte (счётный канал). "
            "Метаданные распознаны, но FFT ускорения для Byte недоступен.")
    if contract.data_length_bytes<4:
        raise ValueError("Single BIN требует минимум 4 байта")
    declared=contract.channel_number
    if declared is not None:
        if not 1<=declared<=8:
            raise ValueError(
                "ChannelNumber указывает не на один из восьми АЦП ускорения")
        if adc is not None and adc!=declared:
            raise ValueError(
                "ChannelNumber в TSXML не совпадает с АЦП в имени BIN")
        adc=declared
    elif adc is None:
        # The old Stage111Z.16 minimal/synthetic sidecar has no number.
        # Keep its single-file fallback, but never claim this is proven.
        adc=1
    raw = _checked_file(
        bin_file, limit=_MAX_BIN_BYTES + 4_096, what="BIN"
    )
    length=contract.data_length_bytes
    offset=contract.data_offset_bytes
    if offset + length != len(raw):
        raise ValueError(
            "BIN/TSXML: DataOffset+DataLength должны точно покрывать файл"
        )
    samples = np.frombuffer(raw, dtype="<f4", count=length//4, offset=offset)
    if not bool(np.isfinite(samples).all()):
        raise ValueError("BIN содержит NaN/Inf: прямой импорт отклонён")
    return DirectBinChannel(
        adc=adc, bin_path=bin_file, tsxml_path=sidecar,
        sample_rate_hz=contract.sample_rate_hz,
        data_offset_bytes=offset,data_length_bytes=length,
        bin_sha256=hashlib.sha256(raw).hexdigest(),
        tsxml_sha256=hashlib.sha256(xml).hexdigest(),
        source_metadata=contract,
    )


@dataclass(frozen=True)
class DirectBinSession(OfflineSession):
    """Explicitly uncalibrated single- or multi-channel BIN/TSXML source.

    Inherited original-window candidate routines call self.samples(), which
    reads verified local bytes. Native ZIP data and DSP CSV paths are untouched.
    """
    channel_files: tuple[DirectBinChannel, ...]

    @classmethod
    def open(cls, file: str | Path) -> "DirectBinSession":
        selected = Path(file).absolute()
        if selected.is_symlink() or not selected.is_file():
            raise ValueError("Нужен обычный локальный BIN/TSXML без ссылок")
        primary = _bin_from_selection(selected)
        _checked_file(primary, limit=_MAX_BIN_BYTES + 4_096, what="BIN")
        _sidecar_for_bin(primary)

        m = _CHANNEL_NAME.fullmatch(primary.name)
        discovered: list[tuple[int | None, Path]] = []
        if m and BIN_NAME_RE.fullmatch(primary.name):
            serial, _, timestamp = m.groups()
            for ch in range(1, 9):
                sibling = primary.with_name(
                    f"{serial}-ADC{ch}-{timestamp}.bin"
                )
                if sibling.exists() or sibling.is_symlink():
                    discovered.append((ch, sibling))
        else:
            # Nonstandard names may still include an original ChannelNumber
            # inside the paired TSXML. Preserve it instead of guessing ADC1.
            # No neighboring files are grouped on ambiguous names.
            serial = "LOCAL_BIN_SINGLE_CHANNEL"
            discovered.append((None, primary))
        if not discovered or primary not in [p for _, p in discovered]:
            raise ValueError("Нельзя определить исходную группу BIN")
        sources = tuple(
            _inspect_channel(p, ch) for ch, p in discovered
        )
        if len({src.sample_rate_hz for src in sources}) != 1:
            raise ValueError("Каналы одного измерения имеют разную частоту")
        return cls(
            path=primary, serial=serial, updates=1, started_utc=None,
            channel_files=sources,
        )

    @property
    def available_channels(self) -> tuple[int, ...]:
        return tuple(ch.adc for ch in self.channel_files)

    def samples(self, channel: int) -> tuple:
        if type(channel) is not int:
            raise ValueError("Номер АЦП должен быть целым")
        entry = next(
            (f for f in self.channel_files if f.adc == channel), None
        )
        if entry is None:
            raise ValueError(
                "Этого АЦП нет в выбранной локальной BIN/TSXML группе"
            )
        raw = _checked_file(
            entry.bin_path, limit=_MAX_BIN_BYTES + 4_096, what="BIN"
        )
        xml = _checked_file(
            entry.tsxml_path, limit=MAX_TSXML_BYTES, what="TSXML"
        )
        if (hashlib.sha256(raw).hexdigest() != entry.bin_sha256 or
                hashlib.sha256(xml).hexdigest() != entry.tsxml_sha256):
            raise ValueError("Исходный BIN или TSXML изменён после открытия")
        buffer = np.frombuffer(
            raw, dtype="<f4", count=entry.data_length_bytes // 4,
            offset=entry.data_offset_bytes
        )
        if not bool(np.isfinite(buffer).all()):
            raise ValueError("BIN содержит неконечные Float32")
        return buffer, float(entry.sample_rate_hz), {
            "source": PROVENANCE,
            "physical_units_verified": False,
            "dsp_metrics_available": False,
            "original_byte_order": "little_endian_Single_from_TSXML",
            "original_tsxml_contract_source": ORIGINAL_TSXML_SOURCE,
            "original_tsxml_writer_fields_complete":
                entry.source_metadata.source_meta_complete,
            "declared_channel_number":
                entry.source_metadata.channel_number,
            "declared_units_text":
                entry.source_metadata.channel_units_text,
            "declared_internal_channel_gain_single":
                entry.source_metadata.internal_gain_single,
            "original_loader_gain_branch_from_idr":
                entry.source_metadata.gain_loader_branch,
            "original_loader_f_range_single_candidate":
                entry.source_metadata.original_f_range_single_candidate,
            "metadata_gain_was_applied_to_bin_samples": False,
            "original_loader_runtime_f_range_verified": False,
        }, entry.bin_path.name

    def calculations(self, tick: int = -1) -> dict:
        raise ValueError(
            "Прямая BIN/TSXML пара не содержит проверенных VALUES/AUX DSP. "
            "Приборные расчётные показатели недоступны."
        )

    def waveform(self, channel: int, start_s: float, seconds: float,
                 mode: str = "acdc", points: int = 4000,
                 display_order: str = "chronological") -> dict:
        result = waveform_for_zip(
            self.path, channel, start_s, seconds, mode, points, display_order,
            sample_provider=self.samples
        )
        return dict(
            result, source=PROVENANCE,
            unit="исходные отсчёты · физическая калибровка не проверена",
            physical_units_verified=False,
            original_bin_decoder_parity_verified=False,
            processing_note=result["processing_note"] +
                " · BIN/TSXML Single принят без подтверждения калибровки."
        )

    def spectrum(self, channel: int, n_fft: int = 65536, mode: int = 1,
                 start_s: float | None = None,
                 max_hz: float = 10000., max_points: int = 5000,
                 backend: str = "idr_float32", *,
                 f_range: float | None = None,
                 input_domain: str = DOMAIN_CALIBRATED_BIN) -> dict:
        result = spectrum_for_zip(
            self.path, channel, n_fft, mode, start_s, max_hz, max_points,
            backend, f_range=f_range, input_domain=input_domain,
            sample_provider=self.samples,
        )
        return dict(
            result, source="APP_DERIVED_DIRECT_BIN_FFT_CANDIDATE",
            unit=("относительные дБ (без аттестации калибровки)"
                  if mode == 0 else "условные единицы (калибровка не проверена)"),
            warning=result["warning"] +
                " · BIN/TSXML Single: исходная физическая калибровка "
                "и оригинальный формат BIN не аттестованы.",
            physical_units_verified=False,
            original_bin_decoder_parity_verified=False,
        )

    def exact_sample(self, *args, **kwargs) -> dict:
        result = super().exact_sample(*args, **kwargs)
        return dict(
            result, source=PROVENANCE, physical_units_verified=False,
            original_bin_decoder_parity_verified=False,
        )

    def verify(self) -> dict:
        return {
            "status": "local_bin_tsxml_float32_structurally_valid",
            "serial": self.serial,
            "updates": self.updates,
            "channels": [
                {"adc": e.adc, "samples": e.data_length_bytes // 4,
                 "fs_hz": e.sample_rate_hz, "calibration_verified": False,
                 "original_tsxml_writer_fields_complete":
                     e.source_metadata.source_meta_complete,
                 "declared_channel_number":
                     e.source_metadata.channel_number,
                 "declared_units_text":
                     e.source_metadata.channel_units_text,
                 "internal_channel_gain_single":
                     e.source_metadata.internal_gain_single,
                 "original_loader_gain_branch":
                     e.source_metadata.gain_loader_branch,
                 "original_f_range_single_candidate":
                     e.source_metadata.original_f_range_single_candidate,
                 "bin_samples_gain_multiplied_by_reader": False}
                for e in self.channel_files
            ],
            "dsp_source": "NOT_AVAILABLE_NO_AUX_VALUES",
            "precision": "TSXML_DECLARED_SINGLE_FLOAT32_ONLY",
            "no_device_connection": True,
            "fft_original_parity_verified": False,
            "original_native_bin_format_fully_decoded": False,
        }
