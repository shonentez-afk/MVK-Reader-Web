package main

// Actual offline Go regression for VALUES descriptor-order sampling.
// Synthetic input only, no original EXE, hardware or vendor data.
import (
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func prefixTestBlock(addr uint16, bits uint32) RegBlock {
    return RegBlock{Addr:addr, Words:2, Payload:sourceRawTestWords(bits)}
}

func prefixTestRead(t *testing.T, dir, name string) []byte {
    t.Helper()
    b,err:=os.ReadFile(filepath.Join(dir,name))
    if err!=nil{t.Fatal(err)}
    return b
}

func prefixTestSHA(b []byte) string {
    h:=sha256.Sum256(b)
    return hex.EncodeToString(h[:])
}

func prefixTestEvent(t *testing.T, m *Monitor) sourceLiveValuesEvent {
    t.Helper()
    var ev sourceLiveValuesEvent
    if err:=json.Unmarshal(prefixTestRead(t,m.dir,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl"),&ev);err!=nil{t.Fatal(err)}
    if ev.RawTickEvidence==nil || len(ev.RawTickEvidence.OrderedFields)!=1 {
        t.Fatalf("missing single selected field: %+v",ev)
    }
    return ev
}

func TestValuesTriggerPrefixOrderAndFinalImage(t *testing.T) {
    seed:=prefixTestBlock(0x2002,0x3f800000)
    two:=prefixTestBlock(0x2002,0x40000000)
    three:=prefixTestBlock(0x2002,0x40400000)
    trigger:=prefixTestBlock(0x3100,0x11223344)
    cases:=[]struct{
        name string
        blocks []RegBlock
        inactive, frozen, invalid bool
        wantRows int
        wantRow, wantFinal, wantText string
    }{
        {"trigger_only",[]RegBlock{trigger},false,false,false,1,"0000803f","0000803f","1"},
        {"before",[]RegBlock{two,trigger},false,false,false,1,"00000040","00000040","2"},
        {"after",[]RegBlock{trigger,two},false,false,false,1,"0000803f","00000040","1"},
        {"both_sides",[]RegBlock{two,trigger,three},false,false,false,1,"00000040","00004040","2"},
        {"duplicate",[]RegBlock{trigger,two,trigger},false,false,true,0,"","00000040",""},
        {"freeze",[]RegBlock{trigger,two},false,true,false,0,"","0000803f",""},
        {"inactive",[]RegBlock{trigger,two},true,false,false,0,"","00000040",""},
        {"no_trigger",[]RegBlock{two},false,false,false,0,"","00000040",""},
    }
    for _,tc:=range cases {
        t.Run(tc.name,func(t *testing.T){
            m,c:=markFixture(t);defer m.CloseFiles()
            m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
            m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
            var ch [10]bool;ch[0]=true
            var spec [43]bool;spec[0]=true
            var vals [73]bool
            if !tc.inactive{sourceSelectedMark(t,c,m,1,"values_begin",ch,spec,vals)}
            at:=time.Date(2026,11,24,4,0,0,0,time.UTC)
            first:=makeParam([]RegBlock{seed})
            if err:=m.ProcessChunk(first,at);err!=nil{t.Fatal(err)}
            m.sourceOriginalRXGate.frozen=tc.frozen
            packet:=makeParam(tc.blocks)
            if _,err:=decodeBlocks(packet);err!=nil{t.Fatal(err)}
            if err:=m.ProcessChunk(packet,at.Add(time.Second));err!=nil{t.Fatal(err)}
            final:=m.sourceLiveRawDWORD(0x2002)
            if final==nil || *final!=tc.wantFinal{t.Fatalf("final image %v, want %s",final,tc.wantFinal)}
            if (m.summary.InvalidFrames>0)!=tc.invalid{t.Fatalf("invalid frame counter %+v",m.summary)}
            report,_,err:=m.Finalize("STOPPED_BY_USER");if err!=nil{t.Fatal(err)}
            if int(report.SourceLiveValuesEventRecords)!=tc.wantRows{t.Fatalf("rows %d want %d",report.SourceLiveValuesEventRecords,tc.wantRows)}
            wire:=append(append([]byte{},first...),packet...)
            if raw:=prefixTestRead(t,m.dir,"incoming.raw");!bytes.Equal(raw,wire)||report.RawSHA256!=prefixTestSHA(wire){t.Fatal("RAW or SHA changed")}
            if tc.wantRows==0{
                if !tc.inactive {
                    if b:=prefixTestRead(t,m.dir,"SOURCE_W01_VALUES_3100_RECEIVED.jsonl");len(b)!=0{t.Fatal("unexpected VALUES bytes")}
                }
                if tc.invalid && m.sourceLiveValuesWriter.windows[0].Outcome!="INTERRUPTED"{t.Fatal("duplicate error certified a clean window")}
                return
            }
            ev:=prefixTestEvent(t,m)
            field:=ev.RawTickEvidence.OrderedFields[0]
            if field.RawLE==nil || *field.RawLE!=tc.wantRow || !field.SourceWordValid ||
                ev.PayloadLEHex!="44332211" || ev.FrameIndex!=2 || ev.TickIndex!=0 {
                t.Fatalf("trigger-prefix event differs: %+v",ev)
            }
            tick:=ev.RawTickEvidence
            if tick.OriginalGetValueTextParityVerified || tick.OriginalCSVByteParityVerified || tick.OriginalLocalTimeParityVerified{
                t.Fatal("synthetic prefix incorrectly claimed original parity")
            }
            rawRow:=prefixTestRead(t,m.dir,"SOURCE_W01_VALUES_3100_RAW_LAYOUT.csv")
            textRow:=prefixTestRead(t,m.dir,"SOURCE_W01_VALUES_3100_TEXT_CANDIDATE.csv")
            if string(rawRow)!="04:00:01.000|RAW_F32_CANDIDATE:"+tc.wantRow+"\r\n" ||
                string(textRow)!="04:00:01.000|"+tc.wantText+"\r\n"{
                t.Fatalf("saved row not trigger-prefix bound: %q / %q",rawRow,textRow)
            }
            if prefixTestSHA(rawRow)!=tick.RawRowSHA256 || prefixTestSHA(textRow)!=tick.TextCandidateRowSHA256{
                t.Fatal("raw/text row digests differ")
            }
            w:=m.sourceLiveValuesWriter.windows[0]
            profile:=prefixTestRead(t,m.dir,w.SourceRUProfileCandidateName)
            header,err:=sourceRUValuesCandidateHeader(w);if err!=nil{t.Fatal(err)}
            row,err:=sourceRUValuesCandidateRow(*tick);if err!=nil{t.Fatal(err)}
            if !bytes.Equal(profile,append(header,row...)) || prefixTestSHA(row)!=tick.RUProfileCandidateRowSHA256 ||
                prefixTestSHA(profile)!=w.SourceRUProfileCandidateSHA256 ||
                w.SourceRawLayoutSHA256!=prefixTestSHA(rawRow)||w.SourceTextCandidateSHA256!=prefixTestSHA(textRow)||
                w.Outcome!="CLOSED_BY_SOURCE_THREAD" || m.sourceLiveValuesWriter.active!=nil ||
                w.file!=nil || w.layoutFile!=nil || w.textFile!=nil || w.ruProfileFile!=nil{
                t.Fatal("prefix artifacts or clean Stop close disagree")
            }
            t.Logf("prefix=%s final=%s row=%s",tc.wantRow,*final,tc.wantText)
        })
    }
}

func TestValuesTriggerPrefixTachFreshnessAndInclusiveTrigger(t *testing.T){
    // TACH1 +FE must have both current PARAM words at the trigger;
    // TACH2 index 0 is the trigger address itself and must be included.
    for _,tc:=range []struct{
        name string
        tachChannel,cell int
        seed,blocks []RegBlock
        want string
        finalAddr int
        final string
    }{
        {"before",8,35,nil,[]RegBlock{prefixTestBlock(0x30fe,0x12345678),prefixTestBlock(0x3100,0)},"78563412",0x30fe,"78563412"},
        {"after",8,35,nil,[]RegBlock{prefixTestBlock(0x3100,0),prefixTestBlock(0x30fe,0x12345678)},"",0x30fe,"78563412"},
        {"stale_prior_frame",8,35,[]RegBlock{prefixTestBlock(0x30fe,0x11111111)},[]RegBlock{prefixTestBlock(0x3100,0),prefixTestBlock(0x30fe,0x12345678)},"",0x30fe,"78563412"},
        {"partial_prefix",8,35,nil,[]RegBlock{prefixTestBlock(0x30fd,0x12340000),prefixTestBlock(0x3100,0),prefixTestBlock(0x30ff,0x00005678)},"",0x30fe,"34127856"},
        {"trigger_inclusive",9,30,nil,[]RegBlock{prefixTestBlock(0x3100,0x40000000),prefixTestBlock(0x3101,0x00004040)},"00000040",0x3100,"00004040"},
    }{
        t.Run(tc.name,func(t *testing.T){
            m,c:=markFixture(t);defer m.CloseFiles()
            m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
            var ch [10]bool;ch[tc.tachChannel]=true
            var spec [43]bool
            var vals [73]bool;vals[tc.cell]=true
            sourceSelectedMark(t,c,m,1,"values_begin",ch,spec,vals)
            at:=time.Date(2026,11,24,4,0,0,0,time.UTC)
            if len(tc.seed)>0{
                if err:=m.ProcessChunk(makeParam(tc.seed),at);err!=nil{t.Fatal(err)}
            }
            if err:=m.ProcessChunk(makeParam(tc.blocks),at.Add(time.Second));err!=nil{t.Fatal(err)}
            final:=m.sourceLiveRawDWORD(tc.finalAddr)
            if final==nil || *final!=tc.final{t.Fatalf("final image not complete: %v",final)}
            if _,_,err:=m.Finalize("STOPPED_BY_USER");err!=nil{t.Fatal(err)}
            ev:=prefixTestEvent(t,m);field:=ev.RawTickEvidence.OrderedFields[0]
            if tc.want==""{
                if field.RawLE!=nil || field.SourceWordValid{t.Fatalf("later/stale/partial TACH accepted at trigger: %+v",field)}
            }else if field.RawLE==nil || *field.RawLE!=tc.want || !field.SourceWordValid{
                t.Fatalf("valid trigger-prefix value dropped: %+v",field)
            }
        })
    }
}

 
// Only the isolated offline cross-language CI opts in to this output.
// It exercises the actual writer/Finalize, not a Python-authored imitation.
func TestValuesTriggerPrefixCoreFixture(t *testing.T){
    root:=os.Getenv("MVK_PREFIX_FIXTURE_DIR")
    if root==""{t.Skip("cross-language fixture not requested")}
    run:=filepath.Join(root,"TEST_2026-11-24_04-00-00.000")
    m,err:=NewMonitor(run,"OFFLINE_REPLAY","192.0.2.84");if err!=nil{t.Fatal(err)}
    defer m.CloseFiles()
    c,err:=newFrameMarkController(root,run);if err!=nil{t.Fatal(err)}
    m.frameMarks=c
    m.sourceLiveValuesWriter=newSourceLiveValuesWriter(m.dir)
    var ch [10]bool;ch[0]=true;ch[8]=true
    var spec [43]bool;spec[0]=true
    var vals [73]bool;vals[0]=true;vals[6]=true;vals[35]=true
    sourceSelectedMark(t,c,m,1,"values_begin",ch,spec,vals)
    at:=time.Date(2026,11,24,4,0,0,0,time.UTC)
    seed:=makeParam([]RegBlock{
        prefixTestBlock(0x2002,0x3f800000),
        prefixTestBlock(0x2120,0x00000051),
        prefixTestBlock(0x2060,0x3fc00000),
        prefixTestBlock(0x30fe,0x11111111),
    })
    packet:=makeParam([]RegBlock{
        prefixTestBlock(0x2002,0x40000000),
        prefixTestBlock(0x3100,0x11223344),
        prefixTestBlock(0x2002,0x40400000),
        prefixTestBlock(0x30fe,0x12345678),
    })
    if err=m.ProcessChunk(seed,at);err!=nil{t.Fatal(err)}
    if err=m.ProcessChunk(packet,at.Add(time.Second));err!=nil{t.Fatal(err)}
    if _,_,err=m.Finalize("STOPPED_BY_USER");err!=nil{t.Fatal(err)}
}
