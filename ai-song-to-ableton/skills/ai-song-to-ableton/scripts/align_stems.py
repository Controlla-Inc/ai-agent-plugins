"""Trim every stem so time 0 = bar 1 beat 1, and build the "music" stem.

Usage: align_stems.py <offset_s> <out_dir> <name>=<file.wav> [...] [--music instrumental=drums,bass]

Writes <out_dir>/<name>.wav for each input (24-bit). Inputs at different sample rates
are resampled to the most common one: a DAW bounce is often 48 kHz while most Controlla
stems come back at 44.1 kHz (and some, e.g. instrumental/vocals, at the input's 48 kHz).
--music A=B,C writes music.wav = A − B − C (e.g. instrumental minus drums minus bass):
the harmonic layer as ONE file, which is what Song to MIDI should transcribe. Splitting
piano/guitar/other separately sends one instrument into several stems and you end up
with the same part twice on different sounds.
"""
import os
import sys

from collections import Counter

import librosa
import numpy as np
import soundfile as sf


def main():
    offset, out = float(sys.argv[1]), sys.argv[2]
    os.makedirs(out, exist_ok=True)
    args = sys.argv[3:]
    music = None
    if "--music" in args:
        i = args.index("--music")
        music = args[i + 1]
        args = args[:i] + args[i + 2:]
    specs = [a.split("=", 1) for a in args]
    target = Counter(sf.info(p).samplerate for _, p in specs).most_common(1)[0][0]
    data = {}
    for name, path in specs:
        y, sr = sf.read(path, always_2d=True)
        if sr != target:
            print(f"{name}: resampling {sr} -> {target} Hz")
            y = librosa.resample(y.T, orig_sr=sr, target_sr=target, res_type="soxr_hq").T
            sr = target
        y = y[int(round(offset * sr)):]
        data[name] = (y, sr)
        sf.write(os.path.join(out, f"{name}.wav"), y, sr, subtype="PCM_24")
        print(f"{name}: {len(y) / sr:.1f} s")
    if music:
        base, minus = music.split("=")
        y, sr = data[base]
        y = y.copy()
        for m in minus.split(","):
            z, zsr = data[m]
            assert zsr == sr, f"{m} sample rate differs"
            n = min(len(y), len(z))
            y[:n] -= z[:n, :y.shape[1]] if z.shape[1] >= y.shape[1] else np.repeat(z[:n], y.shape[1], axis=1)
        y /= max(1.0, np.abs(y).max() / 0.99)
        sf.write(os.path.join(out, "music.wav"), y, sr, subtype="PCM_24")
        print(f"music = {base} - {minus}")


if __name__ == "__main__":
    main()
