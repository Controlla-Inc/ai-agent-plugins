"""Cue sheet for TRAILER CLIP.mp4 -> cue.json (run with the analysis venv). Edit and re-run."""
import json, os
W = os.path.dirname(os.path.abspath(__file__))
BPM = 113.0; BEAT = 60 / BPM
b = lambda sec: sec / BEAT                       # picture time -> beat
raw = json.load(open(f"{W}/analysis/raw_notes.json"))
SB = 60 / 113.01; MOFF = 0.367                    # song beat, and where transcribed notes sit on the grid
sx = json.load(open(f"{W}/SFX/sfx.json"))
CS = f"{W}/Cue stems"

# picture events (seconds)
EYES, FIGURE, STORM, ENGULF, HER, EMBRACE, CLOSE, TITLE, END = 0.0, 1.1, 2.767, 3.767, 4.767, 5.9, 7.1, 8.5, 10.73

def take(track, a, c, shift, lo=0, hi=127, legato=False, vel=None, minlen=0.25):
    """Transcribed notes of song beats [a, c) moved to cue beats (+shift), on a 1/12-beat grid."""
    out = []
    for t, d, p, v in raw[track]:
        x = (t - MOFF) / SB
        if a - 0.04 <= x < c - 0.04 and lo <= p <= hi:
            out.append([p, round((x - a + shift) * 12) / 12, max(minlen, round(d / SB * 12) / 12), vel or min(127, v + 10)])
    out.sort(key=lambda n: (n[1], n[0]))
    if legato:
        starts = sorted({n[1] for n in out})
        for n in out:
            nxt = [s for s in starts if s > n[1] + 1e-6]
            if nxt and n[2] < 1.0:
                n[2] = round(nxt[0] - n[1], 4)
    return out

# ---- MIDI parts -----------------------------------------------------------------------
high = take("Viola", 250, 259, 0, lo=57, legato=True)                       # A pedal, the scale run, the fall
high += [[p + 12, s, d, 84] for p, s, d, v in take("Viola", 217, 222.96, 10, legato=True)]   # run-up, octave double
high += [[74, 16, 8, 110], [81, 16, 8, 104]]                                 # title: D5 + A5 held
low = take("Cello", 250, 259, 0, hi=57) + take("Contrabass", 250, 259, 0)
low += [[38, 9, 4, 112], [26, 9, 4, 112]]                                    # the landing on D under her entrance
low += take("Viola", 217, 222.96, 10, legato=True, vel=96)                   # the rising line under the embrace
low += [[26, 16, 8, 120], [38, 16, 8, 120], [50, 16, 8, 112]]                # title: D1 D2 D3
horn_chord = lambda at, ln, v: [[p, at, ln, v] for p in (50, 57, 62, 65)]    # D3 A3 D4 F4, as transcribed
horn_tune = lambda at: [[57, at + 2, 0.95, 96], [57, at + 3, 0.5, 96], [58, at + 3.5, 0.6, 100], [67, at + 4.1, 0.7, 104], [64, at + 4.8, 1.2, 100]]
horns = horn_chord(9, 2, 100) + horn_tune(9) + horn_chord(16, 2, 118) + horn_tune(16)

K, K2, T1, T2, SUB, SN, SN2, CR = 36, 47, 41, 43, 45, 38, 39, 49           # pads of the cloned kit
def hit(at, v, pads): return [[p, round(at, 3), 0.5, v] for p in pads]
drums = []
drums += hit(b(FIGURE), 96, (SUB, SN))                                      # cut to the figure
drums += hit(5.0, 84, (T1,)) + hit(b(STORM), 124, (K, SUB, SN, CR))         # ka-DON on the storm
for at, v in ((5.73, 104), (6.5, 108), (7.0, 122), (8.0, 112)):             # the stem's own big hits, doubled
    drums += hit(at, v, (K, T2) if v < 120 else (K, SUB, SN2))
for i, at in enumerate((8.25, 8.5, 8.625, 8.75, 8.875)):                    # roll into the cut
    drums += hit(at, 70 + 12 * i, (T1 if i % 2 else T2,))
drums += hit(b(HER), 114, (K, K2, SUB, SN, SN2, CR))                        # the wave lands / cut to her
drums += hit(b(EMBRACE), 62, (SUB,)) + hit(b(CLOSE), 70, (SUB,))            # two heartbeats
for i, at in enumerate((14.5, 15.0, 15.25, 15.5, 15.625, 15.75, 15.875)):   # crescendo roll into the title
    drums += hit(at, 58 + 10 * i, (T1 if i % 2 else T2,) + ((SN,) if i > 3 else ()))
drums += hit(b(TITLE), 127, (K, K2, SUB, SN, SN2, CR, 46))                  # TITLE
drums += hit(17.5, 100, (T2, SUB)) + hit(18.0, 112, (K, SUB, SN2)) + hit(20.0, 118, (K, K2, SUB, SN))

# ---- sound design: [sound, picture time its sync point lands on, gain dB] ----------------
def fx(name, at_s, db=0.0): return {"file": sx[name]["file"], "at_s": at_s, "sync_s": sx[name]["sync_s"], "db": db, "name": name}
impacts = [fx("boom", EYES, -5), fx("impact", STORM, -2), fx("impact", HER, -4), fx("boom", EMBRACE, -8),
           fx("boom", CLOSE, -6), fx("impact_big", TITLE, 0)]
braams = [fx("braam", STORM, -3), fx("braam_long", TITLE, 0)]
moves = [fx("whoosh", FIGURE, -4), fx("riser", STORM, -4), fx("sub_drop", ENGULF, -3), fx("riser_short", HER, -6),
         fx("whoosh", EMBRACE, -10), fx("reverse", TITLE, -2)]
atmos = [fx("wind", EYES, 0), fx("shimmer", HER + 0.15, 0)]

UT = "query:AudioFx#Utility"
def expr(points): return [{"device": "Utility", "param": "Gain", "points": points}]
tracks = [
    {"name": "VIDEO – TRAILER CLIP", "kind": "video", "file": f"{W}/TRAILER CLIP.mp4", "mute": True},
    {"name": "Trailer drums – cloned kit (MIDI)", "kind": "midi", "part": "Drums", "db": -7,
     "load": ["query:UserLibrary#Presets:Instruments:Drum%20Rack:CV%20Drums%20%E2%80%93%20Trailer%20Cue.adg"],
     "kit_dir": os.path.expanduser("~/Music/Ableton/User Library/Samples/Controlla Kits/Trailer Cue"), "kit_prefix": "TC "},
    {"name": "Drums – song stem", "kind": "audio", "db": -1, "clips": [
        {"file": f"{CS}/drums A build.wav", "beat": 0, "pre_ms": 15}, {"file": f"{CS}/drums C title.wav", "beat": 16, "pre_ms": 15}]},
    {"name": "High strings (MIDI + expression)", "kind": "midi", "part": "High strings", "db": -9,
     "load": ["query:Sounds#Strings:FileId_4824", UT],
     "automation": expr([[0, -14], [1, -10], [4.9, 0], [9, 0], [9.9, -16], [10, -16], [15.9, 3], [16, 0], [18, 0], [24, -24]])},
    {"name": "Low strings (MIDI + expression)", "kind": "midi", "part": "Low strings", "db": -8,
     "load": ["query:Sounds#Strings:FileId_6447", UT],
     "automation": expr([[0, -8], [5, 0], [9, 2], [10, -12], [15.9, 3], [16, 2], [18, 0], [24, -24]])},
    {"name": "Horns (MIDI + expression)", "kind": "midi", "part": "Horns", "db": -9,
     "load": ["query:Sounds#Brass:FileId_5216", UT],
     "automation": expr([[0, -12], [9, -8], [9.75, 1], [11, -3], [14, -4], [15.9, -12], [16, -4], [16.75, 3], [18, 0], [24, -24]])},
    {"name": "Music – song stem (build + title)", "kind": "audio", "db": 0, "clips": [
        {"file": f"{CS}/music A build.wav", "beat": 0, "pre_ms": 15}, {"file": f"{CS}/music C title.wav", "beat": 16, "pre_ms": 15}]},
    {"name": "Music – song stem (run-up)", "kind": "audio", "db": 0, "clips": [{"file": f"{CS}/music B run-up.wav", "beat": 10, "pre_ms": 15}]},
    {"name": "Bass – song stem", "kind": "audio", "db": -2, "clips": [
        {"file": f"{CS}/bass A build.wav", "beat": 0, "pre_ms": 15}, {"file": f"{CS}/bass C title.wav", "beat": 16, "pre_ms": 15}]},
    {"name": "SFX – Impacts + booms", "kind": "audio", "db": -4, "clips": impacts},
    {"name": "SFX – Braams", "kind": "audio", "db": -9, "clips": braams},
    {"name": "SFX – Risers + whooshes", "kind": "audio", "db": -8, "clips": moves},
    {"name": "SFX – Atmos (wind, shimmer)", "kind": "audio", "db": -14, "clips": atmos},
    {"name": "REF – Full generated song (muted, from bar 9)", "kind": "audio", "db": -3, "mute": True,
     "clips": [{"file": f"{CS}/full song (from bar 1).wav", "beat": 32}]},
]
TRIM = -7.0                                         # headroom: the title stacks ~15 sources
for t in tracks:
    if "db" in t: t["db"] += TRIM
cue = {"title": "Trailer Cue", "bpm": BPM, "key": "Dm", "length_beats": 28, "video_end_s": END,
       "tracks": tracks, "parts": {"Drums": drums, "High strings": high, "Low strings": low, "Horns": horns},
       "locators": [[0, "Eyes"], [b(FIGURE), "Figure vs storm"], [b(STORM), "STORM HIT"], [b(ENGULF), "Engulfed"],
                    [b(HER), "She walks in"], [b(EMBRACE), "Embrace"], [b(CLOSE), "Close-up"], [b(TITLE), "TITLE"],
                    [b(END), "Picture ends"], [32, "Full song (reference)"]]}
json.dump(cue, open(f"{W}/cue.json", "w"), indent=1)
for k, v in cue["parts"].items():
    print(k, len(v), "notes", "beats %.2f-%.2f" % (min(n[1] for n in v), max(n[1] + n[2] for n in v)))
