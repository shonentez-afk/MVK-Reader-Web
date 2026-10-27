"""Offline test of Butterworth band-pass transfer functions on exported float32 BIN."""
import argparse
import numpy as np
from scipy.signal import butter, periodogram, sosfreqz

def calculate(path, fs=65536):
    x = np.fromfile(path, dtype="<f4").astype(np.float64)
    x -= x.mean()
    f, psd = periodogram(x, fs=fs, window="boxcar",
                         detrend=False, scaling="density")
    df = f[1] - f[0]
    ideal = np.sqrt(np.sum(psd[(f >= 10) & (f < 3000)]) * df)
    print("Ideal [10,3000):", ideal)
    for order in (1, 2, 3, 4, 5, 6, 8):
        sos = butter(order, [10, 3000], btype="bandpass", fs=fs, output="sos")
        _, response = sosfreqz(sos, worN=f, fs=fs)
        rms = np.sqrt(np.sum(psd * np.abs(response)**2) * df)
        print("Butterworth order", order, "RMS", rms)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bin_file")
    parser.add_argument("--fs", type=int, default=65536)
    arguments = parser.parse_args()
    calculate(arguments.bin_file, arguments.fs)
