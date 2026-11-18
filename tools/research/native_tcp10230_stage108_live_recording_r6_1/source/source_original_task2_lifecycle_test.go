package main

import (
    "encoding/binary"
    "errors"
    "path/filepath"
    "testing"
    "time"
)
func sourceStageTestParam(addr uint16,value uint32) []byte {
    payload:=make([]byte,4)
    binary.LittleEndian.PutUint32(payload,value)
    return makeParam([]RegBlock{{Addr:addr,Words:2,Payload:payload}})
}
func sourceStageTestReply(typ uint32) []byte {
    raw:=make([]byte,8)
    binary.LittleEndian.PutUint32(raw[:4],typ)
    binary.LittleEndian.PutUint32(raw[4:8],8)
    return raw
}
func TestOriginalTask2SourceStagesZeroOneThreeNeverTwo(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_task2_original_stage"),
        "LIVE_READ_ONLY","127.0.0.1")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    s:=m.sourceOriginalTask2Stage
    if s.receipt().Connected || s.receipt().Stage!=0 {
        t.Fatal("original Task2 started connected without real TCP")
    }
    s.onConnected(m.summary.SourceNonemptyParameters)
    if s.stage!=0 {t.Fatal("Stage0 must remain until real PARAM")}
    if e:=m.ProcessChunk(sourceStageTestParam(0x2200,0),time.Now());e!=nil {t.Fatal(e)}
    if s.stage!=1 || s.knownSystem0 ||
       !s.receipt().UnobservedFFSentinelRisk {
        t.Fatalf("partial PARAM must enter Stage1 with unknown system0: %+v",s.receipt())
    }
    if e:=m.ProcessChunk(sourceStageTestReply(typeAck),time.Now());e!=nil {t.Fatal(e)}
    if s.stage!=1 || s.ackObserved!=1 {
        t.Fatal("unmatched ACK cannot advance original Task2 Stage")
    }
    if e:=m.ProcessChunk(sourceStageTestParam(0x1006,42),time.Now());e!=nil {t.Fatal(e)}
    if s.stage!=3 || !s.systemErrorLatched ||
       !s.knownSystem0 || s.system0!=42 {
        t.Fatalf("measured system fault must latch Stage3: %+v",s.receipt())
    }
    if e:=m.ProcessChunk(sourceStageTestParam(0x1006,0),time.Now());e!=nil {t.Fatal(e)}
    if s.stage!=3 || !s.systemErrorLatched {
        t.Fatal("system error was accidentally cleared by later healthy PARAM")
    }
    p:=m.snapshotLiveStatus("RECORDING",time.Now()).SourceOriginalTask2Stage
    if p==nil || p.Stage!=3 || p.UnobservedFFSentinelRisk ||
       p.Status0Uint32==nil || *p.Status0Uint32!=0 ||
       p.OriginalDelphiThreadParityVerified || p.DeviceCommandSentByLifecycle {
        t.Fatalf("source live Stage receipt inconsistent: %+v",p)
    }
    s.onDisconnected("SOURCE_READ_TIMEOUT")
    if s.stage!=0 || s.lastLiveStage!=3 ||
       !s.disconnected || s.connected || s.endReason!="SOURCE_READ_TIMEOUT" {
        t.Fatal("source Task2 socket exit did not reset Stage0")
    }
    // Reconnecting to a new socket does NOT reuse stale Stage1 or FF data.
    s.onConnected(m.summary.SourceNonemptyParameters)
    if s.stage!=0 || s.knownSystem0 || s.systemErrorLatched ||
       s.paramsAfterConnect!=0 || s.attempts!=2 {
        t.Fatalf("source Task2 prior socket state leaked: %+v",s.receipt())
    }
    if s.receipt().Stage==2 {t.Fatal("Stage2 belongs to other Tasks, not Task2")}
}
func TestOriginalTask2PassiveDeniedStopsAfterPreservingExactRAW(t *testing.T) {
    m,e:=NewMonitor(filepath.Join(t.TempDir(),"TEST_source_denied"),
        "LIVE_READ_ONLY","127.0.0.1")
    if e!=nil {t.Fatal(e)}
    defer m.CloseFiles()
    m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
    m.sourceOriginalTask2Stage.onConnected(0)
    if e:=m.ProcessChunk(sourceStageTestParam(0x1006,0),time.Now());e!=nil {t.Fatal(e)}
    if m.sourceOriginalTask2Stage.stage!=1 {t.Fatal("first PARAM did not start Task2")}
    reply:=sourceStageTestReply(typeDenied)
    before:=m.summary.RawBytes
    e=m.ProcessChunk(reply,time.Now())
    if !errors.Is(e,errTask2SourceDenied) {
        t.Fatalf("passive source DENIED must end Task2: %v",e)
    }
    if m.summary.InvalidFrames!=0 || m.captureOnly ||
       m.summary.Denials!=1 || m.sourceOriginalTask2Stage.denialObserved!=1 ||
       m.summary.RawBytes!=before+uint64(len(reply)) ||
       !m.summary.ReadOnly {
        t.Fatal("source DENIED converted to bad frame, lost RAW or sent device command")
    }
    m.sourceOriginalTask2Stage.onDisconnected("SOURCE_OPERATION_DENIED")
    p:=m.sourceOriginalTask2Stage.receipt()
    if p.Stage!=0 || p.LastLiveStage!=1 ||
       p.LastEndReason!="SOURCE_OPERATION_DENIED" || !p.Disconnected {
       t.Fatalf("original denied/Stage0 unwind incorrect: %+v",p)
    }
}
