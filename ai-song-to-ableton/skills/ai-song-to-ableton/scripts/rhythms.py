"""How each instrument actually plays, per section: hits per bar, where in the bar, how long.

Usage: rhythms.py <plan.json> <bar_levels.json> <name>=<aligned stem.wav> [...]

Prints a 16-step grid per section ('X' = a hit in most bars, 'x' = in some) and the median
sustain after a hit. Use it to write each part's pattern in plan.json – e.g. on the first
song: bass ~2 hits/bar with an "and of 2" anticipation, piano ~1 held chord per bar,
guitar short chops just before beats 2 and 4. Raw transcriptions are busy even when
accurate; these measured patterns are what make the parts feel like the record.
"""
import json
import sys

import librosa
import numpy as np

SR = 22050


def main():
    plan, lv = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
    spb = 60.0 / plan["bpm"]
    for spec in sys.argv[3:]:
        key, path = spec.split("=", 1)
        y = librosa.load(path, sr=SR)[0]
        env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=256)
        fr = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=256, backtrack=True, delta=0.2)
        t = librosa.frames_to_time(fr, sr=SR, hop_length=256) / spb
        strength = env[np.minimum(fr + 2, len(env) - 1)]
        rms = librosa.feature.rms(y=y, hop_length=256)[0]
        sus = []
        for f in fr[:400]:
            pk, k = rms[f:f + 4].max(), f
            while k < len(rms) - 1 and rms[k] > pk * 0.25 and k - f < 200:
                k += 1
            sus.append((k - f) * 256 / SR / spb)
        print(f"\n{key}: median sustain after a hit {np.median(sus) if sus else 0:.2f} beats")
        thr = -40 if "bass" in key else -50
        for sec in plan["sections"]:
            a, b = sec["bars"]
            bars = [i for i in range(a - 1, b) if i < len(lv.get(key, [])) and lv[key][i] > thr]
            if not bars:
                print(f"  {sec['name']:<12} (silent)")
                continue
            sel = np.isin((t // 4).astype(int), bars) & (strength > np.percentile(strength, 40))
            h = np.bincount(np.round((t[sel] % 4) * 4).astype(int) % 16, minlength=16) / len(bars)
            g = "".join("X" if v >= 0.6 else ("x" if v >= 0.3 else ".") for v in h)
            print(f"  {sec['name']:<12} {len(bars):>2} bars  hits/bar {h.sum():4.1f}  |{g[:4]}|{g[4:8]}|{g[8:12]}|{g[12:]}|")


if __name__ == "__main__":
    main()
