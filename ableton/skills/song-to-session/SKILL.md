---
name: song-to-session
description: Turn an AI-generated song (Controlla Voice) into a ~70%-finished, editable Ableton Live session with no clicks from the user — generate the song, split stems, transcribe to MIDI, clone the drum kit into a Drum Rack, write clean held parts on real instruments, line everything up on the grid, add muted reference stems, and do a first mix (or, for Logic Pro users, export the same draft as a MIDI file + aligned stems + kit + README). Use this whenever someone wants an AI song "in Ableton" (or in Logic Pro), a "first draft"/"starting point" session from a prompt or an existing track (including the user's own bounce from Logic or another DAW), to rebuild a song's parts as MIDI with new instruments, to replace drums with a cloned kit, or to continue/fix/mix a draft this pipeline made — even if they don't name the skill, and even for one step of it (e.g. "make the bass sit lower", "add the stems underneath as references", "mix it").
compatibility: macOS (or Windows) + Ableton Live 12.0.5+ (Standard is enough), and an AI agent that can run local commands (Claude Code, Codex, Cursor, GitHub Copilot and others) with the Controlla Voice connector and the AbletonMCP connector installed via connector/install.sh (Claude Code: the plugin's /ableton:setup); Claude in Chrome only as a fallback for the Song to MIDI step.
---

# AI song → Ableton draft

The promise to the user: **they touch nothing until a draft is open in Live** — tempo right,
everything starting on the 1, parts that sound like the record but simpler, their own
instruments, reference stems underneath, and a sensible first mix. Everything below exists
because a version without it failed in front of a real user (see `references/lessons.md`).

Work in a per-song folder (e.g. `~/Music/Controlla Drafts/<Title>/` for audio the user keeps,
and a scratch folder for JSON). Scripts live in this skill's `scripts/`; run them with the
analysis venv: `PY=~/.local/share/ai-song-to-ableton/venv/bin/python`, from the `scripts/` dir.

## 0. Preflight (every time)

1. `bash connector/install.sh --check`. If anything is missing, walk the user through
   `references/setup.md` (plugin installs: just run `/ableton:setup`) (one-time; needs them to restart Live and pick the control surface).
2. `$PY scripts/live.py tracks` must answer. If it times out, Live isn't open or "AbletonMCP"
   isn't selected as a Control Surface.
3. **Live only loads Remote Script code at startup.** If you (or install.sh) changed the
   script, the user must quit and reopen Live — opening another set is not enough. Commands
   like `delete_device` / `set_mixer` returning "Unknown command" mean exactly this.
4. Ask the user (once, then remember) which instruments they like for drums/bass/keys/
   guitar/etc. Third-party plugins load with default patches only (presets inside plugins
   can't be picked), so prefer their choice or a good Live Core Library preset. If they
   later swap an instrument themselves, keep their swap.

## 1. Get the song and its pieces (Controlla connector)

- New song: `create_song_generation` (song idea, style, BPM/key targets — the targets are
  often ignored, so measure later). Existing audio: `import_audio` / `upload_audio`
  (copy it into the song folder first; `upload_audio` + curl PUT with every returned header).
- **The user's own DAW song** (e.g. a Logic bounce) carries the real tempo: for Logic read
  `BeatsPerMinute` from `<Project>.logicx/**/MetaData.plist` (`plutil -p`). A bounce usually
  starts exactly at bar 1, so expect offset ≈ 0.0 s — still confirm with find_grid (step 2).
- `analyze_upload` on the result, then in parallel:
  - `create_stem_split` with `["vocals", "instrumental", "kick", "snare", "cymbals"]`
    (drum timing + the instrumental),
  - `create_stem_split` with `["drums", "bass", "piano", "guitar", "lead_vocal", "background_vocals"]`
    (per-instrument references and level maps),
  - `create_drum_kit` (the cloned one-shots, ranked best-first per type).
- Poll `get_job`; download outputs with curl into the song folder.

## 2. Find the real grid — never trust a detector's BPM

`$PY find_grid.py kick.wav snare.wav cymbals.wav --hint <analysis BPM>`
Pick the candidate that matches the genre's feel (half/double tempo shows up too). It prints
BPM to two decimals and the offset (s) where bar 1 beat 1 sits. Pick by **grid lock**, not
by closeness to the hint: on "Booty Got Me Weak" the hint (107.7) won with lock 0.35 while the
true 80 BPM had 0.96 — both detectors (analysis and Song to MIDI) said ~108. The downbeat
pick assumes kick on 1 & 3; for trap/half-time kicks it can land on beat 3 — check the
snare sits on 2 & 4 (a 16th-position histogram of kick/snare onsets mod one bar) and that the
offset agrees with the DAW's bar 1. Then trim everything:

`$PY align_stems.py <offset> "<folder>/Stems (aligned)" full=<song.wav> instrumental=... drums=... bass=... piano=... guitar=... vocals=... kick=... snare=... cymbals=... --music instrumental=drums,bass`

From here on every file starts on beat 0, so nothing needs shifting in Live. `music.wav`
(instrumental − drums − bass) is the harmonic layer as one file. Mixed sample rates are
normal (48 kHz bounce/instrumental/vocals vs 44.1 kHz drum and instrument stems) —
align_stems resamples to the most common rate.

## 3. Transcribe (Song to MIDI, in Chrome)

The Controlla connector now lists a `create_song_to_midi` tool (seen 2026-11-05, not yet used here) — try it first and fall back to the web app if it misbehaves: `https://voice.controlla.xyz/app/song-to-midi`.
Browser uploads are capped at 10 MB, so encode first:
`$PY -c "import soundfile as sf; y,sr=sf.read('music.wav'); sf.write('music.mp3', y, sr, format='MP3')"`.
Chrome's `file_upload` only reads files inside the session's folders — copy the MP3s into
the scratchpad (unique names, e.g. `<song>_music.mp3`) and upload from there.
An announcement pop-up can open on load and swallow your typing — check the Tempo field
really shows your BPM before pressing Convert. The page also auto-detects a tempo after
upload; type yours after that and confirm it stuck.
Upload the **aligned `music.mp3`** (one pass — it labels the instruments itself; transcribing
piano/guitar/other stems separately duplicates parts across sounds), type the measured BPM
into the Tempo field, convert, download. Do the same for `bass.wav` (a much better bass
than the full mix) and optionally `vocals.wav` for a melody guide.
Chrome stops saving after a few downloads: read the `storage.googleapis.com` URL from
`read_network_requests` and curl it. Snapshot `~/Downloads` before, so you never grab a
stale file. A music-stem job took ~6 min. If jobs stall >10 min, `basic-pitch`
(`uv pip install 'basic-pitch[onnx]' 'setuptools<70'`) is a local fallback — but with a
recent SciPy it crashes (`scipy.signal has no attribute 'gaussian'`); pin `scipy<1.13` in
the venv before relying on it.

**Song to MIDI returns the music stem as ONE track ("Acoustic Grand Piano") — chords and
the melody/hook riff mixed together.** Step 4 rewrites harmony as held chords, so the
melody disappears unless you pull it out (step 4.8). The user noticed immediately.

Clean and score into a separate file: `$PY midi_parts.py raw_parts.json <bpm> 0 music.mid piano.wav "piano=Piano raw"`
(substring matches the instrument names inside the file; `*` = all; score against that
instrument's own stem). These raw parts are references — accurate but busy, and in both
test songs the rewritten parts from step 4 matched the stems *better* (0.62–0.71 vs
0.51–0.58). After the build, drop them into a free Session slot on their track
(`Live().write_notes(t, slot, notes, length, "Piano raw (reference)")`) so the user can A/B.

## 4. Understand the song, then write the parts people want to hear

Users consistently want **sparse, held parts** ("everything sounds busy"). The raw
transcription is the evidence; the parts you deliver are rewritten from it:

1. `$PY bar_levels.py <bpm> levels.json drums=... bass=... piano=... guitar=... lead=...` →
   read the table and write the section list (`Intro 1-4, Verse 1 5-12, ...`) into
   `plan.json` (see `references/plan-format.md`). Sections come from who is playing — this
   is judgement, do it yourself.
2. `$PY chords.py instrumental.wav drums.wav bass.wav <bpm> <key> chart.json` (key from
   `analyze_upload` – the generation's target key is often ignored), then
   `$PY loops.py plan.json chart.json` → one chord loop per section. Under ~70% agreement it
   prints the section's raw half-bar grid: that usually means a long progression (an 8-bar
   verse ending in a turnaround) rather than a 2-bar loop — read the grid and write the
   section's full progression as its `loop` by hand. Check each loop's beats add up to the
   section length.
3. `$PY rhythms.py plan.json levels.json bass=... piano=... guitar=...` → how often and
   where each instrument hits. Turn that into each part's style/pattern in plan.json.
4. `$PY voicings.py plan.json voicings.json piano=Piano.wav:4 guitar=Guitar.wav:3` → the
   real voicings; strip any obvious bleed note. Cross-check against the raw transcription's
   pitch classes per chord: on "Booty Got Me Weak" chroma put a C♯ in Gm and Dm (from the
   vocal/melody line, not the chord) that the transcription never played — the transcription
   wins; write the voicing by hand (there: E♭maj7, Gm7, Dm7).
5. `$PY write_parts.py plan.json parts.json levels.json voicings.json` — prints attacks
   per bar for each part; around 1–2 for keys and bass is the target for this style.
6. **Snap chord changes to the stem**: `$PY snap_changes.py parts.json <Part> <aligned stem.wav> <bpm>`
   for every held/chord part (keys, guitar, bass). The chart puts changes on beats 1 and 3;
   many songs change later (Lagos Rooftop: Dm on beat 2, Em on the "a" of 3, Am on the
   "and" of 1) and the part then switches a beat early – "the MIDI doesn't follow the
   stem". It prints where each chord really changes and the before/after match.
   Then re-time the rhythmic parts with `$PY follow_harmony.py parts.json Keys "Keys v2" <Guitar|Bass> <chord|bass> voicings.json <stem> <bpm>`
   — per note the STEM decides old vs corrected chord (instruments don't share one timing:
   on Lagos Rooftop guitar followed the late Rhodes, the bass already hit the root on 1).
7. Drums: `$PY drums_midi.py parts.json <bpm> 0 kick=<aligned kick> snare=... hats=<aligned cymbals>`
   and `$PY kit_rack.py <kit_dir> "<Title>"` (prints the Drum Rack's browser URI).
8. **Melody / hook riff — never skip this check.** Print the raw part's top line per bar
   (highest note at each onset). A figure that repeats every bar or loop (Booty Got Me Weak:
   D5–C5–B♭ lead-in, then an A/B♭ 16th trill closing each bar) is an instrumental melody
   that step 5 just threw away. Extract it with
   `$PY melody_line.py raw_parts.json "<raw part>" parts.json --name Melody` (short notes
   ≥ F4, skyline, monophonic) and give it its own MIDI track in layout.json, under the keys
   reference, on a neutral lead preset (e.g. `Sounds#Synth Lead` "Basic Sine Drive Lead").
   No melody-only stem exists, so set its level by ear (~−6 dB) and say so. If the riff
   follows the vocal instead, transcribe `lead.mp3` (Song to MIDI) for the topline.

Rules that came from user corrections: bass lives in ONE low octave (`range [28, 39]`);
keys an octave lower than you'd guess usually sit better; chords held to the next change;
parts only play in bars where their stem is audible in the original; nothing invented —
no pad, lead or extra layer that isn't in the record unless the user asks. The converse
also holds: **nothing that IS in the record may go missing** — sparse harmony is fine, a
dropped hook melody is not.

## 5. Build the set

Ask the user to open a fresh empty Live set (File > New Live Set) and save it as the song
title so it has a project folder (if `live.py tracks` already shows only the default empty
tracks, build into it and remind them to save). For an 808-style bass, `Sounds#Bass` has
"808 Pure" and friends. Write `layout.json` (`references/plan-format.md`): each
part on its instrument, its reference stem **muted, directly underneath**, the real vocal
as audio, the full original mix as a muted reference at the bottom. Then
`$PY build_set.py layout.json parts.json plan.json` and `$PY live.py verify`.
Fix any `CHECK-LENGTH` audio clip by re-placing it (`live.py place-audio <t> <file> --ref`);
if it keeps coming back short, Live's `.asd` sidecar is stale — copy the WAV to a new name.

## 6. First mix

Write `mix.json` (format in `scripts/mix.py`'s docstring; a worked example is in
`references/plan-format.md`) and run `$PY mix.py all mix.json`:
- chains: high-pass everything but kick/bass, a gentle cut in the 250–400 Hz mud area on
  keys/bass, presence on vocals, compression + de-ess on vocals, a subtle chorus on a
  synth guitar to make it sound less static;
- levels: each part/group matched to its own reference stem's playing level — a good,
  neutral starting balance, because the original's balance already worked. Quiet stock
  presets can need more than the fader's +6 dB; the extra goes on a Utility on that track;
- space: keys/guitar panned apart, small reverb sends, a touch of delay on guitar and
  vocal, vocal nudged up ~1.5 dB so it sits on top.

`mix.py` refuses loads that land on the wrong track; if one does, look at every track's
devices (`live.py tracks`) and remove strays with `Live.delete_device(t, i, expect_name)`.

## 7. Hand over

Offer, per part, to **play the original stem instead of the MIDI remake**
(`$PY live.py use-stem <part track> <ref track>`; `use-midi` reverses it). Generated stems
sometimes simply sound better than any stock preset — on the second test song the user
preferred the real guitar and bass stems. The swap unmutes the stem, mutes the MIDI part
(kept on its track as an option) and copies the part's pan and sends; rename both tracks
("Guitar – original stem", "Guitar – MIDI (muted option)") so the set reads clearly.

The user edits the set while you work (Booty Got Me Weak: swapped the keys preset to a
State Machine plugin and unmuted the keys REF within minutes of the build). Before any later
change, run `live.py tracks`, address tracks by NAME, keep their swaps and mute states, and
tell them about side effects (an unmuted REF that holds the melody doubles a new Melody track).

Tell the user to save (⌘S — you can't save a set). Summarise: tempo/offset, sections,
which part is on which instrument, what's muted for reference, what the mix did, and
what's deliberately left for them. Offer the obvious next edits (a part busier/simpler,
an octave, an instrument swap) — each is a quick `write_parts.py` + `live.py place-part` loop,
and earlier versions stay in Session view for A/B.

## 8. Logic Pro (export package instead of a live build)

Logic has no Remote Script equivalent and `.logicx` is undocumented, so for Logic users the
analysis (steps 1–4) is identical and the build is a package of files instead:

`$PY logic_export.py parts.json plan.json layout.json "<folder>/Logic" --title "<Title>" --kit "<folder>/Drum Kit" --mix mix.json --extra raw_parts.json:"Keys raw"="Keys raw (reference)"`

It writes `<Title>.mid` (format 1: tempo, 4/4, key, a marker per section, one named track per
`midi` row of layout.json – drums on channel 10, GM notes – plus `--extra` reference parts),
`Stems/` (every `audio`/`ref` file, numbered in layout order, all starting at bar 1),
`Drum Kit/Drop on C1` (contiguous pads 36…, renamed `036 Kick 1.wav` so a multi-file Sampler
drop at C1 maps them onto the notes the MIDI plays) + `Drum Kit/Alternates`, and `README.md`
(import steps, track list, sections with chords spelled for the key, and the first mix
translated to Logic stock plug-ins: Channel EQ bands, Compressor circuits, DeEsser 2,
ChromaGlow/Phat FX). The user opens the .mid (new project with tempo + markers), sets
44.1 kHz, drags `Stems/` in at bar 1 → Create new tracks, mutes the REF tracks, loads the kit,
picks instruments, and matches each part to its REF by ear. Put the melody track in
layout.json (step 4.8) so it's exported. MIDI meta text is Latin-1 — the script turns "–"
into "-" in track names/markers. Not yet verified by opening in Logic itself: when you hand
it over, ask the user to report anything that imports wrong and fix the script.
A user who sketches in Ableton and finishes in Logic can get both from the same analysis.

## Files

- `scripts/` — `live.py` (socket client + verify), `find_grid.py`, `align_stems.py`,
  `midi_parts.py`, `fidelity.py`, `bar_levels.py`, `chords.py`, `loops.py`, `rhythms.py`,
  `voicings.py`, `write_parts.py`, `snap_changes.py`, `follow_harmony.py`, `melody_line.py`, `logic_export.py`, `drums_midi.py`, `kit_rack.py`/`make_rack.py`,
  `build_set.py`, `mix.py`. Every script has usage in its docstring.
- `references/setup.md` — one-time install, Live settings, privacy settings of the connector.
- `references/plan-format.md` — plan.json / layout.json / mix.json with the first song as example.
- `references/lessons.md` — why each rule exists; read when something sounds off.
- `connector/` — `install.sh`, the AbletonMCP patch (`ableton-mcp-local-patches.diff`) and its MIT license.
