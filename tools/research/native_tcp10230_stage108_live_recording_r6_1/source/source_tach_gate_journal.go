package main

// Compact bounded record of actual local receive-gate decisions.
// Forensic incoming.raw and the V1 PARAM/Freeze ledger are unchanged.
import (
 "bufio"
 "crypto/sha256"
 "encoding/binary"
 "encoding/hex"
 "errors"
 "hash"
 "math"
 "os"
 "path/filepath"
)

const sourceTachGateName="SOURCE_ORIGINAL_TACH_FRAME_GATE.dat"
const sourceTachGateSchema="MVK_SOURCE_TACH_FRAME_GATE_V1_LE64"
const sourceTachGateMaxRecords=8000000
const sourceTachGateRecordSize=64

type sourceTachGateJournal struct {
 f *os.File
 buf *bufio.Writer
 digest hash.Hash
 records uint64
 closed bool
}
func newSourceTachGateJournal(dir string)(*sourceTachGateJournal,error){
 f,err:=os.OpenFile(filepath.Join(dir,sourceTachGateName),os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
 if err!=nil{return nil,err}
 return &sourceTachGateJournal{f:f,buf:bufio.NewWriterSize(f,65536),digest:sha256.New()},nil
}
// 64 bytes: frame index u64, epoch u64, selected Fs u32, wire Fs u32,
// channel u8, flags u8 (freeze/admitted), six zero bytes, frame SHA256.
func(j *sourceTachGateJournal) observe(m *Monitor,f Frame,h SampleHeader,admitted bool)error{
 if j==nil || j.closed || j.f==nil || j.records>=sourceTachGateMaxRecords ||
  m.sourceContract==nil || m.sourceContract.epoch==0 || m.sourceOriginalRXGate==nil ||
  m.summary.TotalFrames==0 || f.Type!=typeTach || h.Channel<8 || h.Channel>9 ||
  len(f.Raw)!=28+h.Samples*4 {return errors.New("source TACH gate invalid/missing/over bound")}
 gate:=m.sourceOriginalRXGate
 if !acceptedRates[gate.rate] || admitted!=(h.Samples>0 && !gate.frozen && h.Rate==gate.rate){
  return errors.New("source TACH admission disagrees with actual gate")
 }
 var row [sourceTachGateRecordSize]byte
 binary.LittleEndian.PutUint64(row[0:8],m.summary.TotalFrames)
 binary.LittleEndian.PutUint64(row[8:16],m.sourceContract.epoch)
 binary.LittleEndian.PutUint32(row[16:20],gate.rate)
 binary.LittleEndian.PutUint32(row[20:24],h.Rate)
 row[24]=byte(h.Channel)
 if gate.frozen {row[25]|=1}
 if admitted {row[25]|=2}
 sum:=sha256.Sum256(f.Raw);copy(row[32:],sum[:])
 n,err:=j.buf.Write(row[:]);if err!=nil || n!=len(row){return errors.New("source TACH gate write failed")}
 _,_=j.digest.Write(row[:]);j.records++
 return nil
}
func(j *sourceTachGateJournal) finalize(m *Monitor)error{
 if j==nil{return nil}
 if j.closed || j.f==nil{return errors.New("source TACH gate already closed")}
 if err:=j.buf.Flush();err!=nil{return err}
 if err:=j.f.Close();err!=nil{return err}
 j.f=nil;j.closed=true
 m.summary.SourceTachGateSchema=sourceTachGateSchema
 m.summary.SourceTachGateSHA256=hex.EncodeToString(j.digest.Sum(nil))
 m.summary.SourceTachGateRecords=j.records
 m.filenames=append(m.filenames,sourceTachGateName)
 m.summary.Files[sourceTachGateName]=sourceTachGateName
 return nil
}
func(j *sourceTachGateJournal) cleanup(){
 if j!=nil && j.f!=nil{_=j.buf.Flush();_=j.f.Close();j.f=nil}
}
func(m *Monitor) observeSourceTach(f Frame,h SampleHeader,admitted bool)error{
 if m.sourceContract==nil && m.sourceTachGate==nil{return nil}
 if m.sourceContract==nil || m.sourceTachGate==nil{return errors.New("incomplete source TACH configuration")}
 if err:=m.sourceTachGate.observe(m,f,h,admitted);err!=nil{return err}
 return m.sourceContract.tach(h.Channel-8,f.Raw[28:],admitted)
}
// Overlay only the two source-local latch DWORDs on a copied VALUES
// trigger image. Never mutate the forensic register image.
func sourceOverlayTachTick(image *RegisterImage,tick *[2]sourceImpulseValue){
 for i,addr:=range impulseAddresses{
  image.Valid[addr]=false;image.Valid[addr+1]=false
  if tick!=nil && tick[i].Known{
   binary.LittleEndian.PutUint32(image.Data[addr*2:(addr+2)*2],tick[i].Value)
   image.Valid[addr]=true;image.Valid[addr+1]=true
  }
 }
}
type sourceMetadataObservationChannel struct {
 Channel int `json:"channel"`
 RangeKnown bool `json:"range_known"`
 RangeRawBits *uint32 `json:"range_raw_bits,omitempty"`
 RangeFactor *float32 `json:"effective_range_factor,omitempty"`
 RangeCurrentSocket bool `json:"range_current_socket"`
 Units string `json:"units"`
 UnitsKnown bool `json:"units_known"`
 UnitsCurrentSocket bool `json:"units_current_socket"`
 FromDescriptor bool `json:"from_descriptor"`
}
type sourceMetadataObservation struct{
 Schema string `json:"schema"`
 SocketEpoch uint64 `json:"socket_epoch"`
 FirstDescriptorSeen bool `json:"first_descriptor_seen"`
 NumericScalingApplied bool `json:"numeric_scaling_applied"`
 ADC []sourceMetadataObservationChannel `json:"adc"`
}
func(s *sourceMetadataLatchCandidate) observation()*sourceMetadataObservation{
 if s==nil{return nil}
 out:=&sourceMetadataObservation{Schema:"MVK_SOURCE_ADC_METADATA_OBSERVATION_V1",SocketEpoch:s.epoch,
  FirstDescriptorSeen:s.firstDescriptor,ADC:make([]sourceMetadataObservationChannel,0,8)}
 for i,c:=range s.channel{
  row:=sourceMetadataObservationChannel{Channel:i+1,RangeKnown:c.RangeKnown,RangeCurrentSocket:c.RangeCurrentSocket,
   Units:c.Units,UnitsKnown:c.UnitsKnown,UnitsCurrentSocket:c.UnitsCurrentSocket,FromDescriptor:c.FromDescriptor}
  if c.RangeKnown{
   bits:=c.RangeBits;row.RangeRawBits=&bits
   if !math.IsNaN(float64(c.Range)) && !math.IsInf(float64(c.Range),0){factor:=c.Range;row.RangeFactor=&factor}
  }
  out.ADC=append(out.ADC,row)
 }
 return out
}
