# Timing and MIDI preparation

Use a project-local Python environment with `mido`; use FFmpeg for conversion. Preserve source files. The scripts refuse existing output paths.

```bash
python scripts/align_stems.py --input-dir Raw-Stems --output-dir Aligned-Stems --sample-rate 44100 --reference Original.wav
python scripts/prepare_midi.py retime Original.mid Rebuild.mid --bpm 100
python scripts/prepare_midi.py simplify Guitar.mid Guitar-Simple.mid --track 0 --max-notes 3
python scripts/prepare_midi.py drums Drums.mid Drums-DMD.mid --map mapping.json
```

Use 100 BPM only as an example; supply the verified current tempo. `--track` is a zero-based MIDI-file index, including conductor tracks. Inspect track names before selection. Simplification supports constant 4/4 only and is a heuristic requiring audition.

Use an explicit drum JSON map, such as `{"35":36,"36":36,"38":38,"42":42,"44":42}`. Include every source pitch after inspecting transcription and available sounds. Preserve timing/duration and velocity; configure sampler one-shot playback in Logic. Retain the map in handoff notes.

Supply an isolated drum MIDI file with notes on channel 10 (zero-based channel 9). The drum helper rejects melodic/non-drum channels instead of accidentally remapping the whole song. If transcription assigns another channel, first inspect and explicitly extract/rechannel only the verified drum part.

Retime by computing absolute seconds through the full source tempo map, then new ticks as `round(seconds * target_bpm * PPQ / 60)`. Do not merely change the tempo meta-event. Check lag separately from drift and retain a variable tempo map when needed.

End padding and format conversion preserve source origins but do not establish synchronization. Compare transients/correlation where applicable and audition stems together. Never remove leading silence independently. Record any deliberate offsets. Avoid stretching audio to fit a guessed BPM.
