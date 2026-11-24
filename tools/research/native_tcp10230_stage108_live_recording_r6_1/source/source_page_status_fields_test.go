package main
import("encoding/binary";"testing")
func TestOriginalPageStatusFifteenSourceRegisters(t *testing.T){
 m:=&Monitor{}
 fields:=m.snapshotSourcePageStatusFields()
 if len(fields)!=15 {t.Fatal(len(fields))}
 for i,f:=range fields {
  s:=sourcePageStatusSpecs[i]
  if f.Index!=i||f.Key!=s.Key||f.Address!=s.Address||f.WordCount!=s.Words||f.Valid||f.RawHexLE!=nil {t.Fatalf("%+v",f)}
 }
 // StatusSerial type 11 occupies exactly 0x1000..0x1003.
 copy(m.image.Data[0x1000*2:],[]byte("AB123456"))
 for i:=0;i<4;i++ {
  m.image.Valid[0x1000+i]=true
  serial:=m.snapshotSourcePageStatusFields()[0]
  if serial.WordCount!=4 || serial.Valid!=(i==3) {t.Fatalf("serial partial width: %+v",serial)}
  if i<3 && serial.RawHexLE!=nil {t.Fatal("partial serial leaked")}
  if i==3 && (serial.RawHexLE==nil || *serial.RawHexLE!="4142313233343536") {t.Fatalf("serial bytes: %+v",serial)}
 }
 if m.snapshotSourcePageStatusFields()[1].Valid {t.Fatal("serial overlaps firmware")}
 m.image.Valid[0x1006]=true
 if m.snapshotSourcePageStatusFields()[2].Valid {t.Fatal("half DWORD")}
 m.image.Valid[0x1007]=true
 binary.LittleEndian.PutUint32(m.image.Data[0x1006*2:],0x12345678)
 f:=m.snapshotSourcePageStatusFields()[2]
 if !f.Valid||*f.RawHexLE!="78563412" {t.Fatalf("%+v",f)}
 for i:=0;i<2;i++ {m.image.Valid[0x1014+i]=true}
 a:=m.snapshotSourcePageStatusFields()
 if !a[6].Valid||!a[7].Valid||*a[6].RawHexLE!=*a[7].RawHexLE {t.Fatal("State/Alarm share registers")}
 for i:=0;i<7;i++ {m.image.Valid[0x100C+i]=true}
 if m.snapshotSourcePageStatusFields()[5].Valid {t.Fatal("partial MD5")}
 m.image.Valid[0x1013]=true
 f=m.snapshotSourcePageStatusFields()[5]
 if !f.Valid||len(*f.RawHexLE)!=32 {t.Fatal("16-byte MD5")}
}
