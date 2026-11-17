package main
import (
    "bytes"
    "encoding/binary"
    "errors"
    "io"
    "net"
    "testing"
)

func labStatus0(value uint32) []byte {
    data:=make([]byte,4)
    binary.LittleEndian.PutUint32(data,value)
    return makeParam([]RegBlock{{Addr:0x1006,Words:2,Payload:data}})
}
func TestSourceOriginalSetRateNineLittleEndianWrites(t *testing.T){
    for _,rate:=range []uint32{65536,32768,8192,2048,512} {
        got,e:=sourceSetRateWireBytes(rate)
        if e!=nil||len(got)!=36{t.Fatalf("rate=%d bytes=%d e=%v",rate,len(got),e)}
        words:=[]uint32{typeParam,36,0,0,0,0,1,0x0002000E,rate}
        for i,w:=range words{
            if binary.LittleEndian.Uint32(got[i*4:])!=w{t.Fatalf("source word[%d] rate=%d",i,rate)}
        }
    }
    if _,e:=sourceSetRateWireBytes(309);e==nil{
        t.Fatal("0x309 is only the Delphi constructor sentinel, not an admissible Hz rate")
    }
}
func TestSourceTask2LabOnlySendsAfterNonemptyParam(t *testing.T){
    lab,e:=newSourceTask2DuplexLab(65536)
    if e!=nil{t.Fatal(e)}
    out:=&bytes.Buffer{}
    n,e:=lab.writeOneBeforeRead(out)
    if n!=0||e!=nil||out.Len()!=0{t.Fatal("cannot send before Stage1")}
    if e=lab.observeFrame(Frame{Type:typeAck,Raw:sourceReply(typeAck)});e!=nil{t.Fatal(e)}
    if lab.inboundACK!=1||lab.stage!=0{t.Fatal("early ACK is unattributed")}
    if e=lab.observeFrame(Frame{Type:typeParam,Raw:labStatus0(0)});e!=nil{t.Fatal(e)}
    if lab.stage!=1 {t.Fatal("valid nonempty PARAM did not enter Stage1")}
    n,e=lab.writeOneBeforeRead(out)
    if e!=nil||n!=36||lab.sentWrites!=1||out.Len()!=36{
        t.Fatalf("expected only one source command: n=%d e=%v",n,e)
    }
    if n,e=lab.writeOneBeforeRead(out);e!=nil||n!=0||out.Len()!=36{t.Fatal("FIFO duplicated")}
    if e=lab.observeFrame(Frame{Type:typeAck,Raw:sourceReply(typeAck)});e!=nil||lab.inboundACK!=2{
        t.Fatal("original ACK does not positively correlate SetRate")
    }
}
func TestSourceTask2LabSystemErrorPreventsWritesAndDeniedStops(t *testing.T){
    l,_:=newSourceTask2DuplexLab(65536)
    if e:=l.observeFrame(Frame{Type:typeParam,Raw:labStatus0(7)});e!=nil{t.Fatal(e)}
    if l.stage!=3{t.Fatal("source system error must latch Stage3")}
    n,e:=l.writeOneBeforeRead(&bytes.Buffer{})
    if n!=0||e!=nil||l.sentWrites!=0{t.Fatal("Stage3 must not dispatch")}
    l2,_:=newSourceTask2DuplexLab(65536)
    if e:=l2.observeFrame(Frame{Type:typeDenied,Raw:sourceReply(typeDenied)});e!=nil{t.Fatal(e)}
    if !l2.closed||l2.inboundDENIED!=1{t.Fatal("original DENIED closes attempt")}
    n,e=l2.writeOneBeforeRead(&bytes.Buffer{})
    if n!=0||e!=nil{t.Fatal("DENIED cannot send")}
}
func TestSourceTask2LabWritesOverInProcessNetPipeOnly(t *testing.T){
    // Exercise a REAL io.Writer and real stream read, never a network NIC.
    client,server:=net.Pipe()
    defer client.Close();defer server.Close()
    source,_:=newSourceTask2DuplexLab(65536)
    if e:=source.observeFrame(Frame{Type:typeParam,Raw:labStatus0(0)});e!=nil {t.Fatal(e)}
    received:=make(chan []byte,1)
    errs:=make(chan error,1)
    go func(){
        buf:=make([]byte,36)
        _,e:=io.ReadFull(server,buf)
        if e!=nil {errs<-e;return}
        received<-buf
    }()
    n,e:=source.writeOneBeforeRead(client)
    if e!=nil||n!=36{t.Fatalf("lab write=%d: %v",n,e)}
    select{
    case actual:=<-received:
        expected,_:=sourceSetRateWireBytes(65536)
        if !bytes.Equal(actual,expected){t.Fatal("lab stream was not byte-exact")}
    case e:=<-errs:t.Fatal(e)
    }
}
func TestSourceMode2GoReadOnlyReceiptNeverClaimsTransmittedCommands(t *testing.T){
    m:=&Monitor{}
    initial:=m.snapshotOriginalTask2TxEvidence()
    if initial.Stage1FromParam||initial.ValidatedSourceCandidate||initial.ActualGoAppBytesSent!=0||
       initial.NoPhysicalCommandClaim{t.Fatal("false initial command claim")}
    m.summary.SourceNonemptyParameters=1
    m.image.Valid[0x1006]=true
    if m.snapshotOriginalTask2TxEvidence().ValidatedSourceCandidate{t.Fatal("incomplete status0")}
    m.image.Valid[0x1007]=true
    ready:=m.snapshotOriginalTask2TxEvidence()
    if !ready.Stage1FromParam||!ready.Status0ValidZero||!ready.ValidatedSourceCandidate||
       ready.ActualGoAppBytesSent!=0{t.Fatal("source candidate must remain passive")}
    m.captureOnly=true
    if m.snapshotOriginalTask2TxEvidence().ValidatedSourceCandidate{t.Fatal("corrupt capture cannot claim ready")}
    // Deliberately the lab's real writer is NOT installed on main.go.
    _=errors.New
}
