package main

// Source-derived StatusCells (original MVKView 1.0.47) — PASSIVE RX only.
//
// PRIVATE _Unit125.pas 00805D08..00805EA0 reads 14 DWORD cells from
// the original register buffer; source addresses at IDP .data 008D3068.
// The 14 DWORDs were independently found as one contiguous sequence in
// the operator-supplied IDP. They are NOT the 15 captions of PageStatus.
//
// TMVKThread initializes its own StatusCells[] with 0xFFFFFFFF. We must
// NOT serialize that source sentinel as an observed instrument value.
// Valid flags below come ONLY from decoded PARAM register blocks.
// Two adjacent 16-bit register words must BOTH be observed for each cell.
//
// No TCP writes, new sockets, register polls or changes to original RAW.

var sourceStatusCellAddresses = [14]uint16{
    0x1006, 0x1038, 0x1030, 0x1032,
    0x2120, 0x2320, 0x2520, 0x2720,
    0x2920, 0x2B20, 0x2D20, 0x2F20,
    0x3004, 0x3104,
}

type LiveSourceStatusCell struct {
    Index int `json:"index"`
    Address uint16 `json:"register_address"`
    Valid bool `json:"valid"`
    Value *uint32 `json:"value_uint32"`
}

// Snapshot is run only from the SAME monitor goroutine as the PARAM
// decoder. It cannot observe a partially-applied register update.
func (m *Monitor) snapshotSourceStatusCells() []LiveSourceStatusCell {
    result := make([]LiveSourceStatusCell, 0, len(sourceStatusCellAddresses))
    for i, addr := range sourceStatusCellAddresses {
        item := LiveSourceStatusCell{Index: i, Address: addr}
        v, err := m.image.Uint32(int(addr))
        if err == nil {
            item.Valid = true
            vv := v
            item.Value = &vv
        }
        result = append(result, item)
    }
    return result
}
