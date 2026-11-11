"""Stage111Z31BG: original TLanguage UTF-8 JSON RESOURCE lookup model.

From private _Unit115:007C7CC0 (TResourceStream type 10; UTF-8 JSON array),
007C7AD0 (enumerate objects, get FCurrLang -> TJSONArray, enumerate
values, use JSONValue.GetValueP(id), last assigned value wins),
007C7DC4 and 007C7E28 (query source key as JSON property).

No vendor translation resource is distributed here. A locally supplied
file is UNAUTHENTICATED until explicitly verified; its contents are not
claimed to be original runtime translations.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .original_language_source import SOURCE_KEY_SET, source_localize

SOURCE = "IDR_TLanguage_TResourceStream_UTF8_JSON_ARRAY_STAGE111Z31BG"
MAX_LANGUAGE_JSON = 1024 * 1024
MAX_TRANSLATIONS = 8192
MAX_ITEMS = 2048


@dataclass(frozen=True)
class LocalLanguageInspection:
    language_id: str
    translations: tuple[tuple[str, str], ...]
    file_sha256: str
    imported_local_resource_verified_as_original: bool = False
    original_runtime_parity_verified: bool = False

    def lookup(self, key: str) -> str | None:
        if not isinstance(key, str) or key not in SOURCE_KEY_SET:
            raise KeyError("Unknown source TLanguage callsite key")
        return dict(self.translations).get(key)

    def display(self, key: str) -> str:
        # Local resource is optional: never manufacture an "original" string.
        original = self.lookup(key)
        return original if original is not None else source_localize(key).display

    def report(self) -> dict:
        return {
            "source": SOURCE,
            "local_resource_sha256": self.file_sha256,
            "language": self.language_id,
            "source_keys_present": len(self.translations),
            "source_keys_expected": len(SOURCE_KEY_SET),
            "imported_local_resource_verified_as_original":
                self.imported_local_resource_verified_as_original,
            "original_runtime_parity_verified":
                self.original_runtime_parity_verified,
            "device_io": False,
        }


def inspect_local_language_bytes(raw: bytes, language_id: str) -> LocalLanguageInspection:
    if type(raw) is not bytes or not 2 <= len(raw) <= MAX_LANGUAGE_JSON:
        raise ValueError("Original resource reader needs bounded UTF-8 bytes")
    if (not isinstance(language_id, str) or not language_id
            or len(language_id) > 32 or
            any(ch in language_id for ch in "/\\\0\n\r")):
        raise ValueError("Invalid source language ID")
    decoded = raw.decode("utf-8-sig")
    value = json.loads(decoded)
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise ValueError("TLanguage source root must be a JSON array")
    parsed: dict[str, str] = {}
    entry_count = 0
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("TLanguage root array must contain objects")
        locales = entry.get(language_id)
        if locales is None:
            continue
        if not isinstance(locales, list) or len(locales) > MAX_ITEMS:
            raise ValueError("Selected original language must be JSON array")
        for datum in locales:
            if not isinstance(datum, dict):
                raise ValueError("Original locale arrays must contain objects")
            if len(datum) > MAX_ITEMS:
                raise ValueError("Locale item too large")
            for key, phrase in datum.items():
                entry_count += 1
                if entry_count > MAX_TRANSLATIONS:
                    raise ValueError("Too many original locale entries")
                if (not isinstance(key, str) or len(key) > 128
                        or not isinstance(phrase, str) or len(phrase) > 2048):
                    raise ValueError("Unsupported source locale field")
                if key in SOURCE_KEY_SET:
                    # Source localize loop overwrites on later matching item.
                    parsed[key] = phrase
    return LocalLanguageInspection(
        language_id=language_id,translations=tuple(sorted(parsed.items())),
        file_sha256=hashlib.sha256(raw).hexdigest(),
    )


def inspect_local_language_file(path: str | Path, language_id: str
                                ) -> LocalLanguageInspection:
    file = Path(path)
    if file.is_symlink() or not file.is_file() or (
            file.stat().st_size > MAX_LANGUAGE_JSON):
        raise ValueError("Original locale source must be a bounded ordinary local file")
    data = file.read_bytes()
    if len(data) != file.stat().st_size:
        raise ValueError("Local locale resource changed during read")
    return inspect_local_language_bytes(data, language_id)
