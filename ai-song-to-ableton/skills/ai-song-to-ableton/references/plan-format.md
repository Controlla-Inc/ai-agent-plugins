# plan.json, layout.json, mix.json — worked example

The example is the first song built this way ("Late Night Drive": modern R&B, F# minor,
90.67 BPM, bar 1 at 0.364 s). The user approved this version after several rounds.

## plan.json

You write `bpm`, `key`, `sections` (from the bar_levels table) and `parts`; `loops.py`
fills each section's `loop` (`[[chord, beats], ...]`) — edit it if a loop looks wrong.

```json
{
  "bpm": 90.67, "key": "F#m",
  "sections": [
    {"name": "Intro",     "bars": [1, 4]},
    {"name": "Verse 1",   "bars": [5, 12]},
    {"name": "Chorus 1",  "bars": [13, 19]},
    {"name": "Inst 1",    "bars": [20, 24]},
    {"name": "Verse 2",   "bars": [25, 32]},
    {"name": "Chorus 2",  "bars": [33, 40]},
    {"name": "Interlude", "bars": [41, 44]},
    {"name": "Bridge",    "bars": [45, 48]},
    {"name": "Chorus 3",  "bars": [49, 56]},
    {"name": "Inst 2",    "bars": [57, 60]},
    {"name": "Outro",     "bars": [61, 68]}
  ],
  "parts": [
    {"name": "Piano", "style": "held", "range": [52, 72], "voicing": "piano", "velocity": 74, "audible": "piano"},
    {"name": "Electric piano", "style": "held", "range": [43, 62], "voicing": "piano", "velocity": 70, "audible": "piano"},
    {"name": "Guitar", "style": "hits", "hits": [0.75, 2.75], "hit_length": 0.4, "range": [60, 76],
     "voicing": "guitar", "velocity": 88, "audible": "guitar",
     "overrides": {"Inst 1": {"hits": [0.75, 1.25, 2.75]}, "Inst 2": {"hits": [0.75, 1.25, 2.75]}}},
    {"name": "Bass", "style": "bass", "range": [28, 39], "velocity": 100, "audible": "bass",
     "pattern": [[0, 1.25], [1.5, 1.5]],
     "overrides": {"Intro": {"held": true}, "Bridge": {"held": true}, "Outro": {"held": true}}}
  ]
}
```

What the measurements said and how it became the parts:
- bass ~2 hits/bar, the 1 and the "and" of 2 anticipating the next chord → `pattern` + `anticipate`;
- piano ~1 attack per chord with long sustain → `held`;
- guitar short chops on the 16th before beats 2 and 4 → `hits: [0.75, 2.75]`;
- the user asked for the electric piano an octave down → its `range` is an octave under the piano.

## layout.json

```json
{
  "tracks": [
    {"kind": "midi", "name": "Drums – cloned kit", "part": "Drums",
     "load": ["query:UserLibrary#Presets:Instruments:Drum%20Rack:CV%20Drums%20%E2%80%93%20Late%20Night%20Drive.adg"]},
    {"kind": "ref",  "name": "REF – Drums (stem)", "file": "<aligned>/drums.wav"},
    {"kind": "midi", "name": "Bass", "part": "Bass", "load": ["<the user's bass, e.g. a SubLab/State Machine URI, or query:Sounds#Bass:...>"]},
    {"kind": "ref",  "name": "REF – Bass (stem)", "file": "<aligned>/bass.wav"},
    {"kind": "midi", "name": "Piano", "part": "Piano", "load": ["<piano URI>"]},
    {"kind": "midi", "name": "Electric piano", "part": "Electric piano", "load": ["<EP URI>"]},
    {"kind": "midi", "name": "Guitar", "part": "Guitar", "load": ["<guitar URI>"]},
    {"kind": "ref",  "name": "REF – Keys + guitar (stem)", "file": "<aligned>/music.wav"},
    {"kind": "audio","name": "Vocals", "file": "<aligned>/vocals.wav"},
    {"kind": "ref",  "name": "REF – Full original mix", "file": "<aligned>/full.wav"}
  ],
  "master": []
}
```

## mix.json

The first mix the user kept (send values are dB on Live's default Reverb/Delay returns):

```json
{
  "measure_at_beat": 128,
  "tracks": {
    "Drums – cloned kit": {"load": ["query:AudioFx#Drum%20Buss:FileId_8091", "query:AudioFx#Glue%20Compressor:FileId_7904"], "reverb_db": -26},
    "Bass":   {"eq": [[1, "lowcut48", 30, 0, 0.71], [2, "bell", 250, -2.0, 0.9]], "load": ["query:AudioFx#Glue%20Compressor:FileId_7901"]},
    "Piano":  {"eq": [[1, "lowcut48", 140, 0, 0.71], [2, "bell", 350, -2.0, 0.9]], "pan": -0.15, "reverb_db": -20},
    "Electric piano": {"eq": [[1, "lowcut48", 150, 0, 0.71], [2, "bell", 400, -2.0, 0.9]], "pan": -0.30, "reverb_db": -18},
    "Guitar": {"eq": [[1, "lowcut48", 180, 0, 0.71], [2, "bell", 2500, 1.5, 1.0], [8, "highcut12", 9000, 0, 0.71]],
               "load": ["query:AudioFx#Chorus-Ensemble:FileId_8187"], "pan": 0.35, "reverb_db": -18, "delay_db": -17},
    "Vocals": {"eq": [[1, "lowcut12", 100, 0, 0.71], [2, "bell", 300, -2.5, 0.9], [3, "bell", 3000, 2.0, 0.8], [4, "highshelf", 10000, 1.5, 0.71]],
               "load": ["query:AudioFx#Compressor:FileId_8183", "query:AudioFx#Compressor:FileId_8172"],
               "reverb_db": -14, "delay_db": -20, "nudge_db": 1.5}
  },
  "level_groups": {
    "drums": [["Drums – cloned kit"], "REF – Drums (stem)"],
    "bass":  [["Bass"], "REF – Bass (stem)"],
    "keys":  [["Piano", "Electric piano", "Guitar"], "REF – Keys + guitar (stem)"]
  }
}
```
FileId presets above were Live 12.4 Standard's (Drum Sharpener, Gentle Two Buss, Bass Punch,
Sustained Lead Vocal, De-esser, Chorus Subtle Funk) — verify names in the browser first.
