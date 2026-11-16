"""Source-proven FIVE Delphi sample-rate Tags, with no instrument control.

Private MVKView 1.0.47 provenance:
  IDR .data RVA 008D2F7C contains five adjacent UInt32s
    00000200 00000800 00002000 00008000 00010000
  .data RVA 008D3AEC holds little-endian pointer 008D2F7C.
  _Unit128 008457F1..0084587B creates TMenuItem for each, then Insert(0)
  => UI order is REVERSED from the array.
  _Unit128 00846DDF..00846DF7 calls mRate1Click on Items[0] after thread
  creation, using Tag, not the observed Native sample rate.
  _Unit125 0080618E encodes 09 03 00 00 = 0x309 internal startup code,
  not decimal 309 and not physical sample rate in Hz.
  _Unit128 0084DEC4 sets SelectedSampleRate from clicked TMenuItem.Tag;
  invokes TMVKThread.SetRate only if a source thread exists.
  _Unit125 00809400 enqueues new rate only if it differs from 0x309.

These are extracted facts, not a copy of any original binary/source file.
The read-only Native R6.1 receiver must not issue SetRate commands.
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE = "IDR_V3_DATA_008D2F7C_008D3AEC_MRATE1_00846DF7"
RATE_ARRAY_ADDRESS = 0x008D2F7C
RATE_POINTER_ADDRESS = 0x008D3AEC
SOURCE_RATE_CODES_IN_MEMORY = (0x200, 0x800, 0x2000, 0x8000, 0x10000)
SOURCE_RATE_MENU_TAGS = tuple(reversed(SOURCE_RATE_CODES_IN_MEMORY))
SOURCE_DEFAULT_MENU_TAG = SOURCE_RATE_MENU_TAGS[0]
SOURCE_THREAD_INITIAL_CODE = 0x309
ORIGINAL_MENU_COUNT = 5


@dataclass(frozen=True)
class OriginalRateMenuItem:
    """Source TMenuItem indexed in the true Insert(0) UI order."""

    position: int
    tag: int
    caption: str

    def receipt(self) -> dict:
        return {
            "source": SOURCE,
            "position_zero_based": self.position,
            "original_TMenuItem_Tag": self.tag,
            "caption": self.caption,
            "source_original_handler": "Tmvkform.mRate1Click",
            "source_handler_address": "0084DEC4",
            "hardware_rate_change_enabled": False,
            "device_commands_sent": False,
        }


def original_rate_menu_items() -> tuple[OriginalRateMenuItem, ...]:
    return tuple(
        OriginalRateMenuItem(i, rate, f"{rate} Гц")
        for i, rate in enumerate(SOURCE_RATE_MENU_TAGS)
    )


def validate_original_rate_tag(rate: int) -> int:
    if type(rate) is not int or rate not in SOURCE_RATE_MENU_TAGS:
        raise ValueError("Sample rate is not one of five source-verified Tags")
    return rate


def source_initial_rate_provenance() -> dict:
    """After original TMVKThread.Create, mRate1Click selects Items[0]."""
    return {
        "source": SOURCE,
        "source_original_rate_array_address": f"{RATE_ARRAY_ADDRESS:08X}",
        "source_pointer_data_address": f"{RATE_POINTER_ADDRESS:08X}",
        "source_memory_array_uint32": list(SOURCE_RATE_CODES_IN_MEMORY),
        "source_visible_menu_tags": list(SOURCE_RATE_MENU_TAGS),
        "original_initial_source_thread_code_hex":
            f"0x{SOURCE_THREAD_INITIAL_CODE:X}",
        "original_initial_source_thread_code_decimal":
            SOURCE_THREAD_INITIAL_CODE,
        "initial_menu_tag": SOURCE_DEFAULT_MENU_TAG,
        "initial_select_handler": "0084DEC4",
        "initial_select_after_thread_create": True,
        "original_menu_count": ORIGINAL_MENU_COUNT,
        "hardware_command_sender_enabled": False,
        "device_commands_sent": 0,
    }
