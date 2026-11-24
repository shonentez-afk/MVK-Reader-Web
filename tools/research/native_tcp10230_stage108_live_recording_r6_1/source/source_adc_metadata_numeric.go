package main

// Original first-descriptor storage metadata is separate from the current
// raw CONFIG image and from the existing calibrated Native BIN spool.
// Normal positive finite Single values only; unknown/exceptional scaling
// refuses the source view, but never changes the captured RAW or writer.
import (
 "encoding/binary"
 "math"
)

const sourceStorageMetadataADC="ORIGINAL_LIVE_ADC_LATCHED_RANGE_FLOAT32"

type sourceADCWindowMetadata struct {
 SocketEpoch uint64 `json:"socket_epoch"`
 FromDescriptor bool `json:"from_descriptor"`
 RangeRawBits uint32 `json:"range_raw_bits"`
 RangeCurrentSocket bool `json:"range_current_socket"`
 UnitsKnown bool `json:"units_known"`
 Units string `json:"units"`
 UnitsCurrentSocket bool `json:"units_current_socket"`
}

func (s *sourceMetadataLatchCandidate) windowMetadata(i int)*sourceADCWindowMetadata {
 if s==nil || s.epoch==0 || i<0 || i>=8{return nil}
 c:=s.channel[i]
 if !c.RangeKnown || !finiteF32(c.Range) || c.Range<=0{return nil}
 return &sourceADCWindowMetadata{SocketEpoch:s.epoch,FromDescriptor:c.FromDescriptor,
  RangeRawBits:c.RangeBits,RangeCurrentSocket:c.RangeCurrentSocket,
  UnitsKnown:c.UnitsKnown,Units:c.Units,UnitsCurrentSocket:c.UnitsCurrentSocket}
}
func (m *sourceADCWindowMetadata) factor()float32{
 if m==nil{return 0}
 f:=math.Float32frombits(m.RangeRawBits)
 if f==0{return 1}
 return f
}
func sameSourceADCMetadata(a,b *sourceADCWindowMetadata)bool{
 if a==nil || b==nil{return a==nil && b==nil}
 return *a==*b
}
func (m *Monitor) syncSourceADCMetadata(){
 if m.sourceContract==nil || m.sourceOriginalStorage==nil{return}
 for i:=0;i<8;i++{
  c:=&m.sourceOriginalStorage.channels[i]
  c.metadata=m.sourceContract.windowMetadata(i)
  // Do not discard already stored physical bytes at the first descriptor
  // or re-multiply old samples. The current factor is used at read time.
  c.domain=sourceStorageMetadataADC
 }
}
func(m *Monitor) sourceContractParam(b RegBlock,frozen bool)(*[2]sourceImpulseValue,error){
 before:=m.sourceContract.firstDescriptor
 tick,err:=m.sourceContract.param(int(b.Addr),b.Payload,frozen)
 if err==nil && !before && m.sourceContract.firstDescriptor{m.syncSourceADCMetadata()}
 return tick,err
}
func(m *Monitor) appendMetadataADC(h SampleHeader,payload []byte)error{
 c:=&m.sourceOriginalStorage.channels[h.Channel]
 c.metadata=m.sourceContract.windowMetadata(h.Channel)
 c.domain=sourceStorageMetadataADC
 // Reject exceptional/unknown local numeric views while leaving forensic
 // RAW and original wire WriteData untouched. Never synthesize zeros.
 reject:=func(){
  c.rejectedScalingElements+=uint64(h.Samples)
  c.validPos=c.rxPos
  c.nextDeviceIndex=h.Index+uint32(h.Samples)
  c.sampleRate=h.Rate
  c.seen=true
 }
 if c.metadata==nil{reject();return nil}
 if h.NonFinite>0{return m.sourceOriginalStorage.appendFrame(h,payload,sourceStorageMetadataADC)}
 scaled,err:=sourceApplyOriginalFRange(payload,c.metadata.factor())
 if err!=nil{reject();return nil}
 for i:=0;i<len(scaled);i+=4{
  if binary.LittleEndian.Uint32(scaled[i:i+4])&0x7f800000==0x7f800000{reject();return nil}
 }
 if err=m.sourceOriginalStorage.appendFrame(h,scaled,sourceStorageMetadataADC);err!=nil{return err}
 m.sourceContract.numericScalingApplied=true
 return nil
}
