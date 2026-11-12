"""Pull the instrumental melody (hook riff / topline) out of a Song-to-MIDI transcription.

Usage: melody_line.py <raw_parts.json> <raw part name> <parts.json> [--name Melody]
                      [--min-pitch 65] [--max-len 1.0]

Song to MIDI on the music stem returns ONE track ("Acoustic Grand Piano") with chords AND
the melody mixed together. write_parts.py rewrites the harmony as held chords, so a hook
riff that lives in that track silently disappears – on "Booty Got Me Weak" the user asked
"there's a melody that's not present". The melody is still in the raw transcription:
short notes (<= --max-len beats) in the upper register (>= --min-pitch, default F4) that
held chord tones don't produce. Per onset the highest such note is kept (skyline), and each
note is cut where the next one starts, so the result is monophonic.

Check before using it: print the per-bar top line of the raw part (see SKILL.md step 4) –
a riff that repeats every bar/loop is a melody; isolated high notes are chord tops.
Writes parts.json["parts"][<name>]. Place it on its own MIDI track under the keys
reference with a neutral lead preset; there is no melody-only stem, so its level is set
by ear (about -6 dB), not level-matched.
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"), ap.add_argument("part"), ap.add_argument("parts")
    ap.add_argument("--name", default="Melody")
    ap.add_argument("--min-pitch", type=int, default=65)
    ap.add_argument("--max-len", type=float, default=1.0)
    a = ap.parse_args()
    raw = json.load(open(a.raw))["parts"][a.part]
    raw = raw["notes"] if isinstance(raw, dict) else raw
    top = {}
    for p, s, d, v in raw:
        if p >= a.min_pitch and d <= a.max_len and (s not in top or p > top[s][0]):
            top[s] = [p, s, d, v]
    mel = sorted(top.values(), key=lambda n: n[1])
    for i in range(len(mel) - 1):
        mel[i][2] = round(min(mel[i][2], mel[i + 1][1] - mel[i][1]), 4)
    parts = json.load(open(a.parts))
    parts["parts"][a.name] = mel
    json.dump(parts, open(a.parts, "w"))
    bars = sorted({int(n[1] // 4) + 1 for n in mel})
    print(f"{a.name}: {len(mel)} notes, pitch {min(n[0] for n in mel)}-{max(n[0] for n in mel)}, "
          f"in {len(bars)} bars ({bars[0]}-{bars[-1]})")


if __name__ == "__main__":
    main()
