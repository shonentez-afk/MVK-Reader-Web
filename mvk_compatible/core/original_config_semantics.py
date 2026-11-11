"""Stage111Z31BE: source-derived ConfigIP/ConfigCalib/AdvancedCell, read-only.

Private evidence: _Unit115.pas 007D0584..007D0980;
_Unit125.pas 00802D4C/00803580/0080380C.
No device reads/writes, config editor, or synthetic translated strings.
"""
from dataclasses import dataclass

UNKNOWN="—"
SOURCE="IDR_UNIT115_125_STAGE111Z31BE"

@dataclass(frozen=True)
class AdvancedValue:
    id:int
    title:str
    link:str=""
    def __post_init__(self):
        if type(self.id) is not int or not 0<=self.id<=0xffffffff:
            raise ValueError("UInt32 expected")

@dataclass(frozen=True)
class AdvancedCell:
    values:tuple[AdvancedValue,...]
    composite:bool=False
    def __post_init__(self):
        if type(self.composite) is not bool or any(
            not isinstance(x,AdvancedValue) for x in self.values):
            raise ValueError("Invalid advanced value list")
    def get_id(self,index:int)->int:
        if type(index) is not int or not 0<=index<len(self.values):
            raise IndexError("AdvancedCell index")
        return self.values[index].id
    def get_index_by_id(self,value:int)->int:
        check_uint32(value)
        return next((i for i,x in enumerate(self.values) if x.id==value),-1)
    def get_link_by_id(self,value:int)->str:
        index=self.get_index_by_id(value)
        return self.values[index].link if index>=0 else ""
    def get_title_by_id(self,value:int)->str:
        check_uint32(value)
        if self.composite:
            labels=[x.title for x in self.values if (x.id&value)==x.id]
            return "; ".join(labels) if labels else "---"
        index=self.get_index_by_id(value)
        return self.values[index].title if index>=0 else f"(0x{value:08X})"

def check_uint32(value):
    if type(value) is not int or not 0<=value<=0xffffffff:
        raise ValueError("UInt32 expected")

MODBUS_ENDIAN=AdvancedCell(tuple(AdvancedValue(i,t) for i,t in (
    (0,"EndianCell0"),(0x99999999,"EndianCell9"),(0x66666666,"EndianCell6"))))
HF_MODE=AdvancedCell(tuple(AdvancedValue(i,t) for i,t in enumerate(
    ("Off","6.4 кГц","10 кГц","15 кГц"))))

@dataclass(frozen=True)
class ConfigField:
    key:str
    offset:int
    cell_type:int
    bounds:tuple[str,str]|None=None
    advanced:str|None=None
    suffix:str=""
    def __post_init__(self):
        if type(self.offset) is not int or not 0<=self.offset<65536 or self.offset%2:
            raise ValueError("Invalid source offset")

NETWORK_FIELDS=(
    ConfigField("ConfigIP",0x04,7),
    ConfigField("ConfigNetmask",0x06,15),
    ConfigField("ConfigGateway",0x08,7),
    ConfigField("ConfigModbusPort",0x0a,2,("1","65535")),
    ConfigField("ConfigModbusEndian",0x0c,10,advanced="modbus_endian"),
    ConfigField("ConfigNumGroups",0x14,10,advanced="num_groups"),
    ConfigField("ConfigOption",0x40,10,advanced="option"),
    ConfigField("ConfigWifiMode",0x42,10,advanced="wifi_mode"),
    ConfigField("ConfigWifiIP",0x44,7),
    ConfigField("ConfigWifiNetmask",0x46,15),
    ConfigField("ConfigWifiGateway",0x48,7),
    ConfigField("ConfigWifiModbusPort",0x4a,2,("1","65535")),
    ConfigField("ConfigWifiModbusEndian",0x4c,10,advanced="modbus_endian"),
    ConfigField("ConfigWifiSSID",0x50,13),
    ConfigField("ConfigWifiPassword",0x60,14),
)
CALIBRATION_FIELDS=tuple(
    ConfigField("ConfigCalibADC",0x20+2*i,0,suffix=f" {i}") for i in range(8)
)+(
    ConfigField("ConfigCalibTachoMin",0x12,0,("0","10000")),
    ConfigField("ConfigCalibTachoMax",0x10,0,("0","10000")),
)
CHANNEL_FIELDS=(
    ConfigField("ConfigADC",0x02,0,("0.000001","1000000")),
    ConfigField("ConfigOverload",0x04,0,("0","1")),
    ConfigField("ConfigUnits",0x10,9),
    ConfigField("ConfigSerial",0x20,9),
    ConfigField("ConfigHF",0x3e,10,advanced="hf_mode"),
    ConfigField("ConfigLowOctave",0x40,10,advanced="octave_band",suffix=" #1"),
    ConfigField("ConfigHighOctave",0x42,10,advanced="octave_band",suffix=" #1"),
    ConfigField("ConfigLowOctave",0x44,10,advanced="octave_band",suffix=" #2"),
    ConfigField("ConfigHighOctave",0x46,10,advanced="octave_band",suffix=" #2"),
    ConfigField("ConfigMinVoltage",0x52,0,("0","100")),
    ConfigField("ConfigMaxVoltage",0x50,0,("0","100")),
)
UNRESOLVED_ADVANCED=frozenset(("num_groups","option","wifi_mode","octave_band"))

def section_fields(section:str,*,adc:int|None=None):
    if section=="ip" and adc is None:
        return NETWORK_FIELDS,0
    if section=="calib" and adc is None:
        return CALIBRATION_FIELDS,0
    if section=="adc" and type(adc) is int and 1<=adc<=8:
        return CHANNEL_FIELDS,0x100+(adc-1)*0x100
    raise ValueError("Expected ip/calib or adc 1..8")

def source_section_rows(document,section:str,*,adc:int|None=None):
    fields,base=section_fields(section,adc=adc)
    result=[]
    for field in fields:
        address=base+field.offset
        value=document.value(address)
        sensitive=field.key=="ConfigWifiPassword" and value is not None
        result.append({
            "source_key":field.key,
            "source_suffix":field.suffix,
            "address":f"0x{address:04X}",
            "cell_type_code":field.cell_type,
            "source_min":field.bounds[0] if field.bounds else None,
            "source_max":field.bounds[1] if field.bounds else None,
            "advanced_kind":field.advanced,
            "advanced_title_verified":field.advanced in ("modbus_endian","hf_mode"),
            "raw_value":("•••••••• (скрыто)" if sensitive else
                         value.formatted if value is not None else UNKNOWN),
            "sensitive_value_masked":sensitive,
            "observed_in_local_file":value is not None,
            "writable":False,
            "live_device_verified":False,
        })
    return tuple(result)

def source_sections_report(document):
    groups=(source_section_rows(document,"ip"),
            source_section_rows(document,"calib"),
            *(source_section_rows(document,"adc",adc=i) for i in range(1,9)))
    return {
        "source":SOURCE,"network_fields":len(groups[0]),
        "calibration_fields":len(groups[1]),
        "adc_fields":sum(map(len,groups[2:])),
        "local_fields_present":sum(row["observed_in_local_file"]
            for group in groups for row in group),
        "live_device_verified":False,"original_runtime_parity_verified":False,
        "device_writes_allowed":False,"vendor_fmtchar_decoding_assumed":False,
    }
