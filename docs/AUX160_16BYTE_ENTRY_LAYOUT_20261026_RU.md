# AUX160: four 16-byte entries and initialization from VAST_MVK (2026-10-26)

Confirmed directly against both preserved 12-second RAW streams. For a channel with zero-based index N, define B = 17296 + 1024*N, relative to the start of the initial VAST_MVK header.

Each of the four entries in AUX160 consists of **four uint32-sized slots**:

| Entry j | AUX160 offset | Initial header offset | Encoding/observation |
|---|---:|---:|---|
| 0 | +32 | B-8 | changing float32 measurement |
| 0 | +36 | B-4 | invariant uint32 descriptor |
| 0 | +40 | B+0 | invariant float32 reference |
| 0 | +44 | B+4 | zero |
| 1 | +48 | B+8 | changing float32 measurement |
| 1 | +52 | B+12 | invariant uint32 descriptor |
| 1 | +56 | B+16 | invariant float32 reference |
| 1 | +60 | B+20 | zero |
| 2 | +64 | B+24 | changing float32 measurement |
| 2 | +68 | B+28 | invariant uint32 descriptor |
| 2 | +72 | B+32 | invariant float32 reference |
| 2 | +76 | B+36 | zero |
| 3 | +80 | B+40 | changing float32 measurement |
| 3 | +84 | B+44 | invariant uint32 descriptor |
| 3 | +88 | B+48 | invariant float32 reference |
| 3 | +92 | B+52 | zero |

**Bitwise validation**: for all eight channels of instrument A and 12 AUX160 frames/channel, all 4 descriptor fields matched the corresponding initial header values: 384/384. Fixed float32 reference fields also matched: 384/384. On instrument B, the corresponding initialization records are zero.

Additional evidence: initial header also carries a value before each descriptor/reference pair, and these initial values differ from later measured AUX160 current values. Thus the 16-byte entry is better modeled as `current_float32, uint32_descriptor, reference_float32, uint32_reserved`; AUX160 varies only `current_float32`, while the initial metadata preserves the seed snapshot.

Examples of integer descriptors: 0x11, 0x411, 0x814, 0xc14, 0xc15, 0xc11, 0x212. These **must not** be mistaken for ADC's sensor-voltage status bits from AUX4700; their semantics remain unknown.

Six active channels of A contain initialized entries, while two faulted channels have zeros for float32 values and descriptor 0x212. B has zeros in these slots across all channels.

**Meaning of reference_float32 is unresolved**. It could be a stored benchmark / earlier measurement / configurable reference, but one cannot distinguish these without documentation or a controlled configuration comparison.

No software release modifications, no equipment connections. Raw payloads remain local.
