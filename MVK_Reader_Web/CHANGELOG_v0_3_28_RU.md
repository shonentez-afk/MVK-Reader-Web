# v0.3.28 - Collector resilience LAB

- SQLite connections now explicitly set a 5-second busy timeout.
- Online backup runs in a temporary file and verifies full integrity before publishing.
- Publishing uses an exclusive filesystem link to prevent overwriting existing backups.
- Failed backup cleans partial file; original database and preexisting backup remain untouched.
- No device reads/writes or polling changes.
