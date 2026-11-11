"""Stage111Z31BF: exact original IDP scalar CONFIG tables, no private bytes.

Read from operator-owned mvkview.idp (SHA256
77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438)
using verified image VA mapping offset=VA-0x400ED8 (code 00802EB7).
Numbers below are derived constants ONLY, not copied original IDP/DFM/PAS
or original locale strings, and are not a live device configuration.

_Unit115:007CE5B1 source width table 0x8D2B18 (in BYTES; LastAddr += width/2).
_Unit115:007CF415 source FmtChar table 0x8D2AD8.
_Unit125:0080250C dynamic selector IDs; 008039DF octave 43 Float32 entries.
"""
from __future__ import annotations

import hashlib
import struct

SOURCE = "ORIGINAL_IDP_STATIC_CONFIG_TABLES_STAGE111Z31BF"
SOURCE_IMAGE_VA_FILE_OFFSET = 0x400ED8
SOURCE_FMT_CHAR_VA = 0x8D2AD8
SOURCE_WIDTH_TABLE_VA = 0x8D2B18
SOURCE_OCTAVE_FLOAT32_VA = 0x8D2F90

# Original 30-element UTF-16 codepoint array; ! is an original placeholder,
# NOT a supported arbitrary format in another app.
SOURCE_FMT_CHARS = tuple("fiw!!!vacshz!qpmbbbbbbbb!!!!hh")
SOURCE_BYTES_PER_TYPE = (
    4,4,4,4,16,4,4,4,4,32,4,8,4,32,64,4,
    4,4,4,4,4,4,4,4,4,4,4,4,4,4,
)

# These numeric sequences come from original DWORD tables, not from guessing
# consecutive IDs. Source locale titles have NOT been recovered.
SOURCE_SELECTOR_IDS = {
    "num_groups": (0,1),              # _Unit125:803254
    "option": (0,1,2,3),              # _Unit125:8032A0
    "wifi_mode": (0,1,2),             # _Unit125:80330C
    "alarm_band": (0,1,48,47),        # _Unit125:8044D4
    "alarm_state": (0,1,2,3,4,5,17,18,19,20,21,255),  # 802610
    "alarm_alert": (1,2,4,8),         # _Unit125:80267C, composite
    "tacho_function": (0,1),         # _Unit125:8048DC
    "result_overload": (0,1),        # _Unit125:804BD4
    "result_buffers": (0,1,3,7),     # _Unit125:804C40
    "result_sensor_state": (0,1,2,3), # _Unit125:804C94
}
SOURCE_SELECTOR_PREFIXES = {
    "num_groups":"ConfigNumGroups",
    "option":"Option",
    "wifi_mode":"WifiMode",
    "alarm_band":"AlarmBand",
    "alarm_state":"AlarmState",
    "alarm_alert":"AlarmAlert",
    "tacho_function":"TachoFunction",
    "result_overload":"Overload",
    "result_buffers":"Buffers",
    "result_sensor_state":"SensorState",
}
# Source _Unit125:008039DF loops 0x2B times (43), enters 0 as Off,
# then IDs 1..43 with precise source nominal third-octave Float32.
SOURCE_OCTAVE_HZ_FLOAT32_BITS = (
    0x3F2147AE,0x3F4CCCCD,0x3F800000,0x3FA00000,0x3FCCCCCD,
    0x40000000,0x40200000,0x4049999A,0x40800000,0x40A00000,
    0x40C9999A,0x41000000,0x41200000,0x41480000,0x41800000,
    0x41A00000,0x41C80000,0x41FC0000,0x42200000,0x42480000,
    0x427C0000,0x42A00000,0x42C80000,0x42FA0000,0x43200000,
    0x43480000,0x437A0000,0x439D8000,0x43C80000,0x43FA0000,
    0x441D8000,0x44480000,0x447A0000,0x449C4000,0x44C80000,
    0x44FA0000,0x451C4000,0x4544E000,0x457A0000,0x459C4000,
    0x45C4E000,0x45FA0000,0x461C4000,
)
SOURCE_OCTAVE_FLOAT32_TABLE_SHA256 = (
    "fb84a7a4b3e8d6a679357082fe114e9f606a1f3d9d90b9feed6529760bc905f6"
)
SOURCE_FMT_TABLE_SHA256 = (
    "3cbba9e7589693768cde9c83b014fa4a93d1917638ff12c57efd9ac6558d4b0a"
)
SOURCE_WIDTH_TABLE_SHA256 = (
    "efc1269bdb2107bca2e5dce66b4a85107dbeb6c54ba07050b69cc50647c6df71"
)


def source_type_description(type_id: int) -> dict:
    if type(type_id) is not int or not 0 <= type_id < 30:
        raise ValueError("Original TMvkCellList type index is 0..29")
    width=SOURCE_BYTES_PER_TYPE[type_id]
    return {
        "type_id":type_id,
        "format_char":SOURCE_FMT_CHARS[type_id],
        "source_storage_bytes":width,
        "source_register_words":width//2,
        "character_has_original_placeholder":SOURCE_FMT_CHARS[type_id]=="!",
    }


def source_selector_key(kind: str, value: int) -> str | None:
    if kind not in SOURCE_SELECTOR_IDS or type(value) is not int:
        return None
    if value not in SOURCE_SELECTOR_IDS[kind]:
        return None
    return SOURCE_SELECTOR_PREFIXES[kind]+"Cell"+str(value)


def source_octave_frequencies_float32() -> tuple[float,...]:
    return tuple(struct.unpack("<f",struct.pack("<I",bits))[0]
                 for bits in SOURCE_OCTAVE_HZ_FLOAT32_BITS)


def verify_embedded_table_digests() -> None:
    fmt=struct.pack("<30H",*(ord(v) for v in SOURCE_FMT_CHARS))
    widths=struct.pack("<30H",*SOURCE_BYTES_PER_TYPE)
    bands=struct.pack("<43I",*SOURCE_OCTAVE_HZ_FLOAT32_BITS)
    expected=(
        (fmt,SOURCE_FMT_TABLE_SHA256),
        (widths,SOURCE_WIDTH_TABLE_SHA256),
        (bands,SOURCE_OCTAVE_FLOAT32_TABLE_SHA256),
    )
    for blob,digest in expected:
        if hashlib.sha256(blob).hexdigest()!=digest:
            raise AssertionError("Source IDP-derived table digest mismatch")


assert len(SOURCE_FMT_CHARS)==len(SOURCE_BYTES_PER_TYPE)==30
assert len(SOURCE_OCTAVE_HZ_FLOAT32_BITS)==43
verify_embedded_table_digests()
