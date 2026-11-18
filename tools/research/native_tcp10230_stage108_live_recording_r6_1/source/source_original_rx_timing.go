package main

// Direct PRIVATE triple-source parity evidence, read-only:
// _Unit125.pas TMVKThread.Execute IDP 00807C24..00807C39 sets
// TIdTCPClient.ConnectTimeout=0x3E8 and ReadTimeout=0x1388.
// The timeout applies to the original Task2 reception regardless of
// whether the operator has separately approved SetRate transmission.
import "time"

const sourceOriginalConnectTimeout=time.Second
const sourceOriginalReadTimeout=5*time.Second

func sourceOriginalReadTimedOut(lastPacket,now time.Time) bool {
    return !now.Before(lastPacket.Add(sourceOriginalReadTimeout))
}
