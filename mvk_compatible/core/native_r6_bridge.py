"""Stage111Z.25: local-only bridge to the already accepted Native R6.1 recorder.

No sockets, instrument commands or automatic gain correction live here.
The original RAW remains in the recorder's run directory. The Qt viewer only
opens a checksum-verified ZIP made from a completed Native R6.1 export.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

NATIVE_EXE = "MVK_Native_R6_1_Stage108_Windows_x64.exe"
NATIVE_SHA_FILE = "NATIVE_SHA256SUMS.txt"
STOP_REQUEST = ".mvk_stop_requested"
EXPORT_DIR = "BIN_TSXML_VALUES_TABLE_RECONSTRUCTED"
EXPORT_ZIP = "MVK_NATIVE_R6_1_QT_VERIFIED.zip"
_SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
_ALLOWED_END = frozenset(("DURATION_REACHED", "SIZE_LIMIT_REACHED", "STOPPED_BY_USER"))
_MAX_ZIP_BYTES = 1024 * 1024 * 1024
_MAX_AUX_BYTES = 16_000_000


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def native_executable(bundle_root: str | Path | None = None) -> Path:
    """Fail closed if the PyInstaller bundle is absent/modified.

    The checksum detects corruption of the packaged helper, not its authorship.
    Source development has NO automatic fallback to a random installed binary.
    """
    root = bundle_root if bundle_root is not None else getattr(sys, "_MEIPASS", None)
    if root is None:
        raise ValueError("Native R6.1 не упакован: используйте Windows-сборку с встроенным приёмником")
    folder = Path(root) / "mvk_native"
    exe = folder / NATIVE_EXE
    receipt = folder / NATIVE_SHA_FILE
    for file in (exe, receipt):
        if file.is_symlink() or not file.is_file():
            raise ValueError("В комплекте Windows отсутствует проверенный Native R6.1")
    expected = receipt.read_text(encoding="ascii").strip()
    if not _SHA_RE.fullmatch(expected):
        raise ValueError("Манифест Native R6.1 повреждён")
    if sha256_file(exe) != expected:
        raise ValueError("Контрольная сумма встроенного Native R6.1 не совпала")
    return exe


def validate_ipv4(value: str, *, field: str) -> str:
    if value != value.strip():
        raise ValueError(f"{field}: удалите пробелы вокруг IPv4")
    try:
        parsed = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"{field}: ожидается числовой IPv4") from exc
    if (parsed.is_multicast or parsed.is_unspecified or parsed.is_loopback or
            parsed.is_link_local or int(parsed) == 0xffffffff):
        raise ValueError(f"{field}: запрещён служебный адрес IPv4")
    # Reject ambiguous leading zeros; the Go side must use exactly this value.
    if str(parsed) != value:
        raise ValueError(f"{field}: используйте канонический числовой IPv4")
    return value


@dataclass(frozen=True)
class CaptureSpec:
    device_ipv4: str
    local_ipv4: str
    seconds: int
    max_mb: int
    output_parent: Path

    def validate(self) -> None:
        validate_ipv4(self.device_ipv4, field="IP МВК")
        validate_ipv4(self.local_ipv4, field="IP Ethernet")
        if not isinstance(self.seconds, int) or not 1 <= self.seconds <= 300:
            raise ValueError("Время записи: 1..300 секунд")
        if not isinstance(self.max_mb, int) or not 1 <= self.max_mb <= 2048:
            raise ValueError("Лимит RAW: 1..2048 МиБ")
        parent = Path(self.output_parent)
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError("Каталог записи должен существовать и не быть ссылкой")

    def create_root(self) -> Path:
        self.validate()
        return Path(tempfile.mkdtemp(prefix="mvk_r6_session_", dir=self.output_parent))

    def native_args(self, root: Path) -> list[str]:
        self.validate()
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Каталог отдельной сессии отсутствует")
        if not root.resolve().is_relative_to(self.output_parent.resolve()):
            raise ValueError("Выходной каталог вне выбранного места хранения")
        stop_file = root / STOP_REQUEST
        if stop_file.exists() or stop_file.is_symlink():
            raise ValueError("Устаревший запрос остановки: запись не будет начата")
        return ["-ip", self.device_ipv4, "-local-ip", self.local_ipv4,
                "-seconds", str(self.seconds), "-max-mb", str(self.max_mb),
                "-out", str(root), "-approve=true", "-export=true",
                "-live-status=true", "-stop-file", str(stop_file.resolve())]


def request_graceful_stop(root: Path) -> None:
    """Qt writes a local sentinel. Go uses context cancel and finalizes RAW."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Нет каталога активной сессии")
    marker = root / STOP_REQUEST
    with marker.open("x", encoding="ascii") as stream:
        stream.write("STOP\n")


def _json(path: Path, maximum: int) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f"Отсутствует или повреждён файл {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Ожидается JSON-объект {path.name}")
    return value


def _source_run(root: Path) -> tuple[Path, dict]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Каталог записи недоступен")
    runs = [p for p in root.iterdir()
            if p.is_dir() and not p.is_symlink() and
            (p / "STAGE108_EXPORT_STATUS.json").is_file()]
    if len(runs) != 1:
        raise ValueError("Нужно ровно одно завершённое измерение Native R6.1")
    run = runs[0]
    status = _json(run / "STAGE108_EXPORT_STATUS.json", 128_000)
    if (status.get("state") != "EXPORTED" or
            status.get("capture_end_reason") not in _ALLOWED_END or
            status.get("output_directory") != EXPORT_DIR or
            status.get("during_capture_bin_spool_verified") is not True or
            status.get("adc_bin_files") != 8):
        raise ValueError("Native R6.1 не подтвердил завершённый проверенный экспорт; RAW сохранён")
    raw_sha = status.get("source_raw_sha256")
    if not isinstance(raw_sha, str) or not _SHA_RE.fullmatch(raw_sha):
        raise ValueError("Не подтверждён SHA256 исходного RAW")
    return run, status


def pack_completed_export(root: str | Path) -> Path:
    """Verify 19 Native export files and independent AUX before building ZIP.

    Intended for a worker thread, *after* the Go process successfully exits.
    Never modifies raw, BIN, original XML, or any ADC samples. No overwrite.
    """
    run, status = _source_run(Path(root))
    export = run / EXPORT_DIR
    if not export.is_dir() or export.is_symlink():
        raise ValueError("Каталог реконструированных данных не подтверждён")
    raw = run / "incoming.raw"
    if raw.is_symlink() or not raw.is_file() or sha256_file(raw) != status["source_raw_sha256"]:
        raise ValueError("RAW после записи изменён: архив не создаётся")
    audit = _json(export / "EXPORT_AUDIT.json", 256_000)
    if audit.get("source_raw_sha256") != status["source_raw_sha256"]:
        raise ValueError("Аудит и исходный RAW относятся к разным сеансам")
    manifest = audit.get("output_file_sha256")
    if not isinstance(manifest, dict) or len(manifest) != 19:
        raise ValueError("Неполный оригинальный манифест 8 BIN/TSXML + VALUES/TABLE/TIMELINE")
    names = sorted(manifest)
    bins = [n for n in names if re.fullmatch(
        r"MVK\d+-ADC[1-8]-\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2}\.bin", n)]
    if len(bins) != 8 or len({re.search(r"ADC([1-8])", n).group(1) for n in bins}) != 8:
        raise ValueError("В экспортном манифесте отсутствует один из 8 ADC")
    if not all(n + ".tsxml" in manifest for n in bins):
        raise ValueError("Отсутствуют TSXML для всех восьми ADC")
    if not {"VALUES_ALL_ADC_RECONSTRUCTED.csv", "TABLE_LAST_AUX_RECONSTRUCTED.csv",
            "TIMELINE.json"} <= manifest.keys():
        raise ValueError("Отсутствуют таблицы/временная шкала")
    total = 0
    for name in names:
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("Небезопасный путь в манифесте Native R6.1")
        path = export / name
        checksum = manifest[name]
        if not isinstance(checksum, str) or not _SHA_RE.fullmatch(checksum):
            raise ValueError(f"Некорректная контрольная сумма {name}")
        if path.is_symlink() or not path.is_file() or sha256_file(path) != checksum:
            raise ValueError(f"Не совпадает контрольная сумма {name}")
        total += path.stat().st_size
    if total > _MAX_ZIP_BYTES:
        raise ValueError("Размер измерения превышает ограничение Qt offline viewer")
    aux = run / "aux4700.jsonl"
    if aux.is_symlink() or not aux.is_file() or aux.stat().st_size > _MAX_AUX_BYTES:
        raise ValueError("Отсутствует полный исходный AUX4700 для ПИК/ПИК-ПИК; RAW сохранён")
    aux_sha = sha256_file(aux)
    provenance = json.dumps({"source_raw_sha256": status["source_raw_sha256"],
                             "aux4700_sha256": aux_sha},
                            separators=(",", ":"), ensure_ascii=True).encode("ascii")
    target = run / EXPORT_ZIP
    partial = run / (EXPORT_ZIP + ".partial.zip")
    if target.exists() or partial.exists():
        raise ValueError("Готовый ZIP уже существует: запрещена перезапись измерения")
    try:
        with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_STORED,
                             allowZip64=True) as archive:
            for name in names:
                archive.write(export / name, arcname=name)
            archive.write(export / "EXPORT_AUDIT.json", arcname="EXPORT_AUDIT.json")
            archive.write(aux, arcname="aux4700.jsonl")
            archive.writestr("AUX_PROVENANCE.json", provenance)
        # Fail closed if the final viewer's own validation disagrees.
        from .offline_export import OfflineSession
        session = OfflineSession.open(partial)
        session.calculations()
        session.samples(1)
        os.rename(partial, target)  # target does not exist; no overwrites
        return target
    except Exception:
        partial.unlink(missing_ok=True)
        raise
