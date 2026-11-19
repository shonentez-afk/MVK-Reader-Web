package main

// One big original active Task2 acceptance pack. Synthetic PCAP-like
// payloads go ONLY into a local net.Pipe. No physical MVK01/industrial
// network, no private Pascal/DFM/SQLite/IDP contents and no service TX.
//
// Original PRIVATE triple-source pointers:
// Projects.7z/_Unit125.pas Execute 00807E8F..00807F6A
// and 00808581..00808762; mvkview.idp Stage+3C,
// CommandList+34 and StatusCells+4008C; mvk_idr(1).sqlite calls.
import (
    "bytes"
    "errors"
    "io"
    "net"
    "os"
    "path/filepath"
    "testing"
    "time"
)

func sourceDuplexFixture(t *testing.T)(*Monitor,net.Conn,net.Conn){
    t.Helper()
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"source_task2_packet_interleave"),
        "LIVE_SOURCE_SET_RATE_APPROVED","127.0.0.1")
    if e!=nil{t.Fatal(e)}
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceTask2TX=newSourceLiveTask2TX()
    m.sourceOriginalTask2Stage.onConnected(0)
    m.sourceTask2TX.resetForNewSourceSocket(m)
    client,device:=net.Pipe()
    m.sourceTask2TX.conn=client
    t.Cleanup(func(){_ = client.Close();_ = device.Close();_ = m.CloseFiles()})
    _=device.SetReadDeadline(time.Now().Add(5*time.Second))
    return m,client,device
}

// The old Native sent one command per OS c.Read, which is wrong when
// TCP combines a PARAM and several ADC packets. Original Indy receives
// one application packet at a time and sends FIFO BEFORE each next packet.
func TestSourceOriginalActiveTask2InterleavesAllCommandsWithinOneTCPChunk(t *testing.T){
    m,_,device:=sourceDuplexFixture(t)
    for _,rate:=range []uint32{32768,8192}{
        if e:=m.sourceTask2TX.queueRate(rate);e!=nil{t.Fatal(e)}
    }
    received:=make(chan [][]byte,1)
    readError:=make(chan error,1)
    go func(){
        commands:=make([][]byte,0,3)
        for i:=0;i<3;i++{
            item:=make([]byte,sourceSetRateWriteLen)
            if _,e:=io.ReadFull(device,item);e!=nil {readError<-e;return}
            commands=append(commands,item)
        }
        received<-commands
    }()
    first:=sourceStageTestParam(0x2200,5) // nonempty, NO Status0
    a:=sourceLiveWriterSample(typeADC,0,65536,0,0x3F800000)
    b:=sourceLiveWriterSample(typeADC,0,65536,1,0x40000000)
    c:=sourceLiveWriterSample(typeADC,0,65536,2,0x40400000)
    wire:=append(append(append(append([]byte{},first...),a...),b...),c...)
    if e:=m.ProcessChunk(wire,time.Now());e!=nil{t.Fatal(e)}
    select{
    case commands:=<-received:
        for i,rate:=range []uint32{65536,32768,8192}{
            expect,e:=sourceSetRateWireBytes(rate)
            if e!=nil || !bytes.Equal(commands[i],expect){
                t.Fatalf("FIFO command %d original SetRate(%d) mismatch: %v",i,rate,e)
            }
        }
    case e:=<-readError:t.Fatalf("local TCP writer: %v",e)
    case <-time.After(5*time.Second):t.Fatal("missing interpacket FIFO commands")
    }
    tx:=m.sourceTask2TX
    stage:=m.sourceOriginalTask2Stage
    if tx.sentCommands!=3 || tx.sentBytes!=108 || tx.sentInSocket!=3 ||
        len(tx.pending)!=0 || tx.status0Seen || tx.status0SocketMask!=0 ||
        tx.stage!=1 || !stage.connected || stage.stage!=1 ||
        stage.knownSystem0 || m.summary.SourceNonemptyParameters!=1 ||
        m.summary.TotalFrames!=4 || m.summary.RawBytes!=uint64(len(wire)) ||
        m.summary.Channels[0].Samples!=3 || m.summary.ReadOnly ||
        m.summary.InvalidFrames!=0 || m.captureOnly {
        t.Fatalf("coalesced original Task2 ordering/stage mismatch: tx=%+v stage=%+v summary=%+v",
            tx,stage,m.summary)
    }
}

// A new socket must not see an old status value merely because the
// cumulative forensic RegisterImage still contains those two words.
// PARAM may span separate 16-bit source register descriptors.
func TestSourceTask2ReconnectStatus0FreshWordsAndFreeze(t *testing.T){
    m,_,_:=sourceDuplexFixture(t)
    first:=task2Status0Param(42).Raw
    if e:=m.ProcessChunk(first,time.Now());e!=nil{t.Fatal(e)}
    if m.sourceOriginalTask2Stage.stage!=3 ||
        !m.sourceTask2TX.systemErrorLatched {t.Fatal("real Status0=42 must latch Stage3")}
    m.sourceOriginalTask2Stage.onDisconnected("REMOTE_DISCONNECTED")
    m.sourceOriginalTask2Stage.onConnected(m.summary.SourceNonemptyParameters)
    m.sourceTask2TX.resetForNewSourceSocket(m)
    // Previous socket's register image STILL holds 42.
    remembered,e:=m.image.Uint32(0x1006)
    if e!=nil || remembered!=42 {t.Fatal("forensic register image incorrectly reset")}
    if e=m.ProcessChunk(sourceStageTestParam(0x2200,0),time.Now());e!=nil {
        t.Fatal(e)
    }
    stage:=m.sourceOriginalTask2Stage
    tx:=m.sourceTask2TX
    if stage.stage!=1 || stage.knownSystem0 || stage.systemErrorLatched ||
        tx.stage!=1 || tx.status0Seen || tx.systemErrorLatched ||
        tx.status0SocketMask!=0 || stage.status0SocketMask!=0 {
        t.Fatalf("stale old socket Status0=42 leaked: tx=%+v stage=%+v",tx,stage)
    }
    // Freeze consumes PARAM bytes into RAW but NOT source status.
    m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
    m.sourceOriginalRXGate.setFreeze(true)
    if e=m.ProcessChunk(task2Status0Param(0).Raw,time.Now());e!=nil {
        t.Fatal(e)
    }
    if stage.knownSystem0 || tx.status0Seen || stage.stage!=1 {
        t.Fatal("frozen PARAM fabricated fresh Status0")
    }
    m.sourceOriginalRXGate.setFreeze(false)
    // Each descriptor has TWO 16-bit words, but only one belongs to
    // Status0. A first half alone MUST NOT reuse the old high half.
    low:=makeParam([]RegBlock{{Addr:0x1005,Words:2,
        Payload:[]byte{0x11,0x22,0x00,0x00}}})
    high:=makeParam([]RegBlock{{Addr:0x1007,Words:2,
        Payload:[]byte{0x00,0x00,0x33,0x44}}})
    if e=m.ProcessChunk(low,time.Now());e!=nil{t.Fatal(e)}
    if stage.knownSystem0 || tx.status0Seen ||
        stage.status0SocketMask!=1 || tx.status0SocketMask!=1 {
        t.Fatal("partial Status0 low word contaminated by prior socket")
    }
    if e=m.ProcessChunk(high,time.Now());e!=nil{t.Fatal(e)}
    if !stage.knownSystem0 || !tx.status0Seen ||
        stage.system0!=0 || tx.status0!=0 ||
        stage.status0SocketMask!=3 || tx.status0SocketMask!=3 {
        t.Fatalf("source split Status0=0 not reconstructed: tx=%+v stage=%+v",tx,stage)
    }
    if e=m.ProcessChunk(task2Status0Param(77).Raw,time.Now());e!=nil{t.Fatal(e)}
    if stage.stage!=3 || !stage.systemErrorLatched ||
        tx.stage!=3 || !tx.systemErrorLatched {
        t.Fatal("fresh system error not latched Stage3")
    }
}

// DENIED is a native Task2 control reply, NOT malformed ADC payload.
// A queued command must be sent at the application-packet boundary
// before this response is consumed, even if TCP merged both packets.
func TestSourceOriginalTask2CoalescedPARAMDENIEDSendsBeforeReplyAndKeepsRAW(t *testing.T){
    m,_,device:=sourceDuplexFixture(t)
    got:=make(chan []byte,1)
    ioErr:=make(chan error,1)
    go func(){
        buf:=make([]byte,sourceSetRateWriteLen)
        _,e:=io.ReadFull(device,buf)
        if e!=nil{ioErr<-e;return}
        got<-buf
    }()
    start:=sourceStageTestParam(0x2200,5)
    denied:=sourceStageTestReply(typeDenied)
    after:=sourceLiveWriterSample(typeADC,0,65536,0,0x3F800000)
    chunk:=append(append(append([]byte{},start...),denied...),after...)
    e:=m.ProcessChunk(chunk,time.Now())
    if !errors.Is(e,errTask2SourceDenied){
        t.Fatalf("source denied in same TCP chunk not signaled: %v",e)
    }
    select{
    case wire:=<-got:
        expect,_:=sourceSetRateWireBytes(65536)
        if !bytes.Equal(wire,expect){t.Fatal("source SetRate sent wrong bytes")}
    case e:=<-ioErr:t.Fatal(e)
    case <-time.After(5*time.Second):t.Fatal("source FIFO not sent before DENIED")
    }
    if m.summary.Denials!=1 || m.summary.TotalFrames!=2 ||
        m.summary.Channels[0].Samples!=0 || m.summary.InvalidFrames!=0 ||
        m.captureOnly || m.sourceTask2TX.sentInSocket!=1 ||
        m.sourceTask2TX.deniedAfterTX!=1 ||
        m.summary.RawBytes!=uint64(len(chunk)) {
        t.Fatal("wrong DENIED/early stop/RAW result")
    }
    if e:=m.CloseFiles();e!=nil{t.Fatal(e)}
    raw,e:=os.ReadFile(filepath.Join(m.dir,"incoming.raw"))
    if e!=nil || !bytes.Equal(raw,chunk){
        t.Fatal("forensic TCP RAW is not byte-exact after early DENIED")
    }
}


func TestSourceTask2PartialNonzeroStatusWordBlocksRealCommand(t *testing.T){
    // Original 00805D08 loads the complete StatusCells dword on an
    // overlapping PARAM address. A NEW nonzero half is conclusive
    // evidence of error; it must latch Stage3 before next packet TX.
    for _,tc:=range []struct{addr uint16;value []byte}{
        {0x1005,[]byte{0,0,0x2A,0}}, // low 16-bit system status nonzero
        {0x1007,[]byte{0x01,0,0,0}}, // high 16-bit system status nonzero
    }{
        m,_,_:=sourceDuplexFixture(t)
        partial:=makeParam([]RegBlock{{
            Addr:tc.addr,Words:2,Payload:tc.value,
        }})
        sample:=sourceLiveWriterSample(typeADC,0,65536,0,0x3F800000)
        joined:=append(append([]byte{},partial...),sample...)
        if e:=m.ProcessChunk(joined,time.Now());e!=nil{t.Fatal(e)}
        if m.sourceOriginalTask2Stage.stage!=3 ||
            !m.sourceOriginalTask2Stage.systemErrorLatched ||
            m.sourceTask2TX.stage!=3 || !m.sourceTask2TX.systemErrorLatched ||
            m.sourceTask2TX.sentBytes!=0 ||
            m.sourceTask2TX.sentCommands!=0 ||
            len(m.sourceTask2TX.pending)!=1 ||
            m.sourceOriginalTask2Stage.receipt().UnobservedFFSentinelRisk ||
            m.summary.TotalFrames!=2 || m.summary.InvalidFrames!=0 {
            t.Fatalf("partial source System0 error lost on addr=%X",tc.addr)
        }
    }
}

func TestSourceTask2DuplicateStatusDescriptorFinalValueWins(t *testing.T){
    // Same PARAM can contain duplicate overlapping register records.
    // Delphi applies each in order, then tests final StatusCells0.
    for _,tc:=range []struct{first,second uint32;fault bool}{
        {42,0,false},{0,42,true},
    }{
        m,_,_:=sourceDuplexFixture(t)
        word:=func(v uint32)[]byte{
            return []byte{byte(v),byte(v>>8),byte(v>>16),byte(v>>24)}
        }
        frame:=makeParam([]RegBlock{
            {Addr:0x1006,Words:2,Payload:word(tc.first)},
            {Addr:0x1006,Words:2,Payload:word(tc.second)},
        })
        if e:=m.ProcessChunk(frame,time.Now());e!=nil{t.Fatal(e)}
        wantStage:=uint32(1)
        if tc.fault{wantStage=3}
        if m.sourceOriginalTask2Stage.systemErrorLatched!=tc.fault ||
           m.sourceTask2TX.systemErrorLatched!=tc.fault ||
           m.sourceOriginalTask2Stage.stage!=wantStage ||
           m.sourceTask2TX.stage!=int(wantStage) ||
           m.sourceTask2TX.status0!=tc.second {
           t.Fatal("source Stage3 after duplicate descriptors differs from final register value")
        }
    }
}
