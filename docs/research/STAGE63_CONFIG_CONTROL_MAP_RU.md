# Stage 63 — Control configuration to measurement status address mapping (2026-10-28)

Source: official manufacturer specification v1.0.39, sections 3.2, 3.5, 3.7.9 and 3.7.10; audited Stage60 CONTROL_FIELDS.csv. No firmware reverse engineering.

For ADC channel N=0..7: configuration base `A=0x0100+N*0x0100`. For controlled parameter slot j=0..7, eight-register (32-byte) configuration begins at `A+0x60+j*0x10`. The first 4-byte field is **parameter number (1..144)**, followed by yellow/red thresholds, up/down delays, hysteresis, and display scale. Status record begins at **measurement** register address `0x2000+N*0x200+0x130+j*0x08`; 8 registers = 16 bytes = current float32, status u32, last transition value float32, reserved u32.

Verified 64 unique channel/slot configuration-to-status mappings and valid state zone codes across 128 channel/slot summaries (two instruments). **The live configuration containing the real parameter numbers is not available in the capture**. `DefaultConfig.txt` has zero parameter selections and is a template, not the live configuration of instruments .83/.84. Therefore it is incorrect to label control slot 4 as acceleration/velocity solely from its numeric magnitude.

The manufacturer document describes Modbus/502; embedded 10230 block correspondence is independently established by observed identifiers and block sizes.

Local reproducible package `MVKVIEW_STAGE63_CONFIG_CONTROL_20261028.zip` includes complete `stage63_config_control.py`, `REGISTER_MAPPING.csv` and Russian report. No instrument traffic. Stable v0.3.40 untouched.