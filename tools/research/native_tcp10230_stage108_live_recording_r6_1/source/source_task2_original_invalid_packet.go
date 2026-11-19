package main

// PRIVATE three-source references: Projects.7z/_Unit125.pas
// TMVKThread.Execute 00807F8B..00807FA1 and 00808706,
// original exceptions 00808871..0080897E, Task2 retry
// 008089A3..00808B15; mvk_idr(1).sqlite call index;
// mvkview.idp TMVKThread.Stage +3C, CommandList +34.
// Original material / PCAP / network credentials never committed.
import (
    "errors"
    "fmt"
)
var errTask2SourceInvalidPacket=errors.New("source original Task2 invalid packet")

func(m *Monitor)sourceTask2InvalidPacket(cause error)error {
    m.summary.InvalidFrames++
    m.summary.SourceTask2ProtocolExceptions++
    m.summary.SourceTask2LastProtocolError=cause.Error()
    m.warn(fmt.Sprintf("original Task2 invalid packet: %v; close THIS socket; preserve RAW; retry only if approved",cause))
    // Do NOT set a persistent captureOnly here. A newly permitted
    // socket starts a fresh Framer and Source Stage0, independently
    // SHA-verified. Finalize fails closed for the aggregate run.
    return fmt.Errorf("%w: %v",errTask2SourceInvalidPacket,cause)
}
