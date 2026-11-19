package main

// Source-backed original Task=2 RX lifecycle; not a physical Delphi thread.
// Joint private evidence: mvkview.idp + Projects.7z _Unit125.pas +
// mvk_idr(1).sqlite. Execute=00807A98; Stage0 at 00807BE3;
// Stage1 at 00808617 on a PARAM; Stage3 at 00808762 for Status0>0;
// DENIED raises errOperationDenied at 008080C5 even in passive Task2;
// Stage0 reset on socket exit at 008089BF. Task2 never uses Stage2.
const sourceOriginalTask2LifecycleSchema="MVK_SOURCE_TASK2_STAGE_LIFECYCLE_V1"

type sourceOriginalTask2Lifecycle struct {
    connected bool
    stage uint32
    lastLiveStage uint32
    attempts uint64
    firstParamBase uint64
    paramsAfterConnect uint64
    knownSystem0 bool
    system0 uint32
    status0SocketMask uint8 // track only new-socket 16-bit words
    systemErrorLatched bool
    ackObserved uint64
    denialObserved uint64
    disconnected bool
    endReason string
}
type sourceOriginalTask2LifecycleReceipt struct {
    Schema string `json:"schema"`
    Task uint32 `json:"task"`
    Stage uint32 `json:"source_stage"`
    LastLiveStage uint32 `json:"last_live_stage"`
    Connected bool `json:"socket_connected"`
    Attempts uint64 `json:"source_socket_attempts"`
    NonemptyParamSinceConnect uint64 `json:"nonempty_param_since_connect"`
    Status0RegisterValid bool `json:"source_system_status0_valid"`
    Status0Uint32 *uint32 `json:"source_system_status0_uint32"`
    UnobservedFFSentinelRisk bool `json:"original_unobserved_ff_sentinel_risk"`
    SystemErrorLatched bool `json:"system_error_latched"`
    AckObserved uint64 `json:"observed_ack_frames"`
    DenialObserved uint64 `json:"observed_denied_frames"`
    Disconnected bool `json:"disconnected"`
    LastEndReason string `json:"last_end_reason"`
    OriginalDelphiThreadParityVerified bool `json:"original_delphi_thread_parity_verified"`
    DeviceCommandSentByLifecycle bool `json:"device_command_sent_by_lifecycle"`
}
func newSourceOriginalTask2Lifecycle() *sourceOriginalTask2Lifecycle {
    return &sourceOriginalTask2Lifecycle{}
}
func (s *sourceOriginalTask2Lifecycle) onConnected(nonempty uint64) {
    if s==nil{return}
    s.connected=true;s.disconnected=false
    s.stage=0;s.lastLiveStage=0;s.attempts++
    s.firstParamBase=nonempty;s.paramsAfterConnect=0
    s.knownSystem0=false;s.system0=0;s.status0SocketMask=0
    s.systemErrorLatched=false
    s.endReason=""
}
func (s *sourceOriginalTask2Lifecycle) afterReceivedFrame(m *Monitor,f Frame) error {
    if s==nil || !s.connected{return nil}
    switch f.Type {
    case typeParam:
        count:=m.summary.SourceNonemptyParameters
        if count>s.firstParamBase {s.paramsAfterConnect=count-s.firstParamBase}
        // An observed partial PARAM suffices for source Stage1.
        // Do not invent Status0=0 or treat the unobserved FF sentinel
        // as a physically observed instrument system error.
        if s.stage==0 && s.paramsAfterConnect>0 {s.stage=1}
        // Read a fresh Status0 only after BOTH 16-bit register words
        // arrived on this TCP socket, never from a prior socket's
        // persistent RegisterImage or a frozen PARAM.
        if m.sourceOriginalRXGate==nil || !m.sourceOriginalRXGate.frozen {
            s.status0SocketMask|=sourceTask2Status0WordMask(f)
            if s.status0SocketMask==3 {
                if v,e:=m.image.Uint32(0x1006);e==nil {
                    s.knownSystem0=true;s.system0=v
                    if v>0 {s.systemErrorLatched=true;s.stage=3}
                }
            }
        }
    case typeAck:
        s.ackObserved++ // temporal only, never matched to a TX sequence
    case typeDenied:
        s.denialObserved++
        s.endReason="SOURCE_OPERATION_DENIED"
        // Unlike the old passive Go capture, original Task2 stops on
        // DENIED even when no application command was transmitted.
        return errTask2SourceDenied
    }
    s.lastLiveStage=s.stage
    return nil
}
func (s *sourceOriginalTask2Lifecycle) onDisconnected(reason string) {
    if s==nil || !s.connected{return}
    s.lastLiveStage=s.stage
    s.stage=0;s.connected=false;s.disconnected=true
    if s.endReason=="" {s.endReason=reason}
}
func (s *sourceOriginalTask2Lifecycle) receipt() sourceOriginalTask2LifecycleReceipt {
    r:=sourceOriginalTask2LifecycleReceipt{
        Schema:sourceOriginalTask2LifecycleSchema,Task:2,
        Stage:s.stage,LastLiveStage:s.lastLiveStage,
        Connected:s.connected,Attempts:s.attempts,
        NonemptyParamSinceConnect:s.paramsAfterConnect,
        Status0RegisterValid:s.knownSystem0,
        UnobservedFFSentinelRisk:s.connected && s.paramsAfterConnect>0 && !s.knownSystem0,
        SystemErrorLatched:s.systemErrorLatched,
        AckObserved:s.ackObserved,DenialObserved:s.denialObserved,
        Disconnected:s.disconnected,LastEndReason:s.endReason,
        OriginalDelphiThreadParityVerified:false,
        DeviceCommandSentByLifecycle:false,
    }
    if s.knownSystem0 {v:=s.system0;r.Status0Uint32=&v}
    return r
}
