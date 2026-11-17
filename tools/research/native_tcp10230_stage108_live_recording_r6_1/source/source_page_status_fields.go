package main

// Original _Unit125:008026B0. 15 VISIBLE fields, not 14 StatusCells.
// AddrOffset=0x1000; all data comes from the SAME passive RegisterImage.
import "encoding/hex"
type SourcePageStatusSpec struct { Key string; Address uint16; Words int }
var sourcePageStatusSpecs=[15]SourcePageStatusSpec{
 {"serial",0x1000,2},{"firmware",0x1004,2},{"errors",0x1006,2},
 {"uptime",0x1008,2},{"memory_kib",0x100A,2},{"dsp_md5",0x100C,8},
 {"control_group1",0x1014,2},{"unack_group1",0x1014,2},
 {"control_group2",0x1016,2},{"unack_group2",0x1016,2},
 {"calc_counter",0x1024,2},{"modbus_queries",0x1036,2},
 {"modbus_last_address",0x103A,2},{"modbus_last_count",0x103C,2},
 {"modbus_clients",0x103E,2},
}
type LiveSourcePageStatusField struct {
 Index int `json:"index"`
 Key string `json:"key"`
 Address uint16 `json:"register_address"`
 WordCount int `json:"word_count"`
 Valid bool `json:"valid"`
 RawHexLE *string `json:"raw_hex_le"`
}
func (m *Monitor) snapshotSourcePageStatusFields() []LiveSourcePageStatusField {
 fields:=make([]LiveSourcePageStatusField,0,15)
 for i,s:=range sourcePageStatusSpecs {
  f:=LiveSourcePageStatusField{Index:i,Key:s.Key,Address:s.Address,WordCount:s.Words}
  valid:=true
  for word:=0;word<s.Words;word++ {
   if !m.image.Valid[int(s.Address)+word] {valid=false;break}
  }
  if valid {
   offset:=int(s.Address)*2
   raw:=hex.EncodeToString(m.image.Data[offset:offset+s.Words*2])
   f.Valid=true;f.RawHexLE=&raw
  }
  fields=append(fields,f)
 }
 return fields
}
