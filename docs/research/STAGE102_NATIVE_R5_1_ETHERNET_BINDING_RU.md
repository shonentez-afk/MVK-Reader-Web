# Stage102 / Native R5.1 — Ethernet interface selection and passive TCP/10230 activation

Date: 2026-10-29. The user clarified two essential live operating constraints:

1. **Connecting to the MVK01 on TCP/10230 itself starts streaming.** No MVK command/handshake is necessary or authorized in the diagnostic client. R5 was already `net.DialTimeout("tcp",IP:10230)` followed by `Read`; no `Write/Send` of application packets.
2. **The operator uses the Ethernet adapter.** R5 did NOT explicitly select a NIC; the Windows route table chose the egress interface. This is an operational gap for multihomed Windows hosts (Wi-Fi/VPN/Ethernet).

## Delivered: MVK10230 Diagnostic R5.1 Windows x64

Full executable **plus full Go source, offline demo, tests, SHA256 manifest and Russian instructions** are preserved in the conversation artifact:
`MVK10230_Diagnostic_R5_1_Ethernet_Windows_x64.zip`

Executable SHA256:
`023186039c0e99599b906a2b7b970fa6232a8141d89ba1de35c1d60f985c0dd9`.

### Changes

- Interactive double-click launch enumerates all UP non-loopback local IPv4 network interfaces by **Windows name, index, IPv4/mask, MAC** and **requires explicit operator selection of the wired Ethernet interface**. A name/MAC alone does not scientifically guarantee physical media type: the operator must verify that the selected adapter is wired.
- CLI Live requires explicit `-local-ip <local_wired_ipv4>`; `-list-interfaces` shows available interfaces without connecting.
- Source `net.Dialer.LocalAddr` bound to selected IPv4. Windows-specific `net.Dialer.Control` uses `IP_UNICAST_IF=31` with 24-bit IPv4 interface index **in network byte order**, as specified by Microsoft's WinSock IPPROTO_IP socket-option documentation. Failed binding is a hard failure, not a fallback to the system route. Post-dial validation checks actual `conn.LocalAddr().IP` against selected local IPv4.
- Records `selected_interface`, `selected_interface_index`, `selected_local_ipv4`, `connected_local_address`, `connected_remote_address` in `summary.json` and logs. Exact transport remains IPv4 **TCP/10230**, not Modbus TCP/502.
- Automatic start remains **connect → read**, NO MVK application commands, sample-rate writes, Flash, reboot, pings, network adapter reconfiguration.
- Live connection may still occupy a single client slot or affect an industrial device; approval required.
- `incoming.raw` is exact received application stream, **NOT** MVKView's gain-adjusted BIN.

### QA

- 13/13 Go unit tests PASS; `go vet` PASS; `go test -race` PASS.
- Windows/amd64 PE32+ executable and Windows/amd64 test executable cross-compile PASS.
- Local Linux TCP fake server with explicitly bound source IP: **zero outbound application bytes** and report contains actual local socket.
- Demo replay: 46,952 bytes, 15 frames, one AUX4700, one 32,800-byte register snapshot, PASS.
- Real offline first-20MiB replay (83 capture): 25,512 valid frames, 18 AUX4700, one full snapshot, 188-byte incomplete tail identified.
- Entire ZIP archive CRC and SHA256 manifest independently verified.
- **NOT tested on a Windows runtime or with an actual live MVK01.** Windows IP_UNICAST_IF usage is verified by code review against official API, not a Windows execution proof.

### First field trial

Double-click `MVK10230_Diagnostic_R5_1_Windows_x64.exe`; enter instrument IPv4, 15 seconds, choose actual wired Ethernet NIC, confirm YES with equipment authorization. After completing, privately submit `MVK10230_TEST_RESULTS.zip` for inspection. Do not publish raw capture or factory details in public GitHub.

The stable MVK Reader Web **v0.3.40 remains unchanged**. This R5.1 source is in the attached ZIP, not integrated into the stable product. Prior R5 GitHub sources remain unchanged for regression history.
