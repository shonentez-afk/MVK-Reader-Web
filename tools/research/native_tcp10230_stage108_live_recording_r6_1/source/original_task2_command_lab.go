package main

// Source-derived OFFLINE duplex TMVKThread Task2 command writer.
// PRIVATE _Unit125.pas:00807E8F..00807F52 / 0080937C..008093FA.
// This lab is NOT called from main.go or the real instrument dialer.
// It can write only to the io.Writer given by local tests (net.Pipe).
// The single production Go TCP/10230 reader retains zero device TX.
import (
    "encoding/binary"
    "errors"
    "fmt"
    "io"
)

const sourceSetRateAddress uint32 = 0x000e
const sourceSetRateWriteLen = 36

// Eight original 32-bit Indy writes followed by the queued Data DWORD.
func sourceSetRateWireBytes(rate uint32) ([]byte,error) {
    if !acceptedRates[rate] { return nil, fmt.Errorf("unsupported source SetRate: %d",rate) }
    words:=[9]uint32{
        typeParam, sourceSetRateWriteLen,
        0,0,0,0,1,
        (2<<16)|sourceSetRateAddress,
        rate,
    }
    data:=make([]byte,sourceSetRateWriteLen)
    for i,w:=range words {
        binary.LittleEndian.PutUint32(data[4*i:],w)
    }
    return data,nil
}

// Original source Task2 (not Native capture) starts Stage0 and queues
// SetRate(65536). A real nonempty PARAM advances to Stage1. Stage3 blocks
// dispatch when source system error is observed. Incoming ACK is unpaired.
type sourceTask2DuplexLab struct {
    stage int
    rate uint32
    pending bool
    sentWrites int
    sentBytes int
    inboundACK int
    inboundDENIED int
    image RegisterImage
    closed bool
}

func newSourceTask2DuplexLab(rate uint32) (*sourceTask2DuplexLab,error) {
    if !acceptedRates[rate] {return nil,errors.New("source rate unsupported")}
    return &sourceTask2DuplexLab{rate:rate,pending:true},nil
}

func (s *sourceTask2DuplexLab) observeFrame(f Frame) error {
    if s.closed {return errors.New("source lab session is closed")}
    switch f.Type {
    case typeParam:
        blocks,e:=decodeBlocks(f.Raw)
        if e!=nil {s.closed=true;return e}
        for _,b:=range blocks {s.image.Put(b)}
        if len(blocks)>0 && s.stage==0 {s.stage=1}
        // Safe laboratory interpretation: require a REAL complete two-word
        // value, not Delphi's uninitialized 0xFFFFFFFF sentinel.
        if value,e:=s.image.Uint32(0x1006);e==nil && value>0 {
            s.stage=3
        }
    case typeAck:
        s.inboundACK++ // original Task2 does not associate this with SetRate
    case typeDenied:
        s.inboundDENIED++
        s.stage=0
        s.closed=true
    }
    return nil
}

// Only an explicitly supplied TEST writer can receive the 36-byte stream.
// Exactly one FIFO element is dispatched, BEFORE the next read in Stage1.
func (s *sourceTask2DuplexLab) writeOneBeforeRead(writer io.Writer) (int,error) {
    if s.closed || !s.pending || s.stage!=1 {return 0,nil}
    if writer==nil {return 0,errors.New("source laboratory writer missing")}
    command,e:=sourceSetRateWireBytes(s.rate)
    if e!=nil {return 0,e}
    s.pending=false // source TList.Get(0)+Delete(0) is before actual Write
    written,e:=writer.Write(command)
    if written>0 {s.sentBytes+=written}
    if e!=nil {s.closed=true;return written,e}
    if written!=len(command) {s.closed=true;return written,io.ErrShortWrite}
    s.sentWrites++
    return written,nil
}

type LiveOriginalTask2TxEvidence struct {
    OriginalWriterExists bool `json:"source_original_writer_present"`
    Stage1FromParam bool `json:"source_stage1_nonempty_param_observed"`
    Status0ValidZero bool `json:"source_system_status0_valid_zero"`
    ValidatedSourceCandidate bool `json:"source_setrate_candidate_after_param"`
    ActualGoAppBytesSent uint64 `json:"source_go_device_app_bytes_sent"`
    OriginalSetRateLength int `json:"source_setrate_frame_size_bytes"`
    NoPhysicalCommandClaim bool `json:"original_source_command_physically_verified"`
}

func (m *Monitor) snapshotOriginalTask2TxEvidence() LiveOriginalTask2TxEvidence {
    status0,e:=m.image.Uint32(0x1006)
    validZero:=e==nil && status0==0
    seenParam:=m.summary.SourceNonemptyParameters>0
    // This is evidence of a potential original command, NOT an attempt to
    // transmit from the single production read-only Native R6 client.
    return LiveOriginalTask2TxEvidence{
        OriginalWriterExists:true,
        Stage1FromParam:seenParam,
        Status0ValidZero:validZero,
        ValidatedSourceCandidate:seenParam && validZero && !m.captureOnly,
        ActualGoAppBytesSent:0,
        OriginalSetRateLength:sourceSetRateWriteLen,
        NoPhysicalCommandClaim:false,
    }
}
