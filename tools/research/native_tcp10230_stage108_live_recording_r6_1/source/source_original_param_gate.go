package main

// Source _Unit125.pas 0080844F and 0080850C..008085E1:
// an empty PARAM is a valid no-op; FreezeUpdate drains PARAM register
// words WITHOUT applying them to Delphi storage or triggering WriteValues.
// This local SHA-checked frame ledger makes independent RAW replay aware
// of those operator-only timing decisions. No device TX, no second socket.
import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "hash"
    "os"
    "path/filepath"
)

const sourceOriginalParamGateName="SOURCE_ORIGINAL_PARAM_FRAME_GATE.jsonl"
const sourceOriginalParamGateSchema="MVK_SOURCE_ORIGINAL_PARAM_GATE_V1"
const sourceOriginalParamGateMaxRecords=1000000

type sourceOriginalParamGateRecord struct {
    Schema string `json:"schema"`
    FrameIndex uint64 `json:"frame_index_one_based"`
    FrameSHA256 string `json:"frame_sha256"`
    DescriptorCount int `json:"descriptor_count"`
    FreezeUpdate bool `json:"freeze_update"`
    AUX4700 bool `json:"is_aux4700"`
    Values3100 bool `json:"contains_values_3100"`
    Values3100DescriptorCount int `json:"source_values_3100_descriptor_count"`
}

type sourceOriginalParamGateJournal struct {
    f *os.File
    digest hash.Hash
    records uint64
    closed bool
}
func countOriginalValuesDescriptors(blocks []RegBlock) int {
    count := 0
    for _, block := range blocks {
        if block.Addr == 0x3100 {
            count++
        }
    }
    return count
}

func newSourceOriginalParamGateJournal(dir string)(*sourceOriginalParamGateJournal,error){
    f,e:=os.OpenFile(filepath.Join(dir,sourceOriginalParamGateName),
        os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
    if e!=nil {return nil,e}
    return &sourceOriginalParamGateJournal{f:f,digest:sha256.New()},nil
}
func(j *sourceOriginalParamGateJournal)onParam(m *Monitor,f Frame,blocks []RegBlock,
    frozen bool)error{
    if j==nil{return nil}
    if j.closed || j.f==nil{return errors.New("source PARAM frame gate closed")}
    if j.records>=sourceOriginalParamGateMaxRecords{
        return errors.New("source PARAM frame gate max records exceeded")
    }
    if f.Type!=typeParam || len(f.Raw)<28 || m.summary.TotalFrames==0{
        return errors.New("source PARAM gate requires complete frame")
    }
    sum:=sha256.Sum256(f.Raw)
    values:=countOriginalValuesDescriptors(blocks)
    entry:=sourceOriginalParamGateRecord{
        Schema:sourceOriginalParamGateSchema,
        FrameIndex:m.summary.TotalFrames,
        FrameSHA256:hex.EncodeToString(sum[:]),
        DescriptorCount:len(blocks),
        FreezeUpdate:frozen,AUX4700:len(f.Raw)==4700,Values3100:values>0,
        Values3100DescriptorCount:values,
    }
    line,e:=json.Marshal(entry)
    if e!=nil{return e}
    line=append(line,'\n')
    n,e:=j.f.Write(line)
    if e!=nil{return e}
    if n!=len(line){return fmt.Errorf("source PARAM journal short write %d/%d",n,len(line))}
    _,_=j.digest.Write(line)
    j.records++
    return nil
}
func(j *sourceOriginalParamGateJournal)finalize(m *Monitor)error{
    if j==nil || j.closed{return nil}
    if j.f==nil{return errors.New("source PARAM journal file absent")}
    if e:=j.f.Close();e!=nil{return e}
    j.f=nil;j.closed=true
    m.summary.SourceOriginalParamGateSHA256=hex.EncodeToString(j.digest.Sum(nil))
    m.summary.SourceOriginalParamGateRecords=j.records
    m.filenames=append(m.filenames,sourceOriginalParamGateName)
    m.summary.Files[sourceOriginalParamGateName]=sourceOriginalParamGateName
    return nil
}
func(j *sourceOriginalParamGateJournal)cleanup(){
    if j!=nil && j.f!=nil {_=j.f.Close();j.f=nil}
}
