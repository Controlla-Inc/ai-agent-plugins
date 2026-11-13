"""How well do MIDI parts match the audio? Chroma agreement per half-beat.

score(notes, wav, bpm): cosine similarity between the part's pitch-class content and
the audio's chroma, averaged over half-beats where the part plays (notes in beats,
audio aligned so 0 = beat 0). Also returns coverage: share of half-beats where the
audio is clearly sounding that the part also plays.
"""
import librosa
import numpy as np

SR, HOP = 22050, 512


def audio_chroma(wav, bpm, n_slots):
    y = librosa.load(wav, sr=SR)[0]
    c = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    fps, slot = SR / HOP, 30.0 / bpm  # half a beat in seconds
    out, loud = np.zeros((n_slots, 12)), np.zeros(n_slots)
    for i in range(n_slots):
        a, z = int(i * slot * fps), int((i + 1) * slot * fps)
        if a >= c.shape[1]:
            break
        out[i] = c[:, a:z].mean(1)
        loud[i] = rms[a:z].mean()
    return out, loud


def midi_chroma(notes, n_slots):
    out = np.zeros((n_slots, 12))
    for p, s, d, v in notes:
        a, z = int(s * 2), int(np.ceil((s + d) * 2))
        out[a:min(z, n_slots), p % 12] += v / 127.0
    return out


def score(notes, wav, bpm, length_beats):
    n = int(length_beats * 2)
    ac, loud = audio_chroma(wav, bpm, n)
    mc = midi_chroma(notes, n)
    plays = mc.sum(1) > 0
    sounding = loud > 0.2 * np.median(loud[loud > 0]) if (loud > 0).any() else loud > 0
    num = (ac * mc).sum(1)
    den = np.linalg.norm(ac, axis=1) * np.linalg.norm(mc, axis=1) + 1e-9
    sim = num / den
    return {
        "match": float(sim[plays].mean()) if plays.any() else 0.0,
        "coverage": float((plays & sounding).sum() / max(sounding.sum(), 1)),
        "plays_where_silent": float((plays & ~sounding).sum() / max(plays.sum(), 1)),
    }
