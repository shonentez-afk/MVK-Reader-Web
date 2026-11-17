package main

// Stage111Z31FI: original TMvkChannelStorage receive ring, separate from
// the tiny GUI preview and from the immutable RAW / verified BIN spool.
//
// PRIVATE three-source provenance (not committed):
//   _Unit128 00846C67..00846CBD allocates 8 Float32 + 2 byte storages,
//     each with 0x200000 elements BEFORE creating TMVKThread.
//   _Unit115 TMvkChannelStorage.Create 007D0988, AllocBufferChunk 007D1B08,
//     ProcessBufferChunk 007D2398, InvalidateData 007D1AE0,
//     CheckDataAvailability 007D1998.
//   _Unit125 TMVKThread.Execute 008081EA..0080828C calls Allocate/Process
//     on the sole receive thread after verifying each sample packet.
//
// The on-wire TACH has 64 Float32 words = 256 raw bytes. Original TACH
// storage is BYTE (data type 2): RxPos advances by 256 bytes, while its
// device sample Index advances by 64. Those positions are NOT interchangeable.
// The Float32 domain comes from the already-verified calibrated spool when
// available, otherwise raw device Float32 bits are kept with a distinct label.
// No TCP, device commands, periodic 64 MiB GUI snapshots or extra disk writes.
import (
    "errors"
    "fmt"
    "math"
)

const (
    sourceOriginalStorageSamples = 0x200000
    sourceOriginalStorageMask = sourceOriginalStorageSamples - 1
    sourceOriginalStorageSchema = "MVK_SOURCE_CHANNEL_STORAGE_V1"
    sourceStorageUnscaledADC = "RAW_DEVICE_FLOAT32_NOT_YET_CALIBRATED"
    sourceStorageCalibratedADC = "CALIBRATED_NATIVE_R6_BIN_SPOOL_FLOAT32"
    sourceStorageTachBytes = "TACH_EXACT_DEVICE_PAYLOAD_BYTES"
)

type sourceOriginalChannelRing struct {
    data []byte
    rxPos uint64
    validPos uint64
    sampleRate uint32
    nextDeviceIndex uint32
    seen bool
    domain string
    sequenceGaps uint64
    rateChanges uint64
    rejectedNonfinite uint64
}

type sourceOriginalStorageRing struct {
    channels [10]sourceOriginalChannelRing
}

func newSourceOriginalStorageRing() *sourceOriginalStorageRing {
    return &sourceOriginalStorageRing{}
}

func sourceOriginalElementWidth(channel int) int {
    if channel < 0 || channel >= 10 { return 0 }
    if channel < 8 { return 4 }
    return 1
}

func (r *sourceOriginalStorageRing) appendFrame(
    h SampleHeader, payload []byte, domain string,
) error {
    if r == nil { return errors.New("source storage not initialized") }
    width := sourceOriginalElementWidth(h.Channel)
    if width == 0 || !acceptedRates[h.Rate] {
        return fmt.Errorf("invalid original channel/rate %d/%d",h.Channel,h.Rate)
    }
    expectBytes:=1024
    expectSamples:=256
    expectDomain:=sourceStorageCalibratedADC
    if h.Channel >= 8 {
        expectBytes=256
        expectSamples=64
        expectDomain=sourceStorageTachBytes
    }
    if len(payload) != expectBytes || h.Samples != expectSamples {
        return fmt.Errorf("incorrect original storage packet length: ch=%d size=%d",h.Channel,len(payload))
    }
    if h.Channel < 8 {
        if domain != expectDomain && domain != sourceStorageUnscaledADC {
            return errors.New("unknown original ADC storage input domain")
        }
    } else if domain != expectDomain {
        return errors.New("TACH original byte storage must preserve exact payload bits")
    }
    c:=&r.channels[h.Channel]
    count:=uint64(len(payload)/width)
    if c.rxPos>math.MaxUint64-count {
        return errors.New("uint64 source receive cursor overflow")
    }
    // A source gap, changed sample rate or raw/calibrated domain invalidates
    // the old continuous window WITHOUT fabricating lost samples.
    if c.seen {
        if h.Index!=c.nextDeviceIndex {
            c.sequenceGaps++
            c.validPos=c.rxPos
        }
        if h.Rate!=c.sampleRate {
            c.rateChanges++
            c.validPos=c.rxPos
        }
        if domain!=c.domain {
            c.validPos=c.rxPos
        }
    }
    c.nextDeviceIndex=h.Index+uint32(h.Samples) // uint32 wraps by design
    c.sampleRate=h.Rate
    c.seen=true
    c.domain=domain
    if h.NonFinite>0 {
        // RAW still carries the exact packet. Never present nonfinite bits
        // as a verified current GetSignal/GetRawSignal window.
        c.rejectedNonfinite++
        c.validPos=c.rxPos
        return nil
    }
    if c.data==nil {
        c.data=make([]byte,sourceOriginalStorageSamples*width)
    }
    start:=int(c.rxPos&sourceOriginalStorageMask)*width
    n:=copy(c.data[start:],payload)
    if n<len(payload) {
        copy(c.data,payload[n:])
    }
    c.rxPos+=count
    return nil
}

// window returns a COPY of exact stored bits, not the downsampled GUI trace.
// Only a contiguous, still-resident and rate-consistent window is permitted.
func (r *sourceOriginalStorageRing) window(
    channel int,start uint64,count uint64,
) ([]byte,error) {
    width:=sourceOriginalElementWidth(channel)
    if r==nil || width==0 || count==0 || count>sourceOriginalStorageSamples ||
       count>math.MaxUint64-start {
        return nil,errors.New("invalid source ring read")
    }
    c:=&r.channels[channel]
    earliest:=c.validPos
    if c.rxPos>sourceOriginalStorageSamples &&
       c.rxPos-sourceOriginalStorageSamples>earliest {
        earliest=c.rxPos-sourceOriginalStorageSamples
    }
    if c.data==nil || start<earliest || start+count>c.rxPos {
        return nil,errors.New("source ring data unavailable or overwritten")
    }
    out:=make([]byte,int(count)*width)
    pos:=int(start&sourceOriginalStorageMask)*width
    n:=copy(out,c.data[pos:])
    if n<len(out) { copy(out[n:],c.data[:len(out)-n]) }
    return out,nil
}

type sourceOriginalChannelReceipt struct {
    Channel int `json:"channel"`
    SampleWidthBytes int `json:"sample_width_bytes"`
    RxPos uint64 `json:"rx_pos_64"`
    ValidPos uint64 `json:"valid_pos_64"`
    FirstReadable uint64 `json:"first_readable_pos_64"`
    Available uint64 `json:"available_elements"`
    SampleRate uint32 `json:"last_sample_rate_hz"`
    NextDeviceIndex *uint32 `json:"next_device_sample_index,omitempty"`
    Domain string `json:"input_domain"`
    SequenceGaps uint64 `json:"sequence_gaps"`
    RateChanges uint64 `json:"rate_changes"`
    RejectedNonfinite uint64 `json:"rejected_nonfinite_frames"`
}

type sourceOriginalStorageReceipt struct {
    Schema string `json:"schema"`
    BufferSamples uint32 `json:"buffer_elements_per_channel"`
    Channels []sourceOriginalChannelReceipt `json:"channels"`
}

func (r *sourceOriginalStorageRing) receipt() sourceOriginalStorageReceipt {
    result:=sourceOriginalStorageReceipt{
        Schema:sourceOriginalStorageSchema,BufferSamples:sourceOriginalStorageSamples,
        Channels:make([]sourceOriginalChannelReceipt,0,10),
    }
    for ch:=0;ch<10;ch++ {
        c:=r.channels[ch]
        width:=sourceOriginalElementWidth(ch)
        first:=c.validPos
        if c.rxPos>sourceOriginalStorageSamples &&
           c.rxPos-sourceOriginalStorageSamples>first {
            first=c.rxPos-sourceOriginalStorageSamples
        }
        row:=sourceOriginalChannelReceipt{
            Channel:ch+1,SampleWidthBytes:width,RxPos:c.rxPos,ValidPos:c.validPos,
            FirstReadable:first,Available:c.rxPos-first,
            SampleRate:c.sampleRate,Domain:c.domain,
            SequenceGaps:c.sequenceGaps,RateChanges:c.rateChanges,
            RejectedNonfinite:c.rejectedNonfinite,
        }
        if c.seen {
            next:=c.nextDeviceIndex
            row.NextDeviceIndex=&next
        }
        result.Channels=append(result.Channels,row)
    }
    return result
}
