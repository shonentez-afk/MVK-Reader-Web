# Stage 56: TCP measurement control blocks

Offline review of two archived captures found 135 packets of length 160 in each capture. Each packet contains one nested record with 64 16-bit words. There are nine identifiers: 0x1000 and eight channel identifiers 0x2130 through 0x2F30, step 0x200, fifteen instances of each in both captures.

The first eight bytes of ID 0x1000 carry an ASCII instrument serial. These strings confirm the earlier file-to-instrument matching independently from rounded calibration gains.

All eight channel records have nonzero bodies in the first capture and zero-filled bodies in the second. This does not imply that time-domain measurements are zero. Meanings of the 128-byte channel records remain unresolved.

Validation: 270 packets, 18 identifier groups, no device interaction. Complete original script, CSV and report remain in local archive MVKVIEW_STAGE56_STRUCTURED160_SERIALS_20261028.zip. Stable application unchanged.