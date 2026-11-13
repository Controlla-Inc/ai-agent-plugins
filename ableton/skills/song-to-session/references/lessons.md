# Lessons — why each rule exists

Each of these came from a real failure on the first song. Read the relevant one when a
result sounds wrong.

## Timing
- **Detectors misread tempo.** Controlla's analysis said 123 BPM, Song to MIDI 92; the song
  was 90.67. Parts at the wrong tempo drift a little more every bar. → `find_grid.py`.
- **"The music doesn't start on the 1."** A coarse offset (0.375 vs 0.364 s), mixing
  onset `backtrack` settings between the phase fit and the drum render, and 60%
  quantize. → one offset for everything, `backtrack=True` everywhere, full quantize.
- **Live auto-warp mis-stretches long stems**, sometimes seconds after import, and an
  arrangement copy made before analysis finishes gets warped later. A stable clip length
  is not proof analysis finished. → import unwarped, wait, force warping off, then copy;
  `live.py verify` 30 s later. A stale `.asd` can keep a wrong end marker → new filename.

## Parts
- **"Sounds like different parts."** Separate piano/guitar/other stems split one instrument
  across stems, so transcribing each produced the same line twice on different sounds;
  invented layers (pad, chord chart chords, synth lead) made it worse. → one Song to MIDI
  pass over the combined music stem; bass from the bass stem; nothing invented.
- **"Everything sounds busy."** Even accurate transcriptions are busy (every ghost note and
  re-strike). → measured patterns + held chords via `write_parts.py`; raw MIDI is kept as
  a reference clip only.
- **Bass an octave high at bar 13.** Nearest-note voice leading let the bass climb. → bass is
  pinned to one low octave (MIDI 28–39), never voice-led.
- **"Make the electric piano an octave down."** Mid-register keys crowd the vocal; go lower
  rather than higher when unsure.
- Song to MIDI labels R&B comping keys as "jazz guitar" — name tracks by what they sound
  like in the original, not by the General MIDI program.
- The snare stem carries kick bleed; weak snare hits on a kick are dropped.

## Live / connector
- **Remote Script changes need a full Live restart.** Opening a set re-instantiates the
  class but keeps the old module. Symptom: "Unknown command".
- **Loads can land on the wrong track** (pending hot-swap, async selection). Once a Drum
  Rack got replaced and two vocal compressors landed on the drums. → `Live.safe_load`
  diffs every track's devices after each load.
- The connector has no track mute → references are muted with a Utility (Mute = param 10).
- Locators: move the playhead, wait ~0.3 s, then create (otherwise the cue lands at the
  old playhead position).
- Return-track device parameters can't be set; use Live's default Reverb/Delay returns.
- **Playback starts from Live's start marker, not the playhead.** Level matching once
  measured the intro instead of the chorus and the piano fader swung ±28 dB between rounds.
  → `mix.py` jumps to the beat after starting playback and checks where the playhead is.
- Stock Live instrument presets can be ~15–20 dB quieter than a mixed stem (Clean Basic
  Guitar needed +14 dB); the fader stops at +6 dB, so `mix.py` adds the rest on a Utility.

## Second test song ("Slow Sunday", 2026-11-05)
Indie soul, generated "D major ~100" → measured A major, 100.00 BPM, bar 1 at 0.411 s
(vocal entering exactly on bar 5 confirmed the downbeat). Verse/chorus were 8-bar
progressions with a turnaround, so `loops.py` agreement was 56–71% and the loops were
written by hand from its grid. Everything else ran as scripted.
- Bulk notes go through the socket (`live.py`), 200 notes per call; MCP tool calls are too
  slow for thousands of notes.
- You can't save the set; ask the user to press ⌘S at hand-over and after big changes.

## Drum Rack files
- The connector can't put samples on pads, so the `.adg` is generated: clone the C1 pad of
  the Core Library "Boom Bap Kit" (ReceivingNote = 128 − MIDI note), rewrite only the
  FileRefs inside `<SampleRef>`, and **keep their `Id` attributes** — Live rejects the file
  without them.

## Third test song ("Lagos Rooftop", 2026-11-05)
Afro R&B, generated "A minor ~102" → measured 102.00 BPM, bar 1 at 0.630 s, A minor
(analysis said C major — the relative major). The piano stem was near-silent: the Rhodes sat
in the residual (music − piano − guitar), so that residual was the keys reference and voicing
source. Two-bar loop Dm7–Em7 | Am7 nearly throughout; Verse 1 swaps Em for C (written by hand).
- **Level matching ran backwards** (every round widened the gap): `mix.py` calibrated meter→dB
  on the first group's track — the drums — and bursty drum meters read *quieter* at 0 dB than
  at −6 dB. → calibrate on a sustained part (`"calibrate_on"` in mix.json), refuse a
  calibration where 0 dB doesn't read louder.
- **A boost Utility came up muted** (Mute = param 10, the REF-mute switch), so the drums
  read silent and the loop pushed +35 dB into a muted device. → `_set_boost` clears Mute;
  a re-run resets leftover boosts to 0 dB first.
- **"The MIDI keys don't follow the Keys stem."** Harmony was right (chroma per chord matched),
  timing wasn't: chords.py's half-bar chart put changes on beats 1/3, the record changed
  ~a beat later (keys, guitar AND bass all lagged the chart by 3–4 sixteenths).
  → `snap_changes.py` fits each change point against the stem and snaps every change of a
  chord to that chord's usual spot (consistent, not per-change jitter): 0.726 → 0.757.
- **The user edits the set while you work.** They inserted a track (a percussion loop on a
  copy of a REF track) and every index below it moved; `place_part(6, …)` hit an audio
  track. → after the build, always resolve tracks BY NAME (`live.py tracks`), never reuse
  indices from earlier in the session.
- **"Put my sample loop in time."** A Splice loop dropped in unwarped plays at its own tempo
  (104 in a 102 song: 15.69 beats instead of 16) and was placed a beat late. → check the
  file is N bars at the tempo in its name, re-import it WARPED (`create_audio_clip`
  warping True), confirm the clip length is exactly N×4 beats (= markers at file start,
  not at the first transient), and place it on a bar line.

## Fourth test song ("Booty Got Me Weak", 2026-11-05)
The user's OWN Logic song (a 48 kHz bounce), not a generation. G minor, 80.00 BPM, bar 1 at
0.00 s, one loop E♭maj7 (1 bar) | Gm7 (1 bar) | Dm7 (2 bars) for all 63 bars. ~683 credits.
- **Both detectors were wrong the same way**: analysis 107.7, Song to MIDI 108. find_grid's
  top pick followed the hint (105, lock 0.35); the true 80 had lock 0.96, and the Logic
  project's MetaData.plist said 80. → choose by grid lock; for a DAW song read the project
  tempo; a bounce starts at bar 1 (offset 0). find_grid's downbeat put bar 1 on beat 3
  (trap kick pattern) — the snare-on-2-&-4 histogram settled it.
- **Mixed sample rates** (48 kHz bounce, instrumental and vocals; 44.1 kHz for every
  other stem) made align_stems assert. → it now resamples to the most common rate.
- **"There's a melody MIDI that's not present."** Song to MIDI returned the music stem as
  one piano track; the hook riff (16th A/B♭ trill, D5–C5–B♭ lead-ins) was inside it, and
  write_parts kept only held chords. → step 4.8 + `melody_line.py`: short upper-register
  notes, skyline, monophonic, on their own track. Sparse is about harmony; a hook the
  listener remembers must survive.
- **Chroma voicings picked up a phantom C♯** (melody/vocal leakage) in Gm and Dm; the
  transcription never played it. → cross-check voicings.py against the transcription.
- **Chrome `file_upload` refuses paths outside the session folders** → copy the MP3s to the
  scratchpad first.
- **basic-pitch fallback crashed** on `scipy.signal.gaussian` (removed in new SciPy) → pin
  scipy<1.13 if you need it; the web job finished in ~6 min anyway.
- The stock E-Piano needed ~+15 dB to reach the music stem's level (fader +6, Utility +9) —
  the original keys were a louder synth; the user swapped in their own keys plugin at once.
- **"How can we do this with Logic Pro?"** Logic has no API, so it's an export:
  `logic_export.py` writes a format-1 MIDI file (tempo, key, section markers, named tracks),
  the aligned stems, the kit renamed by note, and a README. Gotcha: mido writes meta text as
  Latin-1, so an en dash in a track name crashed the export → it normalises dashes and quotes.
