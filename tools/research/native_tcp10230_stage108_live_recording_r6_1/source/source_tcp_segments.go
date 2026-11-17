package main

// _Unit125.pas 008089A3-00808B15: real Task2 starts a new TIdTCPClient
// after disconnect. Preserve a SHA-verified separate RAW for EVERY accepted
// TCP socket and never certify the concatenation as one original measurement.
import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "errors"
 "fmt"
 "io"
 "os"
 "path/filepath"
 "time"
)
const sourceTCPSegmentManifestName="SOURCE_TASK2_TCP_SEGMENTS.json"
const sourceTCPSegmentSchema="MVK_SOURCE_TASK2_TCP_SEGMENTS_V1"

type sourceTCPSegment struct {
 Index int `json:"index"`
 ConnectedUTC string `json:"connected_utc"`
 DisconnectedUTC string `json:"disconnected_utc"`
 StartOffset uint64 `json:"raw_offset_start"`
 EndOffset uint64 `json:"raw_offset_end_exclusive"`
 RawBytes uint64 `json:"raw_bytes"`
 SHA256 string `json:"raw_sha256"`
 RawFile string `json:"separate_raw_file"`
 EndReason string `json:"end_reason"`
 AbandonedTailBytes int `json:"incomplete_application_tail_at_disconnect"`
 CommandBytesStart uint64 `json:"total_command_bytes_before_connect"`
 CommandBytesEnd uint64 `json:"total_command_bytes_after_disconnect"`
}
type sourceTCPLedger struct {
 Segments []sourceTCPSegment
 Active int
}
func (m *Monitor) sourceSentBytes() uint64 {
 if m.sourceTask2TX!=nil{return m.sourceTask2TX.sentBytes}
 return 0
}
func (l *sourceTCPLedger) begin(m *Monitor) error {
 if l.Active!=0{return errors.New("source TCP session already active")}
 if len(l.Segments)>0 {
  // Absolutely no stale registers, fragment, DSP status or sample-index
  // continuity from the old TCP connection may enter the new session.
  m.f=&Framer{}
  m.image=RegisterImage{}
  m.liveDSPSeen=[8]bool{}
  m.liveDSPStatus=[8]uint32{}
  m.liveLastAUXUTC=""
  m.liveLastPacket=time.Time{}
  for i:=range m.summary.Channels {m.summary.Channels[i].seen=false}
  if m.liveBin!=nil {m.liveBin.preview=nil}
  if m.sourceTask2TX!=nil {m.sourceTask2TX.resetForNewSourceSocket(m)}
  m.summary.SourceTCPMultiSocket=true
  m.warn("New original Task2 TCP session: old framer/status discarded, single-socket BIN cannot be certified")
 }
 l.Segments=append(l.Segments,sourceTCPSegment{
  Index:len(l.Segments)+1,ConnectedUTC:time.Now().UTC().Format(time.RFC3339Nano),
  StartOffset:m.summary.RawBytes,CommandBytesStart:m.sourceSentBytes(),
 })
 l.Active=len(l.Segments)
 m.summary.SourceTCPConnectionCount=uint64(len(l.Segments))
 m.note(fmt.Sprintf("SOURCE TCP CONNECT #%d: RAW offset %d",l.Active,m.summary.RawBytes))
 return nil
}
func (l *sourceTCPLedger) finish(m *Monitor,reason string) {
 if l==nil||l.Active==0{return}
 s:=&l.Segments[l.Active-1]
 s.DisconnectedUTC=time.Now().UTC().Format(time.RFC3339Nano)
 s.EndOffset=m.summary.RawBytes
 s.RawBytes=s.EndOffset-s.StartOffset
 s.EndReason=reason
 s.CommandBytesEnd=m.sourceSentBytes()
 if m.f!=nil {
  s.AbandonedTailBytes=len(m.f.Tail)
  m.summary.SourceTCPAbandonedTailBytes+=uint64(s.AbandonedTailBytes)
 }
 m.note(fmt.Sprintf("SOURCE TCP DISCONNECT #%d (%s), RAW bytes %d, unpaired tail %d",
  s.Index,reason,s.RawBytes,s.AbandonedTailBytes))
 l.Active=0
}
func (l *sourceTCPLedger) writeVerifiedArtifacts(m *Monitor) error {
 if l==nil||len(l.Segments)==0{return nil}
 if l.Active!=0{return errors.New("source TCP segment not closed")}
 in,e:=os.Open(filepath.Join(m.dir,"incoming.raw"))
 if e!=nil{return e}
 defer in.Close()
 st,e:=in.Stat()
 if e!=nil{return e}
 if uint64(st.Size())!=m.summary.RawBytes{return errors.New("original RAW length changed")}
 previous:=uint64(0)
 for i:=range l.Segments{
  seg:=&l.Segments[i]
  if seg.StartOffset!=previous||seg.EndOffset<seg.StartOffset||seg.EndOffset>m.summary.RawBytes {
   return fmt.Errorf("non-contiguous source TCP RAW segment %d",seg.Index)
  }
  seg.RawBytes=seg.EndOffset-seg.StartOffset
  seg.RawFile=fmt.Sprintf("SOURCE_TCP_SEGMENT_%04d.raw",seg.Index)
  path:=filepath.Join(m.dir,seg.RawFile)
  out,e:=os.OpenFile(path,os.O_CREATE|os.O_EXCL|os.O_WRONLY,0600)
  if e!=nil{return e}
  h:=sha256.New()
  n,copyErr:=io.Copy(io.MultiWriter(out,h),
       io.NewSectionReader(in,int64(seg.StartOffset),int64(seg.RawBytes)))
  if copyErr==nil && uint64(n)!=seg.RawBytes{copyErr=io.ErrUnexpectedEOF}
  if copyErr==nil{copyErr=out.Sync()}
  if err:=out.Close();copyErr==nil{copyErr=err}
  if copyErr!=nil{_ = os.Remove(path);return copyErr}
  seg.SHA256=hex.EncodeToString(h.Sum(nil))
  m.filenames=append(m.filenames,seg.RawFile)
  m.summary.Files[seg.RawFile]=seg.RawFile
  previous=seg.EndOffset
 }
 if previous!=m.summary.RawBytes{return errors.New("source TCP RAW coverage incomplete")}
 doc:=map[string]any{
  "schema":sourceTCPSegmentSchema,
  "session_id":filepath.Base(m.dir),
  "instrument_ipv4":m.summary.IP,
  "source_raw_sha256":m.summary.RawSHA256,
  "source_tcp_connection_count":len(l.Segments),
  "source_tcp_reconnects_after_raw":m.summary.SourceTCPReconnectAfterRAW,
  "single_rate_bin_certifiable":len(l.Segments)==1 && !m.summary.SourceRateTransition,
  "original_delphi_byte_parity_verified":false,
  "segments":l.Segments,
 }
 b,e:=json.MarshalIndent(doc,"","  ")
 if e!=nil{return e}
 b=append(b,'\n')
 if e=os.WriteFile(filepath.Join(m.dir,sourceTCPSegmentManifestName),b,0600);e!=nil{return e}
 m.filenames=append(m.filenames,sourceTCPSegmentManifestName)
 m.summary.Files[sourceTCPSegmentManifestName]=sourceTCPSegmentManifestName
 sum:=sha256.Sum256(b)
 m.summary.SourceTCPSegmentManifestSHA256=hex.EncodeToString(sum[:])
 m.summary.SourceTCPSegmentCopiesVerified=true
 return nil
}
