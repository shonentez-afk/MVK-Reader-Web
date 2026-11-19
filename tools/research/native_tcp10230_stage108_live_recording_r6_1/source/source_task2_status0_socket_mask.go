package main

// _Unit125.pas:00808581/00805D08 observes StatusCells after
// source nonempty PARAM. Native RegisterImage persists across TCP sockets;
// an old Status0 MUST NOT count as fresh evidence on a new connection.
// This metadata scans exactly the register words in this PARAM.
// Private evidence: Projects.7z/_Unit125.pas; mvk_idr(1).sqlite
// function/call index; mvkview.idp Stage+3C, StatusCells+4008C.
func sourceTask2Status0WordMask(f Frame) uint8 {
    if f.Type!=typeParam {return 0}
    blocks,err:=decodeBlocks(f.Raw)
    if err!=nil {return 0} // ProcessChunk already rejects invalid frames
    var mask uint8
    for _,b:=range blocks {
        begin:=int(b.Addr)
        end:=begin+int(b.Words)
        if begin<=0x1006 && 0x1006<end {mask|=1}
        if begin<=0x1007 && 0x1007<end {mask|=2}
    }
    return mask
}
