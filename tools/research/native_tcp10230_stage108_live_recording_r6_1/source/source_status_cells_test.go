package main

// Stage111Z31DI: Exact original 14 source StatusCells from passive
// already-decoded RegisterImage. No device connection, writes, or polling.
import (
    "encoding/binary"
    "path/filepath"
    "testing"
    "time"
)

func TestSourceStatusCellsUnknownUntilBOTHRegisterWordsArrive(t *testing.T) {
    m,err:=NewMonitor(filepath.Join(t.TempDir(),"TEST_cells"),"OFFLINE_REPLAY","")
    if err!=nil {t.Fatal(err)}
    defer m.CloseFiles()
    before:=m.snapshotLiveStatus("CONNECTING",time.Now())
    if len(before.SourceStatusCells)!=14 || !before.ReadOnly {
        t.Fatalf("missing 14 source cells: %+v",before)
    }
    for i,item:=range before.SourceStatusCells {
        if item.Index!=i || item.Address!=sourceStatusCellAddresses[i] ||
            item.Valid || item.Value!=nil {
            t.Fatalf("invented source register: %+v",item)
        }
    }
    // First valid 16-bit word (0x1006) alone is NOT a DWORD.
    first:=makeParam([]RegBlock{{Addr:0x1005,Words:2,
        Payload:[]byte{0,0,1,0}}})
    if err:=m.ProcessChunk(first,time.Now());err!=nil{t.Fatal(err)}
    half:=m.snapshotLiveStatus("RECORDING",time.Now()).SourceStatusCells
    if half[0].Valid || half[0].Value!=nil {
        t.Fatal("missing upper word incorrectly treated as a 32-bit status")
    }
    // Independent adjacent block now supplies the upper 16 bits.
    second:=makeParam([]RegBlock{{Addr:0x1007,Words:2,
        Payload:[]byte{0,0,0,0}}})
    if err:=m.ProcessChunk(second,time.Now());err!=nil{t.Fatal(err)}
    complete:=m.snapshotLiveStatus("RECORDING",time.Now()).SourceStatusCells
    if !complete[0].Valid || complete[0].Value==nil ||
       *complete[0].Value!=1 {
        t.Fatalf("expected source System StatusCells[0]=1, got %+v",complete[0])
    }
    for _,item:=range complete[1:] {
        if item.Valid || item.Value!=nil {
            t.Fatalf("fabricated absent register: %+v",item)
        }
    }
    if m.summary.TotalFrames!=2 || m.summary.SourceNonemptyParameters!=2 ||
       !m.summary.ReadOnly {
        t.Fatalf("source input/identity mutated: %+v",m.summary)
    }
}

func TestSourceStatusCells14ExactAddressesDistinctRawValuesAndZero(t *testing.T) {
    m,err:=NewMonitor(filepath.Join(t.TempDir(),"TEST_full_cells"),"OFFLINE_REPLAY","")
    if err!=nil{t.Fatal(err)}
    defer m.CloseFiles()
    for i,addr:=range sourceStatusCellAddresses {
        bits:=uint32(i+11)
        if i==0 {bits=0} // explicit known zero is NOT unknown
        if i==13 {bits=0xffffffff} // actual FF bytes must keep Valid=true
        payload:=make([]byte,4)
        binary.LittleEndian.PutUint32(payload,bits)
        if err:=m.ProcessChunk(makeParam([]RegBlock{{
            Addr:addr,Words:2,Payload:payload}}),time.Now());err!=nil {
            t.Fatal(err)
        }
    }
    receipt:=m.snapshotLiveStatus("RECORDING",time.Now())
    if len(receipt.SourceStatusCells)!=14 ||
       receipt.TotalFrames!=14 || !receipt.ReadOnly {
        t.Fatalf("wrong source input proof: %+v",receipt)
    }
    for i,cell:=range receipt.SourceStatusCells {
        value:=uint32(i+11)
        if i==0 {value=0}
        if i==13 {value=0xffffffff}
        if cell.Index!=i || cell.Address!=sourceStatusCellAddresses[i] ||
           !cell.Valid || cell.Value==nil || *cell.Value!=value {
            t.Fatalf("source register %d unexpected: %+v",i,cell)
        }
    }
    if m.summary.InvalidFrames!=0 || m.summary.ACK!=0 ||
       m.summary.Denials!=0 {
        t.Fatalf("source status read generated a device error: %+v",m.summary)
    }
}

func TestSourceStatusCellUpdatedByOneFullRegisterSnapshot(t *testing.T) {
    m,err:=NewMonitor(filepath.Join(t.TempDir(),"TEST_full_image"),"OFFLINE_REPLAY","")
    if err!=nil{t.Fatal(err)}
    defer m.CloseFiles()
    payload:=make([]byte,registerWords*2)
    binary.LittleEndian.PutUint32(payload[0x1006*2:],0x81)
    binary.LittleEndian.PutUint32(payload[0x3104*2:],0x22011)
    if err:=m.ProcessChunk(makeParam([]RegBlock{{
        Addr:0,Words:registerWords,Payload:payload,
    }}),time.Now());err!=nil {t.Fatal(err)}
    receipt:=m.snapshotLiveStatus("RECORDING",time.Now())
    if !receipt.SourceStatusCells[0].Valid ||
        *receipt.SourceStatusCells[0].Value!=0x81 ||
        !receipt.SourceStatusCells[13].Valid ||
        *receipt.SourceStatusCells[13].Value!=0x22011 ||
        receipt.SourceRXNonemptyParam!=1 ||
        receipt.FullSnapshots!=1 {
        t.Fatalf("full original status image wrong: %+v",receipt)
    }
}
