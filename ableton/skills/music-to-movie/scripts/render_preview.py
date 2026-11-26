"""Offline preview of a cue: every audio clip + the drum part on its kit samples, mixed and
laid under the picture. Lets you (and the user) check sync without Live.

Usage: render_preview.py cue.json <outdir>
Writes preview.wav and preview.mp4 (picture + new score; original audio dropped), and prints
for each locator how far the nearest loud onset in the mix is from it. MIDI instruments other
than the drum kit are NOT in the preview - it is the stems, drums and sound design only.
"""
import glob, json, os, subprocess, sys
import numpy as np
import soundfile as sf
import librosa

SR = 48000


def load(path):
    y, sr = sf.read(path, always_2d=True)
    if y.shape[1] == 1:
        y = np.repeat(y, 2, 1)
    if sr != SR:
        y = np.stack([librosa.resample(y[:, c].astype(np.float32), orig_sr=sr, target_sr=SR) for c in (0, 1)], 1)
    return y


def main():
    cue = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    beat = 60.0 / cue["bpm"]
    n = int((cue["length_beats"] * beat + 6) * SR)
    mix = np.zeros((n, 2))
    def add(y, t, db):
        s = int(round(t * SR))
        if s < 0: y = y[-s:]; s = 0
        y = y[:max(0, n - s)]
        mix[s:s + len(y)] += y * 10 ** (db / 20)
    video = None
    for tr in cue["tracks"]:
        if tr["kind"] == "video":
            video = tr["file"]; continue
        if tr.get("mute"):
            continue
        db = tr.get("db", 0)
        if tr["kind"] == "audio":
            for c in tr["clips"]:
                t = c["at_s"] - c.get("sync_s", 0) if "at_s" in c else c["beat"] * beat - c.get("pre_ms", 0) / 1000
                add(load(c["file"]), t, db + c.get("db", 0))
        elif tr.get("kit_dir"):
            pads = {}
            for f in glob.glob(os.path.join(tr["kit_dir"], "*.wav")):
                pads[os.path.basename(f)] = f
            order = {"kick": [36, 41, 43, 45, 47], "snare": [38, 37, 39, 40, 50], "hihat": [42, 44, 48, 51, 52, 53], "open_cymbal": [46, 49, 55, 57]}
            note_file = {}
            for kind, notes in order.items():
                fs = sorted(f for f in pads if f.startswith(tr.get("kit_prefix", "") + kind + "_"))
                note_file.update(dict(zip(notes, (pads[f] for f in fs))))
            cache = {}
            for p, s, d, v in cue["parts"][tr["part"]]:
                if p in note_file:
                    y = cache.setdefault(p, load(note_file[p]))
                    add(y, s * beat, db + 40 * np.log10(max(v, 1) / 127.0))
    peak = np.abs(mix).max()
    print("mix peak %.2f (%.1f dBFS)%s" % (peak, 20 * np.log10(peak), "  -> scaled to -1 dBFS for the preview" if peak > 0.89 else ""))
    if peak > 0.89:
        mix *= 0.89 / peak
    wav = os.path.join(out, "preview.wav"); sf.write(wav, mix, SR, subtype="PCM_24")
    m = mix.mean(1).astype(np.float32)
    env = librosa.onset.onset_strength(y=m, sr=SR, hop_length=256)
    fr = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=256, backtrack=False, delta=0.5)
    on = fr * 256 / SR
    rms = lambda t: 20 * np.log10(np.sqrt((m[int(max(0, t) * SR):int((t + 0.25) * SR)] ** 2).mean()) + 1e-9)
    print("locator            time    nearest onset   level before -> after")
    for bt, name in cue.get("locators", []):
        t = bt * beat
        if t > len(m) / SR - 1: continue
        d = on - t; j = np.abs(d).argmin() if len(on) else None
        print("  %-16s %6.3f s   %+5.0f ms        %5.1f -> %5.1f dB" % (name, t, d[j] * 1000 if j is not None else 0, rms(t - 0.3), rms(t)))
    if video:
        mp4 = os.path.join(out, "preview.mp4")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                            "-c:a", "aac", "-b:a", "256k", "-af", "apad", "-t", str(cue.get("video_end_s", 0) + 3.0), mp4],
                           capture_output=True, text=True)
        print(mp4 if r.returncode == 0 else r.stderr)


if __name__ == "__main__":
    main()
