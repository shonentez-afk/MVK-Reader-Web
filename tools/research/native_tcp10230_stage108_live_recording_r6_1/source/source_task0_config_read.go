package main

// Task0 read-only IP configuration. Source chain:
// _Unit128.pas bConfigDownloadClick 008495A8 -> Create(ATask=0) at
// 0084964C -> TMVKThread.Execute 00807A98, Task0 Stage1->Stage2
// at 00808769..008087B6. It sends NO SetRate, Flash or reboot.
//
// All files are local to the explicitly approved capture directory.
// NEVER publish secret/password register words from address 0x50..0x7f.
import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "errors"
 "fmt"
 "os"
 "path/filepath"
)
const sourceTask0ConfigName="SOURCE_TASK0_CONFIG_IP_READ.json"
const sourceTask0ConfigSchema="MVK_SOURCE_TASK0_CONFIG_IP_READ_V1"
type sourceTask0FieldSpec struct {
 Key string
 Address uint16
 Words int
}
var task0SafeIPFields=[]sourceTask0FieldSpec{
 {"ConfigIP",0x0004,2},
 {"ConfigNetmask",0x0006,2},
 {"ConfigGateway",0x0008,2},
 {"ConfigModbusPort",0x000a,2},
 {"ConfigModbusEndian",0x000c,2},
 {"ConfigNumGroups",0x0014,2},
 {"ConfigOption",0x0040,2},
 {"ConfigWifiMode",0x0042,2},
 {"ConfigWifiIP",0x0044,2},
 {"ConfigWifiNetmask",0x0046,2},
 {"ConfigWifiGateway",0x0048,2},
 {"ConfigWifiModbusPort",0x004a,2},
 {"ConfigWifiModbusEndian",0x004c,2},
}
type sourceTask0Field struct {
 Key string `json:"key"`
 Address uint16 `json:"register_address"`
 WordCount int `json:"word_count"`
 Valid bool `json:"valid"`
 RawHexLE *string `json:"raw_hex_le"`
}
type sourceTask0Receipt struct {
 Schema string `json:"schema"`
 SourceOriginalTask int `json:"original_task"`
 SessionID string `json:"session_id"`
 DeviceIPv4 string `json:"instrument_ipv4"`
 RawSHA256 string `json:"source_raw_sha256"`
 RawBytes uint64 `json:"raw_bytes"`
 ReadOnly bool `json:"device_commands_not_sent"`
 ConfigParamConfirmed bool `json:"source_nonempty_param_received"`
 ConfigFieldsConfirmed int `json:"config_fields_confirmed"`
 OriginalByteParityVerified bool `json:"original_delphi_byte_parity_verified"`
 Fields []sourceTask0Field `json:"fields"`
}
func sourceTask0Snapshot(m *Monitor, report Summary)(sourceTask0Receipt,error){
 if m==nil||!m.sourceTask0ConfigRead||report.EndReason!="SOURCE_TASK0_CONFIG_READ_COMPLETE"||
    report.SourceNonemptyParameters==0||report.RawBytes==0||!report.ReadOnly||
    report.CaptureOnly||m.sourceTask2TX!=nil{
  return sourceTask0Receipt{},errors.New("Task0 source read was not completed without hardware writes")
 }
 r:=sourceTask0Receipt{
  Schema:sourceTask0ConfigSchema,SourceOriginalTask:0,
  SessionID:filepath.Base(m.dir),DeviceIPv4:report.IP,
  RawSHA256:report.RawSHA256,RawBytes:report.RawBytes,
  ReadOnly:true,ConfigParamConfirmed:true,OriginalByteParityVerified:false,
 }
 for _,spec:=range task0SafeIPFields {
  item:=sourceTask0Field{Key:spec.Key,Address:spec.Address,WordCount:spec.Words}
  valid:=true
  for i:=0;i<spec.Words;i++{
   if !m.image.Valid[int(spec.Address)+i]{valid=false;break}
  }
  if valid {
   start:=int(spec.Address)*2
   raw:=hex.EncodeToString(m.image.Data[start:start+spec.Words*2])
   item.Valid=true
   item.RawHexLE=&raw
   r.ConfigFieldsConfirmed++
  }
  r.Fields=append(r.Fields,item)
 }
 return r,nil
}
func writeSourceTask0ConfigSnapshot(m *Monitor, report Summary)error{
 receipt,err:=sourceTask0Snapshot(m,report)
 if err!=nil{return err}
 // Finalize() already closed/synced incoming.raw and computed its SHA.
 rawPath:=filepath.Join(m.dir,"incoming.raw")
 data,err:=os.ReadFile(rawPath)
 if err!=nil{return err}
 if uint64(len(data))!=report.RawBytes {
  return errors.New("source Task0 RAW length mismatch")
 }
 h:=sha256.Sum256(data)
 if hex.EncodeToString(h[:])!=report.RawSHA256 {
  return errors.New("source Task0 RAW SHA256 mismatch")
 }
 encoded,err:=json.MarshalIndent(receipt,"","  ")
 if err!=nil{return err}
 path:=filepath.Join(m.dir,sourceTask0ConfigName)
 f,err:=os.OpenFile(path,os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
 if err!=nil{return err}
 _,err=f.Write(append(encoded,'\n'))
 if err==nil{err=f.Sync()}
 if e:=f.Close();err==nil{err=e}
 if err!=nil{
  _=os.Remove(path)
  return fmt.Errorf("source Task0 file write: %w",err)
 }
 return nil
}
