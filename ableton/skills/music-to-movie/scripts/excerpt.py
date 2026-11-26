"""Cut a bar-aligned excerpt out of a song stem so it can sit on the cue's grid.

Usage: excerpt.py <src.wav> <out.wav> --bpm 113.01 --offset 0.405 --from 250 --to 263
                  [--fade-in 0.03] [--fade-out 2.5]   (fades in BEATS)  [--pre-ms 15]

--offset is where the song's beat 0 sits (find_grid.py, then nudged so drum hits read x.00).
--from/--to are SONG beats (floats ok). The file starts --pre-ms before the first beat so a
hit on that beat keeps its transient; place it that much early (place it at beat - pre).
Works only when the song's tempo equals the cue's tempo (within ~0.1 BPM for a short cue):
generate the song AT the tempo the cuts asked for, and measure it before trusting that.
"""
import argparse
import numpy as np
import soundfile as sf

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--bpm", type=float, required=True); ap.add_argument("--offset", type=float, required=True)
ap.add_argument("--from", dest="a", type=float, required=True); ap.add_argument("--to", dest="b", type=float, required=True)
ap.add_argument("--fade-in", type=float, default=0.03); ap.add_argument("--fade-out", type=float, default=0.25)
ap.add_argument("--pre-ms", type=float, default=15.0)
a = ap.parse_args()
y, sr = sf.read(a.src, always_2d=True)
beat = 60.0 / a.bpm
s = int((a.offset + a.a * beat - a.pre_ms / 1000) * sr); e = int((a.offset + a.b * beat) * sr)
x = y[max(s, 0):e].copy()
ni, no = int(a.fade_in * beat * sr), int(a.fade_out * beat * sr)
if ni: x[:ni] *= np.linspace(0, 1, ni)[:, None]
if no: x[-no:] *= (np.linspace(1, 0, no) ** 1.5)[:, None]
sf.write(a.out, x, sr, subtype="PCM_24")
print("%s  %.2f s  (song %.2f-%.2f s)" % (a.out, len(x) / sr, max(s, 0) / sr, e / sr))
