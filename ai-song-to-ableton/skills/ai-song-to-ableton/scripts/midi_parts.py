"""Clean a Song-to-MIDI (or Basic Pitch) file into parts, and score each against its stem.

Usage: midi_parts.py <parts.json> <bpm> <offset_s> <file.mid> <stem.wav> <instrument substring>=<part name> [...]
  offset_s: 0 if the MIDI came from an aligned stem; the find_grid offset if it came from
            the raw song. Song to MIDI's own tempo map is ignored – times are seconds.
  substring "*" takes every non-drum instrument.

Starts are fully quantized to 1/16, blips/ghosts dropped, and notes kept only in bars
where the stem is audible. Prints a fidelity score per part (chroma agreement with the
stem, 0..1) – on the first song the good candidates scored 0.7–0.8 and a bad one 0.27;
prefer the higher-scoring source when you have two transcriptions of the same thing.
Raw transcriptions are faithful but busy: use them as the reference for voicings and
melody, and write_parts.py for the parts people actually want to hear.
"""
import json
import sys

import numpy as np
import pretty_midi

from common import bar_db, clean_notes, load_mono
from fidelity import score

SR = 22050


def main():
    parts_path, bpm, off, mid, wav = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
    db = bar_db(load_mono(wav, SR), SR, bpm)
    live = db > max(db.max() - 30, -55)
    pm = pretty_midi.PrettyMIDI(mid)
    print("instruments in file:", [(i.name, i.program, len(i.notes)) for i in pm.instruments if not i.is_drum])
    try:
        data = json.load(open(parts_path))
    except FileNotFoundError:
        data = {"bpm": bpm, "parts": {}}
    for spec in sys.argv[6:]:
        key, name = spec.split("=", 1)
        notes = [n for i in pm.instruments if not i.is_drum and (key == "*" or key.lower() in i.name.lower()) for n in i.notes]
        c = clean_notes(notes, bpm, off)
        kept = [n for n in c if live[min(int(n[1] // 4), len(live) - 1)]]
        data["parts"][name] = kept
        length = max([n[1] + n[2] for n in kept] + [data.get("length_beats", 0)])
        data["length_beats"] = int(np.ceil(length / 4) * 4)
        f = score(kept, wav, bpm, data["length_beats"]) if kept else {}
        print(f"{name}: {len(notes)} raw -> {len(kept)} kept; match {f.get('match', 0):.2f}, "
              f"coverage {f.get('coverage', 0):.0%}, plays-where-silent {f.get('plays_where_silent', 0):.0%}")
    json.dump(data, open(parts_path, "w"))


if __name__ == "__main__":
    main()
