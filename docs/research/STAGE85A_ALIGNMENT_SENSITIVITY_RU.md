# Stage85a — lag sensitivity for real BIN and VALUES

The user confirmed BIN and VALUES were started with two separate buttons; the zero-offset assumption is not a physical synchronization proof. Using original MVK43 ADC1/3/6 BIN and 63 VALUES cycles, an offline Butterworth-3 acceleration 10–3000 Hz comparison scanned shared offsets from -0.5 to +1.75 seconds in 25-ms increments. Median absolute log ratio was fitted to cycles 1–30; cycles 31–63 were held out.

Best training-grid offset: +0.025 s, with zero offset a close alternative. This is an **algorithmic alignment estimate**, not the delay between button presses or absolute timestamp synchronization.

Holdout cycles 31–63: ADC1 median absolute error 0.952% at 0 s vs 0.940% at +25 ms, correlation 0.792 vs 0.893. ADC3: 0.776% vs 0.832%, correlation 0.988 vs 0.986 (worse). ADC6: 1.836% vs 1.491%, correlation 0.991 vs 0.994. Improvement is therefore not universal and must not be misrepresented as exact alignment.

Reproducible offline scripts and JSON were provided as `stage85_alignment_package.zip` in conversation; raw recordings remain private and out of GitHub. Next: investigate CSV timestamp semantics, separate channel offsets and per-cycle boundaries before interpreting filter error; stable v0.3.40 unchanged, no device connection.