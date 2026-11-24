"""Stage111Z.16: direct LOCAL BIN + TSXML read-only session (no R6.1 ZIP).

Accepts little-endian IEEE754 Single ADC, or explicitly identified original
Count/Byte TACH1–2. A typed Mode1 Byte source is read as unsigned bytes;
only its graph sample provider uses GetDataArray's Single(Byte/255).
The saved bytes are kept intact. No arbitrary native BIN format, physical
calibration, RPM or DSP values are inferred.

The optional same-named MVK...-ADC/TACH group can be opened together,
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
    MAX_BIN_SAMPLES, OfflineSession,
    waveform_for_zip, spectrum_for_zip,
)
from .storage_f_range_idr_candidate import DOMAIN_CALIBRATED_BIN
from .original_tsxml_contract import (
    OriginalTsxmlContract,inspect_original_tsxml,ORIGINAL_TSXML_SOURCE,
)
from .mvk_original_scale_tables_idr_candidate import source_spectrum_unit_contract

MAX_TSXML_BYTES = 64_000
_MAX_BIN_BYTES = MAX_BIN_SAMPLES * 4
_CHANNEL_NAME = re.compile(
    r"(MVK\d+)-(ADC[1-8]|TACH[12])-(\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2})\.bin\Z"
)
PROVENANCE = "LOCAL_DIRECT_BIN_TSXML_SINGLE_UNVERIFIED_CALIBRATION"
TACH_PROVENANCE = "LOCAL_DIRECT_BIN_TSXML_MODE1_TACH_BYTE"
TACH_INPUT_DOMAIN = "MODE1_TACH_BYTE_DIV255_FLOAT32"
TACH_MODE1_SAMPLE_RATES = frozenset((512, 2048, 8192, 32768, 65536))


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

    @property
    def tach_byte(self) -> bool:
        return self.source_metadata.data_type == "Byte"

    @property
    def sample_count(self) -> int:
        return self.data_length_bytes // self.source_metadata.sample_width_bytes


def _checked_file(path: Path, *, limit: int, what: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{what}: нужен обычный локальный файл, не ссылка")
    before = path.stat()
    size = before.st_size
    if not 1 <= size <= limit:
        raise ValueError(f"{what}: недопустимый размер файла")
    with path.open("rb") as handle:
        data = handle.read(size + 1)
    after = path.stat()
    if (len(data) != size or path.is_symlink()
            or (before.st_dev, before.st_ino, size, before.st_mtime_ns)
               != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
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
    tach = contract.data_type == "Byte"
    declared=contract.channel_number
    if tach and (
            declared not in (9, 10) or contract.channel_units_text != "Count"
            or contract.file_name_declared is None
            or contract.data_offset_bytes != 0
            or contract.sample_rate_hz not in TACH_MODE1_SAMPLE_RATES
            or contract.internal_gain_single not in (None, 1.0)):
        raise ValueError(
            "RealDataType=Byte: требуется связанный TSXML для TACH1/2 "
            "(ChannelNumber 9/10, Units=Count, DataOffset=0, "
            "частота Mode1, gain 1 или отсутствует)")
    if contract.data_length_bytes // contract.sample_width_bytes > MAX_BIN_SAMPLES:
        raise ValueError("Слишком много отсчётов в выбранном BIN")
    if declared is not None:
        if not tach and not 1<=declared<=8:
            raise ValueError(
                "ChannelNumber указывает не на один из восьми АЦП ускорения")
        if adc is not None and adc!=declared:
            raise ValueError(
                "ChannelNumber в TSXML не совпадает с каналом в имени BIN")
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
    if not tach:
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
    """Explicitly typed and non-calibrated local BIN/TSXML source.

    Inherited original-window candidate routines call self.samples(), which
    reads verified local bytes. Native ZIP data and DSP CSV paths are untouched.
    """
    channel_files: tuple[DirectBinChannel, ...]

    @property
    def primary_channel(self) -> int:
        return next(entry.adc for entry in self.channel_files if entry.bin_path == self.path)

    def is_tach(self, channel: int) -> bool:
        return any(entry.adc == channel and entry.tach_byte for entry in self.channel_files)

    def mode1_adc_source(self, channel: int) -> DirectBinChannel | None:
        """Recognize the saved Mode1 writer structure, not physical calibration.

        Bare/mismatched/partial TSXML and research BINs keep their previous
        neutral interpretation. Every subsequent samples() read validates hashes.
        """
        entry = next((item for item in self.channel_files if item.adc == channel), None)
        if entry is None or entry.tach_byte:
            return None
        meta = entry.source_metadata
        name = _CHANNEL_NAME.fullmatch(entry.bin_path.name)
        if (name is None or name.group(2) != f"ADC{channel}"
                or not meta.source_meta_complete or not meta.original_writer_offset_zero
                or meta.file_name_declared is None or meta.channel_number != channel
                or meta.sample_rate_hz not in TACH_MODE1_SAMPLE_RATES):
            return None
        return entry if meta.original_f_range_single_candidate is not None else None

    def mode1_export_source(self, channel: int) -> DirectBinChannel | None:
        """A complete saved ADC or an explicitly typed original TACH Byte."""
        adc = self.mode1_adc_source(channel)
        if adc is not None:
            return adc
        entry = next((item for item in self.channel_files if item.adc == channel), None)
        if entry is None or not entry.tach_byte:
            return None
        meta = entry.source_metadata
        name = _CHANNEL_NAME.fullmatch(entry.bin_path.name)
        if (name is None or name.group(2) != f"TACH{channel-8}"
                or not meta.source_meta_complete or meta.internal_gain_single!=1.0
                or not meta.original_writer_offset_zero or meta.channel_number!=channel
                or meta.channel_units_text!="Count" or meta.file_name_declared is None):
            return None
        return entry

    def mode1_adc_range(self, channel: int) -> float | None:
        entry = self.mode1_adc_source(channel)
        return entry.source_metadata.original_f_range_single_candidate if entry else None

    @classmethod
    def open(cls, file: str | Path) -> "DirectBinSession":
        selected = Path(file).absolute()
        if selected.is_symlink() or not selected.is_file():
            raise ValueError("Нужен обычный локальный BIN/TSXML без ссылок")
        primary = _bin_from_selection(selected)
        m = _CHANNEL_NAME.fullmatch(primary.name)
        discovered: list[tuple[int | None, Path]] = []
        if m:
            serial, _, timestamp = m.groups()
            for ch in range(1, 11):
                label = f"ADC{ch}" if ch <= 8 else f"TACH{ch-8}"
                sibling = primary.with_name(
                    f"{serial}-{label}-{timestamp}.bin"
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
        typed = np.frombuffer(raw, dtype="u1" if entry.tach_byte else "<f4",
                              count=entry.sample_count, offset=entry.data_offset_bytes)
        if entry.tach_byte:
            # Type2 007D2317..007D232D: Byte/255 rounded on store to Single,
            # independent of FileMode's ApplyRange and the (fixed) Byte gain.
            buffer = (typed.astype(np.float64) / 255.0).astype("<f4")
            buffer.setflags(write=False)
        else:
            buffer = typed
        if not bool(np.isfinite(buffer).all()):
            raise ValueError("BIN содержит неконечные Float32")
        return buffer, float(entry.sample_rate_hz), {
            "source": TACH_PROVENANCE if entry.tach_byte else PROVENANCE,
            "physical_units_verified": False,
            "dsp_metrics_available": False,
            "original_byte_order": ("unsigned_Byte_from_TSXML" if entry.tach_byte
                                    else "little_endian_Single_from_TSXML"),
            "source_tach_byte_window": entry.tach_byte,
            "source_sample_width_bytes": entry.source_metadata.sample_width_bytes,
            "source_tach_byte_normalization_divisor": 255 if entry.tach_byte else None,
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
        if mode not in ("ac", "acdc"):
            raise ValueError("Режим должен быть ac или acdc")
        tach = self.is_tach(channel)
        result = waveform_for_zip(
            self.path, channel, start_s, seconds, "acdc" if tach else mode, points, display_order,
            sample_provider=self.samples
        )
        if tach:
            return dict(result, source=TACH_PROVENANCE, unit="",
                        input_domain=TACH_INPUT_DOMAIN,
                        rms_normalized=result["rms_m_s2"],
                        source_tach_byte_normalization_divisor=255,
                        source_sample_width_bytes=1, physical_units_verified=False,
                        original_bin_decoder_parity_verified=False,
                        processing_note="TACH Byte/255; AC+DC, без FIR. Не обороты в минуту.")
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
        tach = self.is_tach(channel)
        if tach and (f_range not in (None, 1.0) or input_domain != DOMAIN_CALIBRATED_BIN):
            raise ValueError("TACH Byte использует фиксированный FRange=1 без повторной калибровки")
        result = spectrum_for_zip(
            self.path, channel, n_fft, mode, start_s, max_hz, max_points,
            backend, f_range=1.0 if tach else f_range, input_domain=input_domain,
            sample_provider=self.samples,
        )
        if tach:
            return dict(result, source="APP_DERIVED_MODE1_TACH_BYTE_FFT_CANDIDATE",
                        input_domain=TACH_INPUT_DOMAIN,
                        source_tach_byte_normalization_divisor=255,
                        source_sample_width_bytes=1, physical_units_verified=False,
                        original_bin_decoder_parity_verified=False,
                        warning="TACH Byte/255 → удаление среднего → Hann/FFT. "
                                "Не обороты в минуту, паритет Win32 не подтверждён.",
                        **source_spectrum_unit_contract(mode, "", source_bound=True))
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

    def exact_sample(self, channel, time_s, start_s=0., seconds=1.,
                     mode="acdc", display_order="chronological") -> dict:
        if mode not in ("ac", "acdc"):
            raise ValueError("Режим должен быть ac или acdc")
        tach = self.is_tach(channel)
        result = super().exact_sample(channel, time_s, start_s, seconds,
                                      "acdc" if tach else mode, display_order)
        return dict(
            result, source=TACH_PROVENANCE if tach else PROVENANCE,
            physical_units_verified=False,
            original_bin_decoder_parity_verified=False,
            **({"unit":"", "normalized_byte_value":result["value_m_s2"]}
               if tach else {}),
        )

    def envelope(self, channel, *args, **kwargs) -> dict:
        if self.is_tach(channel):
            raise ValueError("TACH Byte: огибающая (FIR) недоступна")
        return super().envelope(channel, *args, **kwargs)

    def spectrum_envelope(self, channel, *args, **kwargs) -> dict:
        if self.is_tach(channel):
            raise ValueError("TACH Byte: спектральная огибающая (FIR) недоступна")
        return super().spectrum_envelope(channel, *args, **kwargs)

    def narrowband(self, channel, *args, **kwargs) -> dict:
        if self.is_tach(channel):
            raise ValueError("TACH Byte: узкополосная оценка прибора не подтверждена")
        return super().narrowband(channel, *args, **kwargs)

    def verify(self) -> dict:
        has_tach = any(e.tach_byte for e in self.channel_files)
        return {
            "status": ("local_bin_tsxml_typed_structurally_valid" if has_tach
                       else "local_bin_tsxml_float32_structurally_valid"),
            "serial": self.serial,
            "updates": self.updates,
            "channels": [
                {"adc": e.adc, "samples": e.sample_count,
                 "real_data_type": e.source_metadata.data_type,
                 "channel_role": "TACH" if e.tach_byte else "ADC",
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
            "precision": ("TSXML_DECLARED_SINGLE_OR_UNSIGNED_BYTE" if has_tach
                          else "TSXML_DECLARED_SINGLE_FLOAT32_ONLY"),
            "no_device_connection": True,
            "fft_original_parity_verified": False,
            "original_native_bin_format_fully_decoded": False,
        }
