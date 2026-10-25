MVK01 TCP/10230: passive connectivity test

1. Obtain permission for testing the operational device. Close MVKView.
2. Optional: start Wireshark capture with "host 10.13.42.84 and tcp port 10230" (or use .83).
3. Extract the zip to a normal folder. Double-click RUN_TEST.cmd, or in Windows CMD execute RUN_TEST.cmd.
4. Choose 1 for 10.13.42.84, 2 for 10.13.42.83.
5. Test receives data for a maximum of 12 seconds / 40 MiB, whichever comes first.
6. In the results folder: .json status and .raw received byte stream. Both may be shared for analysis.
7. A .raw file is TCP application payload, not a PCAPNG. To investigate handshake and connection closure, save the Wireshark PCAPNG too.

Safety: no sock.send() calls, no custom protocol commands. TCP handshaking and closing still occur; a connection may cause the device to start streaming. Do not run in parallel with MVKView. This tool has NOT been live-tested against a physical device.

If the workplace blocks .cmd execution, from Command Prompt run:
  py -3 passive_test.py --host 10.13.42.84 --seconds 12 --max-mb 40
