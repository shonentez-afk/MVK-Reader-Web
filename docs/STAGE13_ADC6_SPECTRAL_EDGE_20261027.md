# Stage13 — ADC6 high frequency spectral audit, 2026-10-27

Source: RunUp27-10-2026 08-54-11.zip. Device IP 10.13.42.83 (internal MVK00000050), machine running; operator chose ADC4/ADC6 as candidates. ADC1 short, ADC5 open.

Method: SciPy Welch Hann 65536 samples (1 Hz bins) for peaks; independent boxcar periodogram with detrend constant and density scaling integrated from 10 to selected cutoff for RMS.

ADC6 significant peaks: 2481, 2779, 2886, 2993 Hz (plus 1002,1886 Hz). ADC4 peaks ~1015,1353,1804 Hz.

Cutoff [10,F) Hz | ADC6 RMS m/s2: F2500 2.15605; F3000 2.71341; F3100 2.93699; F3200 3.13171; F3300 3.31498; F3320 3.43268; F3500 3.78381. ADC4 F3000 4.41496, F3500 4.42675.

MVKView ADC6 reported 10–3000 median 3.3945 versus our ideal spectral cutoff 2.71341 (-20.06%). MVKView value lies between our F3300 and F3320 calculations: this DOES NOT establish a 3.3 kHz MVKView cutoff; filter rolloff, time-window selection, units and numerical method remain unknown. 10–1000 Hz difference ~2%.

Engineering interpretation: unusually strong stable spectral energy close to and above 3 kHz; test cutoff sensitivity. Don't assert measurement-core failure, don't fit filter solely to match vendor numbers.

Optional ADC6 rerecord: 30–60 s native BIN+tsxml, VALUES CSV and several TABLE CSV from same recording, spectrum numerical export and screenshot if available, full filter/band/unit settings and running machine rpm/load/time. No concurrent TCP collector. Additional PCAP not required at this point.

Local evidence MVK83_ADC6_HIGH_FREQUENCY_AUDIT_20261027.zip contains REPORT_RU.md and SPECTRAL_PEAK_AUDIT.json. Original private bin files stay off GitHub. Production MVK Reader Web v0.3.40 not modified.