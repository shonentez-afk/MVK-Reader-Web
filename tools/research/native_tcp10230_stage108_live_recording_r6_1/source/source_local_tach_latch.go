package main

// _Unit125 00806030: compare each byte to the PREVIOUS chunk's last byte;
// set local DWORD if any differs; always save final byte. 008085D1 clears
// the DWORD, not the byte, after each accepted 0x3100. IDP 008D30A0 gives
// word addresses 30FE/31FE. Constructor 00806213 initializes last=0.
// Keep wire RegisterImage immutable with respect to these LOCAL writes.
import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "hash"
    "os"
    "path/filepath"
)

const sourceLocalTachSchema="MVK_SOURCE_LOCAL_TACH_LATCH_V1"
const sourceLocalTachGateName="SOURCE_LOCAL_TACH_GATE.jsonl"
const sourceLocalTachGateMaxRecords=4000000

type sourceLocalTachState struct {
    last [2]byte
    value [2]byte
    mask [2]uint8
}
func (s *sourceLocalTachState) observe(tach int,payload []byte) {
    if tach<0||tach>=2||len(payload)==0{return}
    for _,v:=range payload {
        if v!=s.last[tach] {s.value[tach]=1;s.mask[tach]=3;break}
    }
    s.last[tach]=payload[len(payload)-1]
}
func (s *sourceLocalTachState) resetTick(){
    s.value=[2]byte{}
    s.mask=[2]uint8{3,3}
}
func (s *sourceLocalTachState) onBlock(block RegBlock){
    // PARAM writes the same original memory at these addresses. If a
    // wire descriptor overwrites a word, only that local override expires.
    for ch:=0;ch<2;ch++{
        addr:=0x30fe+0x100*ch
        for word:=0;word<2;word++{
            if int(block.Addr)<=addr+word && addr+word<int(block.Addr)+int(block.Words){
                s.mask[ch]&=^(uint8(1)<<uint(word))
            }
        }
    }
}
func (s *sourceLocalTachState) projected(image *RegisterImage,tach int)*string{
    addr:=0x30fe+0x100*tach
    var raw [4]byte
    for word:=0;word<2;word++{
        if s.mask[tach]&(1<<uint(word))!=0{
            if word==0{raw[0]=s.value[tach]}
        }else{
            if !image.Valid[addr+word]{return nil}
            copy(raw[word*2:word*2+2],image.Data[(addr+word)*2:(addr+word)*2+2])
        }
    }
    v:=hex.EncodeToString(raw[:])
    return &v
}

type sourceLocalTachJournal struct {
    state sourceLocalTachState
    f *os.File
    digest hash.Hash
    records uint64
}
type sourceLocalTachGateRecord struct {
    Schema string `json:"schema"`
    Frame uint64 `json:"frame_index_one_based"`
    FrameSHA string `json:"frame_sha256"`
    Channel int `json:"channel"`
    SelectedRate uint32 `json:"selected_rate_hz"`
    Frozen bool `json:"freeze_update"`
    Accepted bool `json:"source_receive_gate_accepted"`
}
func (m *Monitor) ensureSourceLocalTach()error{
    if m.sourceTach!=nil{return nil}
    f,e:=os.OpenFile(filepath.Join(m.dir,sourceLocalTachGateName),
        os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600)
    if e!=nil{return e}
    m.sourceTach=&sourceLocalTachJournal{f:f,digest:sha256.New()}
    return nil
}
func (j *sourceLocalTachJournal) onSample(m *Monitor,f Frame,h SampleHeader,accepted bool)error{
    gate:=m.sourceOriginalRXGate
    if j.f==nil||gate==nil||j.records>=sourceLocalTachGateMaxRecords||
       f.Type!=typeTach||h.Channel<8||h.Channel>9||h.Samples<=0||
       len(f.Raw)!=28+h.Samples*4||accepted!=(!gate.frozen&&h.Rate==gate.rate){
        return errors.New("invalid source local TACH receive evidence")
    }
    sum:=sha256.Sum256(f.Raw)
    row:=sourceLocalTachGateRecord{Schema:sourceLocalTachSchema,Frame:m.summary.TotalFrames,
        FrameSHA:hex.EncodeToString(sum[:]),Channel:h.Channel+1,
        SelectedRate:gate.rate,Frozen:gate.frozen,Accepted:accepted}
    data,e:=json.Marshal(row);if e!=nil{return e}
    data=append(data,'\n')
    n,e:=j.f.Write(data);if e!=nil{return e}
    if n!=len(data){return errors.New("short source local TACH gate write")}
    _,_=j.digest.Write(data);j.records++
    if accepted {j.state.observe(h.Channel-8,f.Raw[28:])}
    return nil
}
func (j *sourceLocalTachJournal) finalize(m *Monitor)error{
    if j.f==nil{return errors.New("source local TACH journal absent")}
    if e:=j.f.Close();e!=nil{return e}
    j.f=nil
    m.summary.SourceLocalTachGateSHA256=hex.EncodeToString(j.digest.Sum(nil))
    m.summary.SourceLocalTachGateRecords=j.records
    m.filenames=append(m.filenames,sourceLocalTachGateName)
    m.summary.Files[sourceLocalTachGateName]=sourceLocalTachGateName
    return nil
}
func (j *sourceLocalTachJournal) cleanup(){
    if j.f!=nil{_=j.f.Close();j.f=nil}
}
