"""Conservative MVK01 ADC status decoder, independent of web application.

Bit semantics from MVK01 manual. Application-specific descriptions of
wiring faults require sensor configuration or independent operator evidence.
"""
from dataclasses import dataclass,asdict

BIT_DEFINITIONS = {
    0: ("input_overload", "Перегрузка входа"),
    4: ("buffer_fs16_not_ready", "Буфер 16 Гц не заполнен"),
    5: ("buffer_fs64_not_ready", "Буфер 64 Гц не заполнен"),
    6: ("buffer_fs512_not_ready", "Буфер 512 Гц не заполнен"),
    10: ("sensor_dc_above_max", "Постоянное напряжение датчика выше допустимого максимума"),
    11: ("sensor_dc_at_or_below_min", "Постоянное напряжение датчика не выше допустимого минимума"),
}
KNOWN_MASK = sum(1 << bit for bit in BIT_DEFINITIONS)

def decode_status(value, cable_open_label=False):
    """Decode uint32 status read from AUX4700 channel record offset +580.

    cable_open_label is an optional, *externally confirmed* sensor-specific
    display mapping, NOT an assertion made by protocol bit 10 itself.
    """
    if not isinstance(value,int) or not 0<=value<=0xffffffff:
        raise ValueError("Status must be uint32")
    active=[{"bit":bit,"code":code,"protocol_description_ru":label}
            for bit,(code,label) in BIT_DEFINITIONS.items() if value & (1 << bit)]
    labels=[item["protocol_description_ru"] for item in active]
    if cable_open_label and value & (1 << 10):
        labels.append("Обрыв кабеля (подтверждённая интерпретация данного канала)")
    return {"raw_uint32":value,"hex":f"0x{value:08X}","active":active,
            "unknown_mask":value & ~KNOWN_MASK, "display_labels_ru":labels,
            "has_known_fault_bits":bool(value & ((1 << 0)|(1 << 10)|(1 << 11)))}
