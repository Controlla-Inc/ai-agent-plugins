---
name: music-to-movie
description: Score a video clip in Ableton Live - read the clip's cuts, generate an original song in Controlla Voice at the tempo the edit asks for, split it into stems, MIDI and a cloned drum kit, then rebuild it on the timeline UNDER THE PICTURE so every moment of the music lands on an edit - big trailer drums on the cuts, string parts with expression automation, and designed sound FX (impacts, braams, risers, whooshes, sub drops) synced to the frame. Built on the song-to-session skill (same connector, same analysis tools). Use whenever someone wants music FOR a video - "score this trailer / clip / scene", "make a song for this video in Ableton", "epic/cinematic music that hits the cuts", "music to movie", "add sound design and hits to my edit", or wants an existing cue re-timed to a new cut - even if they don't name the skill. For a song with no picture use song-to-session. 
---

# Music to movie: score a clip in Ableton

The promise: **the user opens Live and the picture is on the timeline with a cue that already
hits its cuts** - stems, MIDI, a drum kit and sound design they can all edit. The song comes
from Controlla; the cue is a *rebuild* of it against the picture, not the song laid under the
video. `song-to-session` is the foundation (connector, venv, `live.py`, grid tools,
kit rack): read its SKILL.md first and run its preflight (step 0). This skill adds the
picture.

Scripts are in `scripts/`; run them with the same venv:
`PY=~/.local/share/ai-song-to-ableton/venv/bin/python`. Work in
`~/Music/Controlla Drafts/<Cue title>/` (copy the video in - Live references it by path).

## 0. Preflight

1. song-to-session's preflight (plugin installs: `/ableton:setup`; otherwise `connector/install.sh --check`, `live.py tracks`).
2. The connector needs this skill's commands: `set_clip_envelope`,
   `create_arrangement_audio_clip`, `get_parameter_strings`, `set_track_mute`, `delete_track`.
   They are in song-to-session's `connector/ableton-mcp-local-patches.diff` since
   2026-11-26. "Unknown command" = Live is running an older Remote Script: re-run
   `install.sh`, then **quit and reopen Live** (it only loads Remote Scripts at startup).
   Do this BEFORE building anything - the restart is free on an empty set.
3. `ffmpeg` must be on PATH (`brew install ffmpeg`) - the cut map and preview use it.
4. Video in Arrangement needs Live Standard or Suite. Live opens to an empty set; build into it.

## 1. Read the picture first

`$PY scripts/cut_map.py "<video>" "<folder>/analysis" --weights <title_s>=3,<reveal_s>=2 --bpm-range 100 130`

- **Look at `sheet.jpg`** (4 frames per second, index i = i/4 s). Write down what each shot
  IS (close-up, storm, embrace, title card) - the cue is written from the story, the numbers
  only say when. Cut detection misses dissolves and fires twice on flashes; the sheet settles it.
- Pick the tempo where the **title card / final reveal lands on a bar line** and most cuts
  sit within ~60 ms of a beat. Prefer offset 0 so the video sits at 1.1.1.
  (First cue: 10.7 s clip, cuts at 1.10 2.77 3.77 4.77 5.90 7.10 8.50 → 113 BPM, title on
  bar 5 beat 1.) Cuts a beat cannot reach are hit with sound design, which is placed in
  seconds, not beats.
- A hit up to ~3 frames early reads as in sync; late reads as a mistake. When the music's
  hit is ~100 ms early, add a flam: grace hit on the beat, main hit on the frame (ka-DON).

## 2. Generate the song AT that tempo, then take it apart

`create_song_generation` (Instrumental, `target_bpm` = the cut tempo, a `target_key`, a style
that names the ensemble: taiko/gran cassa, staccato low-string ostinato, sustained high
strings, low brass, choir, risers). Describe the scene, never a film, composer or franchise.
Two takes come back - measure both (`librosa` beat track + 5 s RMS curve) and keep the one
whose tempo matches. Then, as in song-to-session step 1: `import_audio` the take's URL,
`analyze_upload`, and in parallel
`create_stem_split ["vocals","instrumental","kick","snare","cymbals","toms"]`,
`create_stem_split ["drums","bass","piano","guitar"]`, `create_drum_kit`,
`create_song_to_midi` (free; it separated French horn / viola / cello / contrabass on the
first cue and is the source of every MIDI part).

**Measure the tempo** (`find_grid.py` on the full drums stem gave lock 0.88; kick+snare alone
0.50 on orchestral percussion). If it equals the cut tempo within ~0.1 BPM, song sections
drop onto the picture grid unstretched. If not: regenerate, or re-fit the cut tempo to the
song (`cut_map.py --bpm <song bpm>` prints the beat map) - don't time-stretch orchestral stems.

Nudge the grid offset until the big drum hits read x.00 in a per-beat level table (0.25 →
0.405 s on the first cue); transcribed notes sit on their own offset (0.367 s there) - check
where the notes cluster and use that for MIDI.

## 3. Find the song's moments

Print per-beat levels of drums / kick / toms / instrumental / bass, and per-beat chord +
onset strength of `music = instrumental − drums − bass`. You are looking for:
- a **build** (dominant pedal, rising line, drum fury) → under the action;
- a **breakdown** (drums out, a line climbing to the re-entry) → under the quiet or emotional
  shots, timed so its last beat is the beat before the title;
- the **biggest landing chord with a long ring-out** → on the title (it can be reused: the
  first cue used the same landing under two different picture moments);
- phrase lengths that match the gaps between cuts. The first cue's breakdown was exactly the
  six beats between the embrace and the title - look for that kind of fit before forcing one.
Listing the transcription's notes for each candidate tells you what the instruments play
there (a scale run, sextuplets, a horn tune), which you cannot hear from here.

## 4. Cut, synthesise, write the cue sheet

- `excerpt.py` cuts each section of `music`, `bass`, `drums` on SONG beats with fades; each
  file is placed at a cue beat. Sections that overlap in time go on different tracks.
- `trailer_sfx.py <folder>/SFX --root <key root>` renders boom, impact, impact_big, braam,
  braam_long, riser, riser_short, reverse, whoosh, sub_drop, wind, shimmer and `sfx.json`
  with each sound's **sync point** (an impact's transient, a riser's END, a whoosh's peak).
- `kit_rack.py "<kit dir>" "<Title>"` (song-to-session) makes the cloned-kit Drum Rack.
  On an orchestral song the "kicks" are bass drums/taikos and the "snares"/"hats" low
  percussion - check spectral centroids, don't trust the names. Pads: 36 41 43 45 47 lows,
  38 37 39 40 50 mids, 46 49 55 57 cymbals.
- Copy `examples/make_cue_trailer_clip.py` to the cue folder as `make_cue.py` and rewrite
  it: picture events in seconds, `take()` to lift transcribed notes from song beats to cue
  beats, the drum part, the SFX list, automation points, track list. It writes `cue.json`
  (format in `scripts/score_build.py`'s docstring).

What goes where (trailer grammar that worked):
- **Drums**: the song's drums stem plays; the cloned-kit MIDI doubles ITS big hits on the
  same beats (never 100 ms beside them - that is a flam you didn't choose) and adds the
  picture-only hits: one on each cut, a 16th roll with rising velocity into a hard cut, soft
  low "heartbeats" under quiet shots, a full-kit stack on the title, one or two trailing
  hits and a final button.
- **Strings/horns MIDI** = the transcription, notes held to the next onset (stock string
  patches swallow 0.1-beat notes). Each MIDI track gets a Utility whose gain is automated
  as *expression*: crescendo through a run, drop at a cut-out, swell into the title, long
  fade on the tail. The track fader stays free for mixing.
- **Sound design**: riser ending ON a cut, impact + braam on the biggest reveals, whoosh on
  a camera move/cut, sub drop when the frame goes dark, wind/atmos bed for the location,
  reverse swell into the title, a soft boom on quiet cuts. Fewer, bigger, on the frame.
- **Dynamics are the edit**: the title must be the loudest moment by a clear margin. Print
  the preview's 0.25 s RMS curve and pull back anything earlier that competes with it.

## 5. Preview without Live

`$PY scripts/render_preview.py cue.json "<folder>/Preview"` → `preview.wav` + `preview.mp4`
(picture + stems + kit + SFX; the MIDI instruments are not in it). It prints the mix peak
(the title stacks ~15 sources: on the first cue the sum was +6.7 dBFS until every track
came down 7 dB) and the level before/after each cut. Send the MP4 to the user - it is the
fastest way for them to judge sync.

## 6. Build in Live

`$PY scripts/score_build.py cue.json` on the empty set: picture on the first track (its own
audio muted), every track in cue order, MIDI parts with automation, clips at their beats,
levels, locators on every picture event. Then:
- `score_build.py cue.json --verify` ~30 s later (clip lengths vs files = auto-warp check);
- `meter_pass.py cue.json --sections 0,5,9,16,...` plays once with the master at silence and
  prints each track's meter per section: any `SILENT` row is a failed instrument load or a
  missing clip. Meters are compressed - read them as silent / present / loud.
- Changing one MIDI part later: edit make_cue.py, re-run it, `score_build.py cue.json --part "<track name>"`.
- Rebuilding everything: `--replace` (deletes EVERY track in the set first - only on a set
  this skill built, and say so before running it).
- `export_midi.py cue.json "<folder>/MIDI"` writes the parts as .mid files (plus one
  multi-track file with tempo and cut markers) for the user to keep.

## 7. Hand over

Tell the user to **save (Cmd-S)** - nothing here can save a set - and to open the video
window (View > Video Window) if the picture isn't showing. Summarise as a cue sheet: time →
what the picture does → what the music does. Say plainly what was not checked by ear (all
of it: balance, the stock string/horn sounds, whether the spliced sections flow) and what
is deliberately left for them: instrument choices (their orchestral libraries load with
default patches only, so stock presets are used), the mix, a limiter on the master.
Offer the next edits: swap the stock strings for their library, move a hit, more/less
sound design, a longer tail, a different section of the song under a shot, export.

## Lessons (each one cost a rebuild)

- **Live cuts a clip's tail when the next clip starts on the same track**, and creating a
  clip inside an existing one SPLITS it. Long tails (impacts ring 6-9 s) need lanes:
  `score_build.py` spreads overlapping clips over two lanes and fades the tail that has
  rung longest (`max_lanes` per track in cue.json).
- **Live remembers a file's length by its name.** A re-rendered copy with the same filename
  keeps the old length and then gets split by its neighbour. Baked copies carry gain, tail
  and head in their names; if you change a source file, change its name too.
- **Automation only goes into Session clips** (`Clip.automation_envelope` returns nothing
  for Arrangement clips). Write the envelope into the Session clip, then
  `duplicate_session_clip_to_arrangement` - it arrives as track automation.
- **Utility's gain is called "Output" and is not linear**: 35 dB per unit down to −17.5 dB,
  steeper below (−0.75 = −29.6 dB, −0.9 = −45.7 dB). `score_build.py` inverts the device's
  own display strings (`get_parameter_strings`) - do the same for any parameter given in dB.
- `Track.create_audio_clip(path, beat)` places audio AND video straight on the Arrangement
  (no Session detour, no auto-warp surprise if warping is set off immediately).
- **Never delete tracks by index after a script may already have done it.** A build died on
  a locator after it had removed the default tracks; "cleaning up tracks 0-3" then deleted
  the video, the drums and the strings. Deletions take `expect_name` from a list captured
  BEFORE the build, and locators are created last and never abort a build.
- Locators: `create_locator` failed every time at two of nine positions (1.10 s and the
  picture's end) for reasons not found; the build reports them and carries on. Re-run
  `--locators` once; if they still fail, tell the user which markers to add by hand.
- A clip with a pre-roll placed at beat 0 would start before 1.1.1: the build cuts the head
  off a copy instead (a riser that must start before the picture loses its start - move the
  video to bar 2 if that matters).
- Screenshots of the user's desktop don't show Live when it is behind other windows; verify
  with clip lists and meters, not screen grabs.
- `find_grid.py` on kick+snare stems of orchestral percussion locks poorly; use the full
  drums stem for both arguments.

## Files

- `scripts/cut_map.py` - cuts, contact sheet, tempo fit, beat map.
- `scripts/excerpt.py` - bar-aligned section out of a song stem.
- `scripts/trailer_sfx.py` - synthesised trailer sound design + sync points.
- `scripts/render_preview.py` - offline mix under the picture, sync/level report.
- `scripts/score_build.py` - cue.json → Live (also `--part`, `--locators`, `--verify`, `--replace`).
- `scripts/meter_pass.py` - silent playback, per-track meters per section.
- `scripts/export_midi.py` - the cue's MIDI parts as files.
- `examples/make_cue_trailer_clip.py` - the first cue's sheet (dark orchestral trailer, 10.7 s).
- `references/first-cue.md` - what the first cue did, second by second.
