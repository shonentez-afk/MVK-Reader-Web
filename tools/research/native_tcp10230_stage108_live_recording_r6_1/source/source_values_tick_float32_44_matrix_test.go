package main

// The same 44 IEEE-754 source-format CANDIDATE guards as Python.
// These assert cross-implementation stability, NOT vendor Delphi x87
// FormatFloat, not Windows locale or original GetValueText 1:1.
import (
    "crypto/sha256"
    "encoding/binary"
    "fmt"
    "testing"
)

func TestSourceGetValueTextFloat32Candidate44IEEEParity(t *testing.T){
    bits:=[]uint32{
        0x00000000,
        0x80000000,
        0x00000001,
        0x80000001,
        0x007fffff,
        0x00800000,
        0x80800000,
        0x3dcccccd,
        0xbdcccccd,
        0x3f800000,
        0xbf800000,
        0x3fc00000,
        0x40200000,
        0x7f7fffff,
        0xff7fffff,
        0x7f800000,
        0xff800000,
        0x7fc00000,
        0xffc00000,
        0x3f000000,
        0x3eaaaaab,
        0x42f70000,
        0x447a0000,
        0x44fa0000,
        0x45000000,
        0x461c4000,
        0x477fe000,
        0x3a83126f,
        0x3935bdc6,
        0x1cb3d9b5,
        0x5f3759df,
        0x2c3d4e5f,
        0x7e4fffff,
        0xf74fffff,
        0x3f7fffff,
        0x3f800001,
        0x447a0001,
        0x4479ffff,
        0x4c000000,
        0x4bfffffe,
        0x4d800000,
        0x4d7fffff,
        0x80000002,
        0x47c35000,
    }
    h:=sha256.New()
    for _,v:=range bits {
        raw:=make([]byte,4)
        binary.LittleEndian.PutUint32(raw,v)
        got:=sourceFloat32FourSignificantCandidate(raw)
        _,_=fmt.Fprintf(h,"%08x:%s\n",v,got)
    }
    if len(bits)!=44{
        t.Fatalf("wrong candidate vector count %d",len(bits))
    }
    expected:="2d473a0bef28878044163499021c74571d5072c62dc3fc839c447268b9ca31f2"
    if got:=fmt.Sprintf("%x",h.Sum(nil));got!=expected{
        t.Fatalf("source Float32 Go candidate drift: %s != %s",got,expected)
    }
}
