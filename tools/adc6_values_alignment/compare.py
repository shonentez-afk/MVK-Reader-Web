#!/usr/bin/env python3
"""Offline ADC6 BIN / VALUES comparison. No network/device operations."""
import argparse
import csv
from datetime import datetime
from pathlib import Path
import numpy as np
from scipy.signal import periodogram

def load_values(path):
    with open(path, encoding="cp1251", newline="") as f:
        rows = list(csv.reader(f, delimiter="|"))
    labels = rows[2]
    fields = [labels.index("Виброускорение, 10..3000 Гц"),
              labels.index("Виброускорение, 10..2000 Гц"),
              labels.index("Виброускорение, 10..1000 Гц")]
    t0 = datetime.strptime(rows[3][0], "%H:%M:%S.%f")
    times, measures = [], []
    for r in rows[3:]:
        if len(r) != len(labels):
            continue
        ti = datetime.strptime(r[0], "%H:%M:%S.%f")
        times.append((ti - t0).total_seconds())
        measures.append([float(r[i].replace(",", ".")) for i in fields])
    return np.asarray(times), np.asarray(measures)

def compare(binary, values, fs, start_offset, window):
    samples = np.memmap(binary, dtype="<f4")
    times, reference = load_values(values)
    # Start_offset: time of first VALUES row relative to actual BIN start.
    times = times + start_offset
    ours, theirs = [], []
    for t, ref in zip(times, reference):
        a, b = int(round((t-window)*fs)), int(round(t*fs))
        if a < 0 or b > len(samples) or b-a != int(round(window*fs)):
            continue
        freq, psd = periodogram(samples[a:b], fs=fs, window="boxcar",
                               detrend="constant", scaling="density")
        df = freq[1]-freq[0]
        calc = [float(np.sqrt(np.sum(psd[(freq>=10)&(freq<hi)])*df))
                for hi in (3000,2000,1000)]
        ours.append(calc)
        theirs.append(ref)
    x, y = np.asarray(ours), np.asarray(theirs)
    print("N windows:", len(x), "window seconds:", window)
    for j, band in enumerate(("10-3000","10-2000","10-1000")):
        print(band, "BIN median", np.median(x[:,j]),
              "MVKView median", np.median(y[:,j]),
              "median pointwise ratio", np.median(x[:,j]/y[:,j]),
              "Pearson r", np.corrcoef(x[:,j],y[:,j])[0,1])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("binary", type=Path)
    ap.add_argument("values_csv", type=Path)
    ap.add_argument("--fs", type=int, default=65536)
    ap.add_argument("--first-values-offset", type=float, default=-0.089,
                    help="Seconds, first VALUES sample relative to estimated BIN start (not proven)")
    ap.add_argument("--window", type=float, default=2.0)
    a = ap.parse_args()
    compare(a.binary,a.values_csv,a.fs,a.first_values_offset,a.window)
