"""Write simple, section-aware MIDI parts from plan.json (loops + measured patterns).

Usage: write_parts.py <plan.json> <parts.json> [bar_levels.json] [voicings.json]

Each entry in plan["parts"] becomes parts.json["parts"][name]. Fields:
  style      "held"  – one attack per chord change, held to the next change
             "hits"  – short chord stabs at fixed bar positions ("hits")
             "bass"  – root notes: a pattern per bar on long chords, anticipation on short ones
             "off"   – nothing (use in overrides to rest a part in a section)
  range      [lo, hi] MIDI notes. Bass: keep it ONE low octave, e.g. [28, 39] (E0–D#1 in
             Live's naming) – a bass that follows voice leading drifts an octave up.
  voicing    key into voicings.json (real voicings), or "color" (full chord) / "triad"
  velocity   default 80
  hits       style hits: beat positions inside the bar, 0 = beat 1 (0.75 = the 16th before beat 2)
  hit_length style hits: note length in beats (default 0.4)
  pattern    style bass: [[beat, length], ...] per bar for chords lasting a bar or more
             (default [[0, 1.25], [1.5, 1.5]] – the 1 and the "and" of 2)
  anticipate style bass: a chord that starts on beat 3 is hit an 8th early (default true)
  held       style bass: one long root per chord instead (good for intros/bridges/outros)
  audible    bar_levels key: only play bars where that stem is audible in the original
  overrides  {section name: {any field above}} – e.g. held bass in the intro/outro
"""
import json
import sys

from common import chord_pcs, parse_chord, voice


def audible_bars(levels, key):
    if not levels or key not in levels:
        return None
    thr = -40 if "bass" in key else -50
    return [x > thr for x in levels[key]]


def main():
    plan = json.load(open(sys.argv[1]))
    parts_path = sys.argv[2]
    levels = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    real = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
    try:
        data = json.load(open(parts_path))
    except FileNotFoundError:
        data = {"bpm": plan["bpm"], "parts": {}}
    data["bpm"] = plan["bpm"]
    data["length_beats"] = max(s["bars"][1] for s in plan["sections"]) * 4

    chords = []  # (start, dur, chord, section)
    for sec in plan["sections"]:
        a, b = sec["bars"]
        t, end, i = (a - 1) * 4.0, b * 4.0, 0
        while t < end:
            ch, d = sec["loop"][i % len(sec["loop"])]
            chords.append((t, min(d, end - t), ch, sec["name"]))
            t += d
            i += 1

    for spec in plan["parts"]:
        notes, prev = [], None
        on = audible_bars(levels, spec.get("audible"))
        for t, d, ch, sec in chords:
            p = {**spec, **spec.get("overrides", {}).get(sec, {})}
            if not ch or p["style"] == "off":
                continue
            bar = int(t // 4)
            if on is not None and (bar >= len(on) or not on[bar]):
                continue
            lo, hi = p.get("range", [48, 72])
            vel = p.get("velocity", 80)
            src = p.get("voicing", "color")
            pcs = real.get(src, {}).get(ch) or chord_pcs(ch, triad=(src == "triad"))
            if p["style"] == "held":
                prev = voice(pcs, prev, lo, hi)
                notes += [[n, t, round(d - 0.05, 3), vel] for n in prev]
            elif p["style"] == "hits":
                prev = voice(pcs, prev, lo, hi)
                for b0 in range(int(t // 4) * 4, int(t + d) + 4, 4):
                    for pos in p.get("hits", [1.0, 3.0]):
                        h = b0 + pos
                        if t <= h < t + d:
                            notes += [[n, round(h, 3), p.get("hit_length", 0.4), vel] for n in prev]
            elif p["style"] == "bass":
                r = parse_chord(ch)[0]
                root = next(n for n in range(lo, lo + 12) if n % 12 == r)
                if p.get("held"):
                    notes.append([root, t, round(d - 0.1, 3), vel])
                elif d >= 4:
                    for b0 in range(int(t), int(t + d), 4):
                        notes += [[root, b0 + o, ln, vel if o == 0 else vel - 14]
                                  for o, ln in p.get("pattern", [[0, 1.25], [1.5, 1.5]]) if b0 + o < t + d]
                elif p.get("anticipate", True) and t % 4 == 2.0:
                    notes.append([root, t - 0.5, round(d - 0.25, 3), vel - 10])
                else:
                    notes.append([root, t, round(d - (0.5 if p.get("anticipate", True) else 0.1), 3), vel])
        notes.sort(key=lambda n: (n[1], n[0]))
        data["parts"][spec["name"]] = notes
        bars = len({int(n[1] // 4) for n in notes})
        attacks = len({n[1] for n in notes})
        print(f"{spec['name']:<20} {len(notes):>4} notes, {attacks:>3} attacks over {bars} bars "
              f"({attacks / max(bars, 1):.1f}/bar)")
    json.dump(data, open(parts_path, "w"))


if __name__ == "__main__":
    main()
