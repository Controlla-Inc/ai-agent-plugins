"""Export the draft as a Logic Pro package (Logic has no API, so it gets files, not a live build).

Usage: logic_export.py <parts.json> <plan.json> <layout.json> <out_dir>
                       [--title "Song"] [--kit <drum kit dir>] [--mix mix.json]
                       [--extra <raw_parts.json>:"<raw part>"="<track name>"]...

Same inputs as build_set.py, so one analysis feeds both DAWs. Writes into <out_dir>:
  <Title>.mid   Standard MIDI File, format 1: tempo, 4/4, key signature and a marker per
                section on the conductor track, then one named track per "midi" row of
                layout.json (drums on channel 10, GM notes 36/38/42…), plus any --extra
                reference parts (e.g. the busy raw transcription). Opening it in Logic
                (File > Open) creates a project with the tempo, markers and tracks in place.
  Stems/        every "audio" and "ref" file from layout.json, numbered in layout order,
                all starting at bar 1 (they come from align_stems.py).
  Drum Kit/     the cloned one-shots renamed by MIDI note. "Drop on C1/" holds the
                contiguous pads 36..45 so a multi-file drop onto Sampler (zone per file)
                from C1 lands each sample on the note drums_midi.py wrote;
                "Alternates/" holds the rest.
  README.md     import steps, track list, sections, chords and the first-mix settings.

Logic can't be driven from outside (no Remote Script equivalent; .logicx is undocumented),
so instruments, the kit and the mix are the user's few clicks – the README lists them.
"""
import argparse
import glob
import json
import os
import re
import shutil

import mido

from kit_rack import SLOTS

TPB = 480
EQ_KIND = {"lowcut48": "high-pass 48 dB/oct", "lowcut12": "high-pass 12 dB/oct", "highcut12": "low-pass 12 dB/oct",
           "bell": "bell", "highshelf": "high shelf", "lowshelf": "low shelf"}
# Live 12 Standard presets the mix uses (FileIds in mix.json) -> the Logic stock plug-in to reach for
LOGIC_FX = {
    "FileId_8091": "ChromaGlow or Phat FX (Drum Buss 'Drum Sharpener': drive + punch)",
    "FileId_7904": "Compressor, Bus/VCA circuit, ~2:1, slow attack, auto release ('Gentle Two Buss')",
    "FileId_7901": "Compressor, Platinum Digital, ~4:1, fast release ('Bass Punch')",
    "FileId_8183": "Compressor, Vintage Opto, ~4–6 dB gain reduction ('Sustained Lead Vocal')",
    "FileId_8172": "DeEsser 2 ('De-esser')",
    "FileId_8187": "Chorus or Ensemble, subtle ('Chorus Subtle Funk')",
}
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm"}
FLATS = {"C#": "D♭", "D#": "E♭", "F#": "G♭", "G#": "A♭", "A#": "B♭"}


def spell(chord, key):
    """Chord names come out of chords.py with sharps; spell them flat in flat keys (D# -> E♭ in Gm)."""
    if key not in FLAT_KEYS:
        return chord
    for sharp, flat in FLATS.items():
        if chord.startswith(sharp):
            return flat + chord[len(sharp):]
    return chord


GM_PROGRAM = {"keys": 4, "piano": 0, "808": 38, "bass": 33, "guitar": 27, "melody": 80, "lead": 80}


def safe(name):
    return re.sub(r'[/:*?"<>|]', "-", name).strip()


def text(s):
    """MIDI meta text is Latin-1: dashes/quotes from track names would crash mido."""
    s = s.replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return s.encode("latin-1", "replace").decode("latin-1")


def ticks(beats):
    return int(round(beats * TPB))


def note_track(name, notes, channel, program=None):
    ev = []
    for p, s, d, v in notes:
        ev.append((ticks(s), 1, mido.Message("note_on", note=int(p), velocity=max(1, min(127, int(v))), channel=channel)))
        ev.append((ticks(s + max(d, 0.02)), 0, mido.Message("note_off", note=int(p), velocity=0, channel=channel)))
    ev.sort(key=lambda e: (e[0], e[1]))
    tr = mido.MidiTrack([mido.MetaMessage("track_name", name=text(name), time=0)])
    if program is not None:
        tr.append(mido.Message("program_change", program=program, channel=channel, time=0))
    now = 0
    for t, _, msg in ev:
        tr.append(msg.copy(time=t - now))
        now = t
    tr.append(mido.MetaMessage("end_of_track", time=0))
    return tr


def conductor(title, bpm, key, sections):
    tr = mido.MidiTrack([
        mido.MetaMessage("track_name", name=text(title), time=0),
        mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0),
        mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0),
    ])
    try:
        tr.append(mido.MetaMessage("key_signature", key=key, time=0))
    except (ValueError, KeyError):
        pass
    now = 0
    for s in sections:
        t = ticks((s["bars"][0] - 1) * 4)
        tr.append(mido.MetaMessage("marker", text=text(s["name"]), time=t - now))
        now = t
    tr.append(mido.MetaMessage("end_of_track", time=0))
    return tr


def program_for(name):
    low = name.lower()
    return next((p for k, p in GM_PROGRAM.items() if k in low), None)


def export_kit(kit, out):
    drop, alt = os.path.join(out, "Drop on C1"), os.path.join(out, "Alternates")
    os.makedirs(drop, exist_ok=True)
    os.makedirs(alt, exist_ok=True)
    pads = {}
    for kind, notes in SLOTS.items():
        for rank, (note, f) in enumerate(zip(notes, sorted(glob.glob(os.path.join(kit, f"{kind}_*.wav"))))):
            pads.setdefault(note, (kind, rank + 1, f))
    run = 36
    while run in pads:
        run += 1
    for note, (kind, rank, f) in sorted(pads.items()):
        label = {"hihat": "Hat", "open_cymbal": "Open Cymbal"}.get(kind, kind.title())
        dst = drop if note < run else alt
        shutil.copy2(f, os.path.join(dst, f"{note:03d} {label} {rank}.wav"))
    return pads, run - 1


def mix_lines(mix):
    if not mix:
        return []
    lines = []
    for name, t in mix.get("tracks", {}).items():
        bits = []
        eq = []
        for band in t.get("eq", []):
            _, kind, freq, gain, q = band
            label = EQ_KIND.get(kind, kind)
            eq.append(f"{label} {freq} Hz" + (f" {gain:+.1f} dB (Q {q})" if gain else ""))
        if eq:
            bits.append("Channel EQ: " + ", ".join(eq))
        for uri in t.get("load", []):
            fid = uri.rsplit(":", 1)[-1]
            bits.append(LOGIC_FX.get(fid) or uri.split("#")[-1].split(":")[0].replace("%20", " ") + " (Live device – use Logic's closest)")
        if "pan" in t:
            bits.append(f"pan {t['pan'] * 64:+.0f}")
        if "reverb_db" in t:
            bits.append(f"reverb send {t['reverb_db']} dB")
        if "delay_db" in t:
            bits.append(f"delay send {t['delay_db']} dB")
        if "nudge_db" in t:
            bits.append(f"{t['nudge_db']:+.1f} dB above its matched level")
        lines.append(f"- **{name}**: " + "; ".join(bits))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parts"), ap.add_argument("plan"), ap.add_argument("layout"), ap.add_argument("out")
    ap.add_argument("--title"), ap.add_argument("--kit"), ap.add_argument("--mix")
    ap.add_argument("--extra", action="append", default=[])
    a = ap.parse_args()
    parts, plan, layout = (json.load(open(p)) for p in (a.parts, a.plan, a.layout))
    mix = json.load(open(a.mix)) if a.mix else None
    title = a.title or os.path.basename(os.path.normpath(a.out))
    bpm = parts.get("bpm") or plan["bpm"]
    os.makedirs(a.out, exist_ok=True)

    mid = mido.MidiFile(type=1, ticks_per_beat=TPB)
    mid.tracks.append(conductor(title, bpm, plan.get("key", "C"), plan["sections"]))
    midi_rows, ch = [], 0
    for row in layout["tracks"]:
        if row["kind"] != "midi":
            continue
        notes = parts["parts"][row["part"]]
        drums = row["part"].lower().startswith("drum")
        channel = 9 if drums else ch
        if not drums:
            ch = ch + 1 if ch + 1 != 9 else 10
        mid.tracks.append(note_track(row["name"], notes, channel, None if drums else program_for(row["name"])))
        midi_rows.append((row["name"], len(notes)))
    for spec in a.extra:
        src, rest = spec.split(":", 1)
        raw_name, track_name = (x.strip('"') for x in rest.split("=", 1))
        notes = json.load(open(src))["parts"][raw_name]
        notes = notes["notes"] if isinstance(notes, dict) else notes
        mid.tracks.append(note_track(track_name, notes, ch))
        ch = ch + 1 if ch + 1 != 9 else 10
        midi_rows.append((track_name, len(notes)))
    mid_path = os.path.join(a.out, f"{safe(title)}.mid")
    mid.save(mid_path)

    stems = os.path.join(a.out, "Stems")
    os.makedirs(stems, exist_ok=True)
    audio_rows = []
    for row in layout["tracks"]:
        if row["kind"] in ("audio", "ref"):
            n = len(audio_rows) + 1
            dst = os.path.join(stems, f"{n:02d} {safe(row['name'])}.wav")
            shutil.copy2(row["file"], dst)
            audio_rows.append((row["name"], row["kind"] == "ref"))

    kit_note = ""
    if a.kit:
        pads, last = export_kit(a.kit, os.path.join(a.out, "Drum Kit"))
        kit_note = f"{len(pads)} one-shots; notes 36–{last} in `Drum Kit/Drop on C1`"

    loops = {s["name"]: " | ".join(f"{spell(c, plan.get('key', ''))} ({b // 4 if b % 4 == 0 else b / 4} bar{'s' if b != 4 else ''})" for c, b in s.get("loop", []))
             for s in plan["sections"]}
    lines = [
        f"# {title} — Logic Pro draft", "",
        f"{bpm:g} BPM · 4/4 · key {plan.get('key', '?')} · every file starts at bar 1 (1 1 1 1).", "",
        "## Import (about 3 minutes)", "",
        f"1. **Open `{os.path.basename(mid_path)}` in Logic** (File > Open, or drag it onto the Logic icon). "
        "Logic makes a new project with the tempo, the section markers and one track per part. "
        "If you import it into an existing project instead (File > Import > MIDI File), say **yes** to importing the tempo.",
        "2. **Project sample rate:** File > Project Settings > Audio — set **44.1 kHz** before adding audio "
        "(the stems are 44.1 kHz; with another rate Logic must convert them on import).",
        "3. **Drag every file in `Stems/` into the empty area below the tracks at bar 1** and choose "
        "**Create new tracks**. They line up by themselves. Mute the tracks whose names start with `REF` — "
        "they are the original parts, there to compare against (solo a part and its REF in turn).",
    ]
    if a.kit:
        lines.append(
            "4. **Drums – cloned kit:** on the drum track open a **Sampler**, drag all files in "
            "`Drum Kit/Drop on C1` onto the keyboard at **C1** and pick **Zone per file** — they land in name "
            "order on notes 36, 37, 38 … (kick 36, snare 38, hat 42 are what the MIDI plays). Or load "
            "**Drum Machine Designer** and drag `036 Kick 1`, `038 Snare 1`, `042 Hat 1` onto the Kick/Snare/"
            "Closed-hat pads. Alternates for every pad are in `Drum Kit/Alternates`.")
    lines.append(f"{5 if a.kit else 4}. Pick instruments for the MIDI tracks (suggestions below), set levels by "
                 "matching each part to its REF track, then save.")
    lines += ["", "## Tracks", "", "MIDI (in the .mid file):"]
    lines += [f"- {n} — {c} notes" for n, c in midi_rows]
    lines += ["", "Audio (`Stems/`, in this order):"]
    lines += [f"- {n}{' — reference, mute it' if ref else ''}" for n, ref in audio_rows]
    if kit_note:
        lines += ["", f"Drum kit: {kit_note}."]
    lines += ["", "## Sections (markers)", ""]
    lines += [f"- **{s['name']}** — bars {s['bars'][0]}–{s['bars'][1]}" + (f": {loops[s['name']]}" if loops[s["name"]] else "")
              for s in plan["sections"]]
    ml = mix_lines(mix)
    if ml:
        lines += ["", "## First-mix starting points (what the Ableton draft used)", ""] + ml
        lines += ["", "Levels: in Ableton each part was set to its REF stem's playing level — do the same "
                  "by ear: solo the part, then its REF, and match."]
    lines += ["", "## Instrument suggestions", "",
              "- Drums: the cloned kit above (Sampler or Drum Machine Designer).",
              "- 808 / bass: an 808 patch (e.g. Alchemy or Sampler 808 presets) — the part stays in one low octave.",
              "- Keys: an electric piano or your own keys plugin — the held chords sit an octave low on purpose.",
              "- Melody: a soft lead or bell; it is the hook riff, one note at a time.", ""]
    open(os.path.join(a.out, "README.md"), "w").write("\n".join(lines))
    print(f"wrote {mid_path}: {len(mid.tracks) - 1} MIDI tracks + conductor ({len(plan['sections'])} markers, {bpm:g} BPM)")
    print(f"      {len(audio_rows)} stems, kit: {kit_note or 'none'}, README.md")


if __name__ == "__main__":
    main()
