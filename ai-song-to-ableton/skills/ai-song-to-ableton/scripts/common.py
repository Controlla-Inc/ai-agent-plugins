"""Shared helpers: audio loading, chord names, voicing, MIDI note cleanup.

Notes everywhere are [pitch, start_beat, dur_beats, velocity], beat 0 = bar 1 beat 1.
"""
import librosa
import numpy as np
import soundfile as sf

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PC = {n: i for i, n in enumerate(NAMES)}
PC.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})
SHAPES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
          "dim": (0, 3, 6), "m7b5": (0, 3, 6, 10), "sus2": (0, 2, 7), "sus4": (0, 5, 7), "6": (0, 4, 7, 9),
          "m6": (0, 3, 7, 9), "9": (0, 4, 7, 10, 2), "maj9": (0, 4, 7, 11, 2), "m9": (0, 3, 7, 10, 2), "add9": (0, 4, 7, 2)}
MAJOR, MINOR = (0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 8, 10)


def parse_chord(name):
    """'F#m7' -> (6, 'm7'). Unknown qualities fall back to major/minor triad."""
    root = name[:2] if len(name) > 1 and name[1] in "#b" else name[:1]
    q = name[len(root):]
    if q not in SHAPES:
        q = "m" if q.startswith("m") and not q.startswith("maj") else ""
    return PC[root], q


def chord_pcs(name, triad=False):
    r, q = parse_chord(name)
    sh = SHAPES[q][:3] if triad else SHAPES[q]
    return [(r + i) % 12 for i in sh]


def voice(pcs, prev, lo, hi):
    """Place pitch classes in [lo, hi], each as close as possible to the previous chord's
    centre (smooth voice leading). Never use this for bass – it drifts octaves."""
    centre = sum(prev) / len(prev) if prev else (lo + hi) / 2
    return sorted({min((p for p in range(lo, hi + 1) if p % 12 == pc), key=lambda p: abs(p - centre)) for pc in pcs})


def load_mono(path, sr=22050, offset=0.0):
    y, s = sf.read(str(path), always_2d=True)
    y = y.mean(axis=1).astype(np.float32)
    if s != sr:
        y = librosa.resample(y, orig_sr=s, target_sr=sr)
    return y[int(offset * sr):]


def bar_db(y, sr, bpm):
    bar = int(4 * 60.0 / bpm * sr)
    return np.array([20 * np.log10(np.sqrt(np.mean(y[i:i + bar] ** 2)) + 1e-9) for i in range(0, len(y), bar)])


def clean_notes(notes, bpm, offset=0.0, grid=0.25, min_beats=0.1, min_vel=20):
    """pretty_midi notes -> cleaned beat notes: shift by offset (s), quantize starts FULLY to
    1/16 (partial quantize sounded late/early against the grid), drop blips and ghosts,
    and trim same-pitch overlaps."""
    spb = 60.0 / bpm
    out = []
    for n in notes:
        s, e = (n.start - offset) / spb, (n.end - offset) / spb
        if s < 0 or e - s < min_beats or n.velocity < min_vel:
            continue
        out.append([n.pitch, round(round(s / grid) * grid, 4), round(max(e - s, grid * 0.5), 4), int(n.velocity)])
    out.sort(key=lambda x: (x[1], x[0]))
    last = {}
    for n in out:
        if n[0] in last and last[n[0]][1] + last[n[0]][2] > n[1]:
            last[n[0]][2] = max(0.05, round(n[1] - last[n[0]][1], 4))
        last[n[0]] = n
    return out


def onset_hits(path, offset=0.0, sr=44100, hop=256, delta=0.25):
    """[(time_s, velocity 30..127)] with backtrack=True – the same setting find_grid.py uses."""
    y = load_mono(path, sr, offset)
    if np.abs(y).max() < 1e-3:
        return []
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    fr = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, delta=delta, backtrack=True)
    if len(fr) == 0:
        return []
    t = librosa.frames_to_time(fr, sr=sr, hop_length=hop)
    st = env[np.minimum(fr + 2, len(env) - 1)]
    vel = np.clip(40 + 87 * st / (np.percentile(st, 95) or 1), 30, 127)
    return list(zip(t.tolist(), vel.tolist()))
