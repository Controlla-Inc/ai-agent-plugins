"""Write a cue's MIDI parts as files the user can keep or take to another DAW.

Usage: export_midi.py cue.json <outdir>
Writes <Title>.mid (format 1: tempo, a marker per locator, one named track per part; the kit
part on channel 10) and one single-track .mid per part. Starts at the cue's beat 0 = picture 0.
"""
import json, os, sys
import mido

cue = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
TPB = 480
clean = lambda s: s.replace("–", "-").replace("—", "-").encode("latin-1", "replace").decode("latin-1")


def track(name, notes, ch):
    tr = mido.MidiTrack([mido.MetaMessage("track_name", name=clean(name), time=0)])
    ev = []
    for p, s, d, v in notes:
        ev.append((int(round(s * TPB)), 1, mido.Message("note_on", note=int(p), velocity=int(v), channel=ch)))
        ev.append((int(round((s + d) * TPB)), 0, mido.Message("note_off", note=int(p), velocity=0, channel=ch)))
    last = 0
    for t, _, m in sorted(ev, key=lambda e: (e[0], e[1])):
        tr.append(m.copy(time=t - last)); last = t
    return tr


def conductor():
    tr = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(cue["bpm"]), time=0),
                         mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0)])
    last = 0
    for b, name in sorted(cue.get("locators", [])):
        t = int(round(b * TPB)); tr.append(mido.MetaMessage("marker", text=clean(name), time=t - last)); last = t
    return tr


full = mido.MidiFile(type=1, ticks_per_beat=TPB); full.tracks.append(conductor())
ch = 0
for tr in cue["tracks"]:
    if tr["kind"] != "midi":
        continue
    c = 9 if tr.get("kit_dir") else ch
    t = track(tr["name"], cue["parts"][tr["part"]], c)
    full.tracks.append(t)
    one = mido.MidiFile(type=1, ticks_per_beat=TPB); one.tracks += [conductor(), t]
    one.save(os.path.join(out, clean(tr["part"]) + ".mid"))
    ch += 0 if c == 9 else 1
path = os.path.join(out, clean(cue["title"]) + ".mid"); full.save(path)
print(path, "+", len(full.tracks) - 1, "part files")
