package main

// MVK Live local-only, authenticated, read-only IPC. The SAME Native Go
// receiver retains the only TCP/10230 connection. An HTTP loopback socket
// is strictly for a local viewer; it NEVER addresses the instrument.
//
// All reads copy bounded calibrated Float32 bytes out of the existing source
// ring. A short RWLock preserves a coherent source position, sample rate,
// SHA256, sample indices and bytes without racing the receive goroutine.
import (
    "context"
    "crypto/rand"
    "crypto/sha256"
    "crypto/subtle"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "net"
    "net/http"
    "os"
    "path/filepath"
    "strconv"
    "strings"
    "time"
)

const liveIPCName = "MVK_NATIVE_LIVE_IPC.json"
const liveIPCSchema = "MVK_NATIVE_CALIBRATED_IPC_V1"

type liveIPCEndpoint struct {
    server *http.Server
    listener net.Listener
    path string
    session string
    token string
    port int
}

func startLiveIPC(runDir string, ring *sourceOriginalStorageRing) (*liveIPCEndpoint,error) {
    if ring==nil {return nil,errors.New("source ring unavailable")}
    secret:=make([]byte,32)
    if _,err:=rand.Read(secret);err!=nil{return nil,err}
    listener,err:=net.Listen("tcp4","127.0.0.1:0")
    if err!=nil{return nil,err}
    ep:=&liveIPCEndpoint{
        listener:listener, session:filepath.Base(runDir),
        token:hex.EncodeToString(secret),
        port:listener.Addr().(*net.TCPAddr).Port,
        path:filepath.Join(runDir,liveIPCName),
    }
    handler:=http.HandlerFunc(func(w http.ResponseWriter,req *http.Request) {
        w.Header().Set("Cache-Control","no-store")
        w.Header().Set("X-Content-Type-Options","nosniff")
        // Never be available to arbitrary browser origins or remote clients.
        ip,_,e:=net.SplitHostPort(req.RemoteAddr)
        host,_,hostErr:=net.SplitHostPort(req.Host)
        if e!=nil || net.ParseIP(ip)==nil || !net.ParseIP(ip).IsLoopback() ||
           hostErr!=nil || host!="127.0.0.1" ||
           req.Header.Get("Origin")!="" || req.Method!="GET" ||
           req.ContentLength>0 {
            http.Error(w,"local read-only request refused",http.StatusForbidden)
            return
        }
        supplied:=strings.TrimPrefix(req.Header.Get("Authorization"),"Bearer ")
        if len(supplied)!=len(ep.token) ||
           subtle.ConstantTimeCompare([]byte(supplied),[]byte(ep.token))!=1 {
            http.Error(w,"not authorized",http.StatusUnauthorized)
            return
        }
        path:=strings.TrimPrefix(req.URL.Path,"/v1/adc/")
        if !strings.HasPrefix(req.URL.Path,"/v1/adc/") ||
           !strings.HasSuffix(path,"/window") {
            http.NotFound(w,req)
            return
        }
        numberText:=strings.TrimSuffix(path,"/window")
        ch,e:=strconv.Atoi(numberText)
        if e!=nil || ch<1 || ch>8 || strconv.Itoa(ch)!=numberText {
            http.Error(w,"bad ADC",http.StatusBadRequest)
            return
        }
        queries:=req.URL.Query()
        if len(queries)!=1 || len(queries["count"])!=1 {
            http.Error(w,"one count required",http.StatusBadRequest)
            return
        }
        count,e:=strconv.ParseUint(queries.Get("count"),10,32)
        if e!=nil || count<1 || count>262144 {
            http.Error(w,"bounded window 1..262144 required",http.StatusBadRequest)
            return
        }
        data,meta,e:=ring.snapshotCalibratedADC(ch-1,count)
        if e!=nil {
            // A source gap, missing initial calibration or insufficient
            // samples is NOT a zero-padded or silently scaled preview.
            http.Error(w,"verified ADC window unavailable",http.StatusConflict)
            return
        }
        digest:=sha256.Sum256(data)
        w.Header().Set("Content-Type","application/octet-stream")
        w.Header().Set("X-MVK-Schema",liveIPCSchema)
        w.Header().Set("X-MVK-Session",ep.session)
        w.Header().Set("X-MVK-ADC",strconv.Itoa(ch))
        w.Header().Set("X-MVK-Count",strconv.FormatUint(count,10))
        w.Header().Set("X-MVK-RxPos",strconv.FormatUint(meta.RxPos,10))
        w.Header().Set("X-MVK-Rate",strconv.FormatUint(uint64(meta.SampleRate),10))
        w.Header().Set("X-MVK-NextIndex",strconv.FormatUint(uint64(*meta.NextDeviceIndex),10))
        w.Header().Set("X-MVK-Available",strconv.FormatUint(meta.Available,10))
        w.Header().Set("X-MVK-FirstReadable",strconv.FormatUint(meta.FirstReadable,10))
        w.Header().Set("X-MVK-Domain",meta.Domain)
        w.Header().Set("X-MVK-SHA256",hex.EncodeToString(digest[:]))
        w.Header().Set("Content-Length",strconv.Itoa(len(data)))
        _,_ = w.Write(data)
    })
    ep.server=&http.Server{
        Handler:handler, ReadHeaderTimeout:time.Second,
        ReadTimeout:2*time.Second, WriteTimeout:2*time.Second,
        IdleTimeout:2*time.Second, MaxHeaderBytes:8192,
    }
    descriptor:=map[string]interface{}{
        "schema":liveIPCSchema,"session_id":ep.session,
        "host":"127.0.0.1","port":ep.port,
        "token":ep.token,"read_only":true,
        "source_domain":sourceStorageCalibratedADC,
        "max_window_samples":262144,
    }
    content,e:=json.Marshal(descriptor)
    if e!=nil {listener.Close();return nil,e}
    tmp,e:=os.CreateTemp(runDir,".mvk_ipc_pending_")
    if e!=nil {listener.Close();return nil,e}
    defer os.Remove(tmp.Name())
    if e=tmp.Chmod(0600);e==nil {_,e=tmp.Write(content)}
    if e==nil {e=tmp.Close()} else {_=tmp.Close()}
    if e==nil {e=os.Rename(tmp.Name(),ep.path)}
    if e!=nil {listener.Close();return nil,fmt.Errorf("publish local IPC descriptor: %w",e)}
    go func(){_ = ep.server.Serve(listener)}()
    return ep,nil
}

func (e *liveIPCEndpoint) Close() error {
    if e==nil {return nil}
    // Close local viewer access BEFORE original RAW export/finalization.
    ctx,cancel:=context.WithTimeout(context.Background(),time.Second)
    defer cancel()
    err:=e.server.Shutdown(ctx)
    _=e.listener.Close()
    _=os.Remove(e.path)
    return err
}
