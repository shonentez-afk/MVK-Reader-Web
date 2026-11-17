package main

import (
    "bytes"
    "encoding/binary"
    "encoding/json"
    "io"
    "net/http"
    "os"
    "path/filepath"
    "strconv"
    "strings"
    "sync"
    "testing"
)

func ipcSourceFrame(index uint32) []byte {
    out:=make([]byte,1024)
    for i:=0;i<256;i++ {
        binary.LittleEndian.PutUint32(out[4*i:],index+uint32(i))
    }
    return out
}

func TestLocalIPCSafeCalibratedADCAndAuthorization(t *testing.T) {
    ring:=newSourceOriginalStorageRing()
    run:=filepath.Join(t.TempDir(),"TEST_2026-11-17_00-00-00.000")
    if e:=os.Mkdir(run,0700);e!=nil {t.Fatal(e)}
    ipc,e:=startLiveIPC(run,ring)
    if e!=nil {t.Fatal(e)}
    defer ipc.Close()
    descriptor,e:=os.ReadFile(filepath.Join(run,liveIPCName))
    if e!=nil {t.Fatal(e)}
    var doc map[string]interface{}
    if e=json.Unmarshal(descriptor,&doc);e!=nil {t.Fatal(e)}
    if doc["schema"]!=liveIPCSchema || doc["read_only"]!=true ||
       doc["host"]!="127.0.0.1" || doc["token"]!=ipc.token {
        t.Fatal("unexpected authenticated descriptor")
    }
    addr:="http://127.0.0.1:"+strconv.Itoa(ipc.port)+"/v1/adc/1/window?count=256"
    // Refuse samples until initial calibration has actually been accepted.
    ring.appendFrame(SampleHeader{Channel:0,Rate:65536,Index:7,Samples:256},
        ipcSourceFrame(10),sourceStorageUnscaledADC)
    req,_:=http.NewRequest("GET",addr,nil)
    req.Header.Set("Authorization","Bearer "+ipc.token)
    c:=&http.Client{}
    rsp,e:=c.Do(req)
    if e!=nil {t.Fatal(e)}
    rsp.Body.Close()
    if rsp.StatusCode!=409 {t.Fatalf("uncalibrated IPC should be 409, got %d",rsp.StatusCode)}
    // The source rate/domain changes and the latest 256 calibrated samples
    // start a new valid epoch. No fake FRange or previous RAW bytes.
    expected:=ipcSourceFrame(300)
    if e=ring.appendFrame(SampleHeader{Channel:0,Rate:65536,Index:263,Samples:256},
        expected,sourceStorageCalibratedADC);e!=nil {t.Fatal(e)}
    rsp,e=c.Do(req)
    if e!=nil {t.Fatal(e)}
    data,e:=io.ReadAll(rsp.Body)
    rsp.Body.Close()
    if e!=nil || rsp.StatusCode!=200 || !bytes.Equal(data,expected) {
        t.Fatalf("IPC byte-exact calibrated window failure: status %d err %v",rsp.StatusCode,e)
    }
    if rsp.Header.Get("X-MVK-Session")!=filepath.Base(run) ||
       rsp.Header.Get("X-MVK-Domain")!=sourceStorageCalibratedADC ||
       rsp.Header.Get("X-MVK-Rxpos")!="512" ||
       rsp.Header.Get("X-MVK-Rate")!="65536" ||
       rsp.Header.Get("X-MVK-Nextindex")!="519" {
        t.Fatalf("metadata not coherent with actual ring: %+v",rsp.Header)
    }
    // Bearer token, browser origin, bad method and oversized windows.
    noAuth,_:=http.NewRequest("GET",addr,nil)
    rsp,e=c.Do(noAuth)
    if e!=nil {t.Fatal(e)}
    rsp.Body.Close()
    if rsp.StatusCode!=401 {t.Fatal("missing token accepted")}
    withOrigin,_:=http.NewRequest("GET",addr,nil)
    withOrigin.Header.Set("Authorization","Bearer "+ipc.token)
    withOrigin.Header.Set("Origin","https://attacker.test")
    rsp,e=c.Do(withOrigin)
    if e!=nil {t.Fatal(e)}
    rsp.Body.Close()
    if rsp.StatusCode!=403 {t.Fatal("cross-origin request accepted")}
    bigReq,_:=http.NewRequest("GET",strings.Replace(addr,"count=256","count=999999",1),nil)
    bigReq.Header.Set("Authorization","Bearer "+ipc.token)
    rsp,e=c.Do(bigReq)
    if e!=nil {t.Fatal(e)}
    rsp.Body.Close()
    if rsp.StatusCode!=400 {t.Fatal("oversize request accepted")}
    badMethod,_:=http.NewRequest("POST",addr,nil)
    badMethod.Header.Set("Authorization","Bearer "+ipc.token)
    rsp,e=c.Do(badMethod)
    if e!=nil {t.Fatal(e)}
    rsp.Body.Close()
    if rsp.StatusCode!=403 {t.Fatal("device-command method accepted")}
    if e=ipc.Close();e!=nil {t.Fatal(e)}
    if _,e=os.Stat(filepath.Join(run,liveIPCName));!os.IsNotExist(e){
        t.Fatal("stale descriptor left after local IPC close",e)
    }
}

func TestIPCSnapshotConcurrentWithNativeRingWriter(t *testing.T) {
    r:=newSourceOriginalStorageRing()
    var wg sync.WaitGroup
    errs:=make(chan error,256)
    wg.Add(2)
    go func(){
        defer wg.Done()
        for i:=0;i<1000;i++ {
            h:=SampleHeader{Channel:2,Index:uint32(i*256),Rate:65536,Samples:256}
            if e:=r.appendFrame(h,ipcSourceFrame(uint32(i*256)),sourceStorageCalibratedADC);e!=nil {
                errs<-e;return
            }
        }
    }()
    go func(){
        defer wg.Done()
        for i:=0;i<1000;i++ {
            bytes,meta,e:=r.snapshotCalibratedADC(2,256)
            if e!=nil {continue} // first packet may not exist yet
            if len(bytes)!=1024 || meta.NextDeviceIndex==nil ||
               meta.RxPos==0 || meta.RxPos%256!=0 || meta.Domain!=sourceStorageCalibratedADC {
                errs<-io.ErrUnexpectedEOF;return
            }
        }
    }()
    wg.Wait()
    close(errs)
    for e:=range errs {t.Fatal(e)}
    last,meta,e:=r.snapshotCalibratedADC(2,256)
    if e!=nil || len(last)!=1024 || meta.RxPos!=256000 {
        t.Fatal("concurrent final snapshot corrupted",e,meta)
    }
}
