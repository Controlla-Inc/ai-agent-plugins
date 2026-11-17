---
name: rebuild-controlla-song-in-logic
description: Generate or rebuild Controlla Voice songs as editable Logic Pro sessions with aligned stems, simplified held MIDI chords, basic stock instruments, and regenerated drum samples triggered by mapped MIDI in Drum Machine Designer. Use for requests to turn an AI song into a Logic project, rebuild stems as MIDI, simplify acoustic guitar MIDI, or replace a song's drums with a playable cloned kit.
---

# Controlla to Logic Song Rebuild

Follow the user's musical direction. For an unspecified new song, default to modern Afro R&B, dreamy male vocals, original lyrics and spacious held harmony. Do not regenerate an existing song unless requested.

## Recover and prepare

Inspect the current project, workspace and named previous deliverables before spending credits or replacing work. Preserve user edits and raw transcription; save a recoverable revision before material edits. Record source/take identity, job statuses, verified BPM/key, sample rate, song origin, paths, drum mapping and pending checks in a project-local manifest. Do not store credentials or expiring download links in this skill.

Discover current Controlla tools and actual Logic controls. Prefer a sufficient dedicated connector; otherwise use supported computer-use APIs. Never assume a Logic MCP exists. If native control is unavailable, prepare the assets and explicitly report that the Logic project remains unbuilt.

Read [Logic session controls](references/logic-session.md) before GUI editing and [Timing and MIDI](references/timing-and-midi.md) before processing notes or audio.

## Obtain the song and parts

Reuse the existing source when appropriate. For generation, choose lyrics/arrangement within the brief, check current credits/pricing, submit one song job, inspect returned takes and select one. Use generic vocal descriptors or an available authorized voice. Follow current tools' explicit consent requirements for voice references/clones.

Download the chosen audio and complete import/analysis before dependent jobs. Request vocal/instrument stems, song-to-MIDI and regenerated drum one-shots. Run independent jobs concurrently when supported; reuse a suitable completed stem split for drum cloning. Follow current polling intervals. Resume existing jobs after interruption; do not rerun paid jobs merely because polling/download failed.

## Establish one timeline

Verify tempo against transients at the beginning, middle and end, then audition against a click. Treat analyzed BPM as an estimate. Distinguish fixed offset from cumulative drift and check half/double-time ambiguity. Retain a tempo map for genuinely variable performances.

Preserve leading silence and common source origin. Convert stems to one sample rate/PCM format and pad only their ends to a common length. Do not independently normalize stems or trim their starts. Use `scripts/align_stems.py` for conversion, end padding and an audit manifest; identical length alone does not prove alignment.

To change a MIDI grid while retaining the performance, use `scripts/prepare_midi.py retime`; preserve absolute seconds through the original tempo map. Set Logic to the verified tempo, retain it on MIDI import, and check that Smart Tempo/Flex has not stretched the audio.

## Rebuild editable instruments

Create named MIDI tracks with basic stock sounds: electric piano for chords, simple bass, acoustic/clean guitar, piano, optional muted vocal melody guide, and regenerated drums. Put all audio stems together underneath all MIDI tracks. Label alternatives; avoid accidental doubling of MIDI and corresponding stems.

Keep raw MIDI. Remove demonstrably spurious fragments, duplicates and overlaps on working copies. Reduce messy harmony to a few held notes per actual chord change; retain rests and section boundaries. Keep bass monophonic where appropriate. Simplify guitar by reducing repetitive strums/arpeggio fragments to restrained held voicings, with a small strum spread only if useful.

Use `scripts/prepare_midi.py simplify` on a selected harmonic track as a **first pass**. Audition and correct it against the stem. Weighted pitch classes do not identify chords reliably; split at true harmonic changes instead of forcing one chord per bar. Prefer replaying a clear voicing to preserving transcription clutter.

## Make regenerated drums playable

Create an actual Drum Machine Designer track. Load regenerated one-shots into individual pads through supported Logic controls; use Quick Sampler or a suitable stock sampler on pad channels as needed. Disable pitch tracking and configure one-shot playback, suitable choke groups and velocity response.

Inventory source drum pitches and actual numeric pad input notes. Build an explicit source-to-pad map, then use `scripts/prepare_midi.py drums --map mapping.json`. The script rejects unassigned source notes. Assign extra pads for available toms/percussion; do not silently collapse all unmatched hits into rim shots. Label approved approximations. An alternate short hat is not a regenerated open cymbal.

Preserve onsets and velocities. Solo/test every used pad, inspect the loaded filename, and confirm its MIDI produces the intended sample and meter/audio activity. A factory kit, unassigned MIDI, rendered groove or SFZ file alone does not satisfy this step. Keep an optional audio render below MIDI as a muted reference. Mute redundant drums only after the new kit passes playback checks.

## Verify and deliver

Check the source/take, tempo, key, sample rate, origin, duration, and alignment at beginning/middle/end. Check correct instruments, simplified harmony, every drum mapping, no unwanted factory sounds, no temporary audition tracks, clear names, track order, sensible mute/solo state and no accidental doubling/clipping.

Save the native project with audio **and sampler samples copied into the project**. Reopen a copy without temporary sample directories before calling it portable. Include individual MIDI, raw transcription, stems, one-shots and a concise timing/mapping note when requested. Validate ZIP integrity and contents. Save requested deliverables with the available persistent file workflow.

Report verified outcomes and concrete unfinished checks. Distinguish a visually checked setup from an auditioned mix. Do not describe untested sampler preset modifications as a reliable workflow. Never include generated songs, personal paths or audio samples in this skill itself.
