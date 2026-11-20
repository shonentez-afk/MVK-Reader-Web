"""Source-confirmed Russian VALUES/TABLE text and Win32-1251 layout.

Grounded in the user's original 28 Oct 2026 VALUES/TABLE pair, the
source TMvkCellList constructors and _Unit128 bWriteTable/WriteValues,
and the previously extracted original EXTLOCALIZATION ru-ru resource.

Contains only short UI labels / names, never private instrument values.
No device access. All new live exports remain explicitly CANDIDATE until
paired against the same register-image inputs of original MVKView.
"""
from __future__ import annotations

from .original_get_value_text_30 import get_value_text_30
from .original_get_value_text_30 import live_get_units

PROFILE="MVK_ORIGINAL_RU_CP1251_VALUES_TABLE_LAYOUT_V1"
NUM_ADC=8
NUM_TACH=2
SOURCE_GROUP_ORDER=("SPEC","RESULT","BAND","TACH")
SOURCE_OCTAVE_TITLES=("0.63","0.8","1","1.25","1.6","2","2.5","3.15","4","5",
    "6.3","8","10","12.5","16","20","25","31.5","40","50","63","80",
    "100","125","160","200","250","315","400","500","630","800",
    "1000","1250","1600","2000","2500","3150","4000","5000","6300","8000","10000")
assert len(SOURCE_OCTAVE_TITLES)==43
RANGES=("10..3000 Гц","10..2000 Гц","10..1000 Гц","2..1000 Гц",
        "0,8..300 Гц","0,8..150 Гц","Польз. 1","Польз. 2")
QUANTITIES=("Виброускорение, ","Виброскорость, ","Виброперемещение, ")
RESULT_TITLES=(
    "Индикатор перегрузки","Индикатор заполнения буферов",
    "Состояние датчика","Напряжение на датчике",
    "Виброускорение, Х..25 кГц","Пик-фактор виброуск., Х..25 кГц",
)
TACH_TITLES=(
    "Частота вращения","Среднее приращение ЧВ на один оборот",
    "Ошибка датчика оборотов","Последняя метка времени",
    "Текущее значение на входе","Наличие импульсов на входе",
)
ADVANCED_KINDS=("result_overload","result_buffers","result_sensor_state")
assert len(RESULT_TITLES)==6 and len(TACH_TITLES)==6
assert len(RANGES)*len(QUANTITIES)==24


def source_ru_cell_title(group:str,index:int)->str:
    if type(index) is not int or index<0:
        raise ValueError("Original source cell index must be nonnegative")
    if group=="SPEC" and index<43:
        # Convert source IDR numeric 43 frequencies to exactly the printed
        # original strings: decimal dot (not the CSV decimal comma).
        s=SOURCE_OCTAVE_TITLES[index]
        return "Полоса "+s+" Гц"
    if group=="RESULT" and index<6:
        return RESULT_TITLES[index]
    if group=="BAND" and index<24:
        return QUANTITIES[index%3]+RANGES[index//3]
    if group=="TACH" and index<6:
        return TACH_TITLES[index]
    raise ValueError("Source group/index is not a vendor VALUES list cell")


def source_ru_encode_csv(rows)->bytes:
    """Local ANSI profile: exactly CP1251, no BOM, CRLF, pipe, sep=|."""
    checked=[]
    for row in rows:
        if not isinstance(row,(tuple,list)) or any(
                not isinstance(v,str) or "\r" in v or "\n" in v
                or "|" in v for v in row):
            raise ValueError("Source CSV row contains illegal field")
        checked.append("|".join(row))
    return ("sep=|\r\n"+"\r\n".join(checked)+"\r\n").encode("cp1251","strict")


def source_ru_values_header(selected_fields:list[dict])->bytes:
    """Header from actual selected SOURCE 0x3100 cell-order evidence.

    Doesn't infer missing channels or extra historical 73-flag indices.
    Source parse_source_values_3100_event validates address and full order.
    """
    if not isinstance(selected_fields,list) or not selected_fields:
        raise ValueError("Source VALUES header requires nonempty selected field order")
    first=[""]
    second=["Время"]
    last=None
    for field in selected_fields:
        ch,group,idx=(field.get("channel"),field.get("source_list_group"),
                      field.get("source_cell_index"))
        if type(ch) is not int or not 1<=ch<=10:
            raise ValueError("Source VALUES header has invalid channel")
        if group not in SOURCE_GROUP_ORDER:
            raise ValueError("Source VALUES header has invalid list group")
        if type(idx) is not int:
            raise ValueError("Source VALUES header has invalid cell index")
        key=(ch,SOURCE_GROUP_ORDER.index(group),idx)
        if last is not None and key<=last:
            raise ValueError("Source VALUES cell order not strictly original")
        last=key
        label=(f"АЦП {ch}" if ch<=8 else f"Тахометр {ch-8}")
        first.append(label)
        second.append(source_ru_cell_title(group,idx))
    return source_ru_encode_csv((tuple(first),tuple(second)))


def source_ru_advanced_title(index:int,raw_uint32:int)->str:
    if type(index) is not int or not 0<=index<3:
        raise ValueError("Source Advanced belongs only to first three RESULT")
    if type(raw_uint32) is not int or not 0<=raw_uint32<1<<32:
        raise ValueError("Source Advanced requires complete DWORD")
    # Call the exact same type-10 source dispatcher used by the
    # independent GetValueText acceptance code. The RU lookup is taken
    # from the extracted original EXTLOCALIZATION resource (41 IDs),
    # not maintained as a second copy of three alarm dictionaries.
    return get_value_text_30(
        10,raw_uint32.to_bytes(4,"little"),advanced_kind=ADVANCED_KINDS[index],
        source_locale="ru-ru").text


def source_ru_typed_text(group:str,index:int,raw_le_hex:str|None)->str:
    """Source value *candidate* for a complete original DWORD.

    Literal UNKNOWN is reserved for a missing network DWORD, not
    TMvkCellList.Data=nil. The latter has a separate '####' source path.
    """
    source_ru_cell_title(group,index)
    if raw_le_hex is None:return "UNKNOWN"
    if not isinstance(raw_le_hex,str) or len(raw_le_hex)!=8:
        raise ValueError("Original GetValueText requires complete LE DWORD")
    try:
        raw=bytes.fromhex(raw_le_hex)
    except ValueError as exc:
        raise ValueError("Invalid source LE DWORD hex") from exc
    if group=="RESULT" and index<3:
        return source_ru_advanced_title(index,int.from_bytes(raw,"little"))
    typ=2 if group=="TACH" and index>=2 else 0
    source=get_value_text_30(typ,raw)
    return source.text.replace(".",",") if typ==0 else source.text


def source_ru_table_rows(channels:list[int],tach_channels:list[int],
                         adc_values:list[list[str]],tach_values:list[list[str]]):
    """Build two source TABLE sections from already rendered vendor-order rows.

    First matrix: len(channels) x 30 (RESULT6+BAND24).
    Second matrix: len(tach_channels) x 6. No guessed measurements.
    """
    if not isinstance(channels,list) or not isinstance(tach_channels,list):
        raise ValueError("Original table selection must be explicit lists")
    if (any(type(x) is not int or not 1<=x<=8 for x in channels)
        or any(type(x) is not int or not 1<=x<=2 for x in tach_channels)
        or channels!=sorted(set(channels))
        or tach_channels!=sorted(set(tach_channels))):
        raise ValueError("Original TABLE channel flags have invalid order")
    if (len(adc_values)!=len(channels) or
        len(tach_values)!=len(tach_channels)
        or any(len(row)!=30 for row in adc_values)
        or any(len(row)!=6 for row in tach_values)):
        raise ValueError("Source TABLE data does not fit original selected channels")
    rows=[("Наименование параметра",*(f"АЦП {ch}" for ch in channels),"")]
    for i in range(30):
        group,index=("RESULT",i) if i<6 else ("BAND",i-6)
        rows.append((source_ru_cell_title(group,index),
                     *(row[i] for row in adc_values),
                     live_get_units(group,index)))
    rows.append(())
    rows.append(("Наименование параметра",*(f"Тахометр {ch}" for ch in tach_channels),""))
    for i in range(6):
        rows.append((source_ru_cell_title("TACH",i),
                     *(row[i] for row in tach_values),
                     live_get_units("TACH",i)))
    assert len(rows)==39
    return tuple(rows)
