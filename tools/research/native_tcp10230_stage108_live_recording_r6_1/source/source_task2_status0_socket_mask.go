package main

import "encoding/binary"

// _Unit125.pas:00808581/00805D08 observes StatusCells after
// source nonempty PARAM. Native RegisterImage persists across TCP sockets;
// an old Status0 MUST NOT count as fresh evidence on a new connection.
// This metadata scans exactly the register words in this PARAM.
// Private evidence: Projects.7z/_Unit125.pas; mvk_idr(1).sqlite
// function/call index; mvkview.idp Stage+3C, StatusCells+4008C.
// Return BOTH observed-word coverage and an unambiguously nonzero
// latest wire value from either half of Status0. A nonzero half proves
// an actual original 32-bit system error before both words are known.
// A later duplicate descriptor in the SAME frame replaces earlier
// values, as it does in the original register image update.
func sourceTask2Status0WordEvidence(f Frame)(mask uint8,observedNonzero bool){
    if f.Type!=typeParam{return 0,false}
    blocks,e:=decodeBlocks(f.Raw)
    if e!=nil{return 0,false}
    var low,high uint16
    for _,b:=range blocks{
        begin:=int(b.Addr)
        end:=begin+int(b.Words)
        if begin<=0x1006 && 0x1006<end{
            mask|=1
            pos:=(0x1006-begin)*2
            low=binary.LittleEndian.Uint16(b.Payload[pos:pos+2])
        }
        if begin<=0x1007 && 0x1007<end{
            mask|=2
            pos:=(0x1007-begin)*2
            high=binary.LittleEndian.Uint16(b.Payload[pos:pos+2])
        }
    }
    return mask,((mask&1)!=0 && low!=0)||((mask&2)!=0 && high!=0)
}

// Legacy mask name retains the narrower source on-wire metadata query.
func sourceTask2Status0WordMask(f Frame) uint8 {
    mask,_:=sourceTask2Status0WordEvidence(f)
    return mask
}
