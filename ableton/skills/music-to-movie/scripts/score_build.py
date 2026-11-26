"""Build a cue in Ableton Live from cue.json: picture on the timeline, song stems, MIDI parts
with automation, sound design, locators on every cut.

Usage: score_build.py cue.json [--keep-default-tracks | --replace]   (--replace deletes ALL existing tracks)
       score_build.py cue.json --part "<track name>"     re-place one MIDI track's notes + automation
       score_build.py cue.json --locators                 (re)create the cut markers only
       score_build.py cue.json --verify                  re-check clip lengths (run ~30 s after a build)

Needs the ai-song-to-ableton connector WITH the music-to-movie commands (set_clip_envelope,
create_arrangement_audio_clip, set_track_mute, delete_track): `live.py` is imported from that
skill. Build into a fresh empty set; the default tracks are removed at the end.

cue.json (written by a per-cue make_cue.py - see examples/):
  bpm, length_beats, parts{name: [[pitch, start_beat, length_beats, velocity], ...]},
  locators[[beat, name]], tracks[...] in top-to-bottom order, each one of
   video  {name, file, mute}                 picture at 1.1.1; mute silences its own audio
   audio  {name, db, mute?, clips[{file, beat, pre_ms?} | {file, at_s, sync_s, db?, name?}]}
          at_s is PICTURE time; the file's sync point (trailer_sfx.py's sfx.json) lands on it
   midi   {name, part, db, load[browser URIs], automation[{device, param, points[[beat, value]]}]}
          automation values: dB for Utility "Gain" (the expression fader - the track fader stays
          free for mixing), otherwise the parameter's own units. Points are joined by straight
          lines, written as 1/8-beat steps into the Session clip, then copied to the Arrangement.
"""
import json, os, sys, time
import numpy as np
import soundfile as sf

for _d in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "song-to-session", "scripts"),
           os.path.expanduser("~/.claude/skills/ai-song-to-ableton/scripts")):
    if os.path.isdir(_d):
        sys.path.insert(0, _d)
        break
from live import Live  # noqa: E402

STEP = 0.125


def steps_from_points(points, to_value):
    pts = sorted(points)
    out = []
    t = pts[0][0]
    while t < pts[-1][0] - 1e-9:
        v = np.interp(t + STEP / 2, [p[0] for p in pts], [p[1] for p in pts])
        out.append([round(t, 4), STEP, float(to_value(v))])
        t += STEP
    out.append([round(pts[-1][0], 4), STEP, float(to_value(pts[-1][1]))])
    return out


def write_midi(L, t, tr, cue):
    notes = cue["parts"][tr["part"]]
    length = float(cue["length_beats"])
    slot = next(c["index"] for c in L.track(t)["clip_slots"] if not c["has_clip"])
    L.write_notes(t, slot, notes, length, tr["part"])
    devs = L.track(t)["devices"]
    for a in tr.get("automation", []):
        di = next(d["index"] for d in devs if d["name"] == a["device"])
        params = L.send("get_device_parameters", {"track_index": t, "device_index": di})["device"]["parameters"]
        pname = "Output" if (a["device"], a["param"]) == ("Utility", "Gain") else a["param"]   # Live calls Utility's gain "Output"
        p = next(x for x in params if x["name"] == pname)
        conv = lambda v: v
        if a.get("unit", "db" if pname == "Output" else "raw") == "db":
            # raw value <-> what the device displays is not linear (Utility: 35 dB per unit down to
            # -17.5 dB, steeper below), so invert the device's own display strings
            raws = [p["min"] + (p["max"] - p["min"]) * i / 400.0 for i in range(401)]
            strs = L.send("get_parameter_strings", {"track_index": t, "device_index": di, "parameter_index": p["index"], "values": raws})["strings"]
            dbs = [-120.0 if "inf" in x else float(x.split()[0]) for x in strs]
            conv = lambda db: float(np.interp(db, dbs, raws))
        r = L.send("set_clip_envelope", {"track_index": t, "clip_index": slot, "device_index": di,
                                         "parameter_index": p["index"], "clear": True,
                                         "steps": steps_from_points(a["points"], conv)})
        print("   automation %s/%s: %d steps" % (a["device"], r["parameter"], r["steps"]))
    L.clear_arrangement(t)
    L.send("duplicate_session_clip_to_arrangement", {"track_index": t, "clip_index": slot, "destination_time": 0.0})
    return len(notes)


def placed_file(c, folder, head_s=0.0):
    """A clip with its own gain gets a level-baked copy (the connector has no clip gain); a clip
    that would start before 1.1.1 gets its head (head_s) cut off the copy."""
    if not c.get("db") and head_s <= 0 and not c.get("trim_to_s"):
        return c["file"]
    os.makedirs(folder, exist_ok=True)
    y, sr = sf.read(c["file"], always_2d=True)
    if c.get("trim_to_s"):                       # tail faded over its last 0.3 s instead of being chopped by the next clip
        y = y[:int(c["trim_to_s"] * sr)].copy()
        n = min(len(y), int(0.3 * sr))
        y[-n:] *= np.linspace(1, 0, n)[:, None]
    y = y[int(round(head_s * sr)):]
    # Live remembers a file's length by NAME (.asd + its own cache): a changed copy must get a new name
    name = "%s @ %.2fs (%+.0f dB%s%s).wav" % (os.path.splitext(os.path.basename(c["file"]))[0],
                                              c.get("at_s", c.get("beat", 0)), c.get("db", 0),
                                              ", tail %.2fs" % c["trim_to_s"] if c.get("trim_to_s") else "",
                                              ", head -%.3fs" % head_s if head_s > 0 else "")
    out = os.path.join(folder, name)
    sf.write(out, y * 10 ** (c.get("db", 0) / 20), sr, subtype="PCM_24")
    return out


def clip_beat(c, beat_s):
    if "at_s" in c:
        return (c["at_s"] - c.get("sync_s", 0.0)) / beat_s
    return c["beat"] - c.get("pre_ms", 0) / 1000.0 / beat_s


def with_lanes(cue):
    """Live allows one clip at a time per track: a later clip CUTS the tail of an earlier one
    (an impact's 6 s tail dies at the next hit). Overlapping clips are spread over lanes:
    "<name>", "<name> (lane 2)", ... - returns the track list with those extra tracks."""
    beat_s = 60.0 / cue["bpm"]
    out = []
    for tr in cue["tracks"]:
        if tr["kind"] != "audio":
            out.append(tr); continue
        lanes, cap = [], int(tr.get("max_lanes", 2))
        for c in sorted(tr["clips"], key=lambda c: clip_beat(c, beat_s)):
            a = max(0.0, clip_beat(c, beat_s)); z = a + sf.info(c["file"]).duration / beat_s
            free = [ln for ln in lanes if ln[-1][2] <= a + 1e-6]
            if free:
                free[0].append((c, a, z))
            elif len(lanes) < cap:
                lanes.append([(c, a, z)])
            else:                                # no lane left: fade out the tail that has rung longest
                ln = min(lanes, key=lambda ln: ln[-1][1])
                pc, pa, pz = ln[-1]
                ln[-1] = (dict(pc, trim_to_s=(a - pa) * beat_s), pa, a)
                ln.append((c, a, z))
        for i, lane in enumerate(lanes):
            out.append(dict(tr, name=tr["name"] if i == 0 else "%s (lane %d)" % (tr["name"], i + 1), clips=[c for c, _, _ in lane]))
    return out


def verify(L, cue):
    beat_s = 60.0 / cue["bpm"]
    names = {L.track(i)["name"]: i for i in range(L.track_count())}
    bad = 0
    for tr in with_lanes(cue):
        t = names.get(tr["name"])
        if t is None:
            print("MISSING TRACK", tr["name"]); bad += 1; continue
        clips = L.send("get_arrangement_clips", {"track_index": t})["clips"]
        files = [tr] if tr["kind"] == "video" else tr.get("clips", [])
        if tr["kind"] != "midi" and len(clips) != len(files):
            print("CHECK %s: %d clips, expected %d" % (tr["name"], len(clips), len(files))); bad += 1
        for c, f in zip(sorted(clips, key=lambda x: x["start_time"]), sorted(files, key=lambda x: clip_beat(x, beat_s) if "file" in x and tr["kind"] != "video" else 0)):
            if tr["kind"] != "audio":
                continue
            want = f["trim_to_s"] / beat_s if f.get("trim_to_s") else sf.info(f["file"]).duration / beat_s
            if abs(c["length"] - want) > max(0.05, want * 0.005) and c["start_time"] > 0.001:
                print("CHECK-LENGTH %s / %s: %.2f beats, file is %.2f (auto-warp?)" % (tr["name"], c["name"], c["length"], want)); bad += 1
    print("verify:", "ok" if not bad else "%d problem(s)" % bad)


def main():
    cue = json.load(open(sys.argv[1]))
    L = Live()
    beat_s = 60.0 / cue["bpm"]
    if "--verify" in sys.argv:
        return verify(L, cue)
    if "--locators" in sys.argv:
        for bt, name in cue.get("locators", []):
            try:
                L.send("set_current_song_time", {"time": float(bt)}); time.sleep(0.8)
                print(L.send("create_locator", {"time": float(bt), "name": name}))
            except Exception as e:
                print("failed", name, e)
        return
    if "--part" in sys.argv:
        name = sys.argv[sys.argv.index("--part") + 1]
        t = next(i for i in range(L.track_count()) if L.track(i)["name"] == name)
        tr = next(x for x in cue["tracks"] if x["name"] == name)
        print(name, write_midi(L, t, tr, cue), "notes")
        return
    L.send("set_tempo", {"tempo": float(cue["bpm"])})
    import re
    defaults = [(i, L.track(i)["name"]) for i in range(L.track_count())]
    mine = [n for _, n in defaults if not re.match(r"^\d+[- ](MIDI|Audio)$", n)]
    if mine and "--replace" not in sys.argv and "--keep-default-tracks" not in sys.argv:
        raise SystemExit("this set already has tracks (%s ...). Build into a fresh set, or pass --replace to DELETE every "
                         "existing track and rebuild, or --keep-default-tracks to add below them." % ", ".join(mine[:3]))
    folder = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "Placed")
    for tr in with_lanes(cue):
        kind = "create_midi_track" if tr["kind"] == "midi" else "create_audio_track"
        L.send(kind, {"index": -1})
        t = L.track_count() - 1
        L.send("set_track_name", {"track_index": t, "name": tr["name"]})
        print("%2d %s" % (t, tr["name"]))
        if tr["kind"] == "video":
            r = L.send("create_arrangement_audio_clip", {"track_index": t, "path": tr["file"], "position": 0.0,
                                                         "warping": False, "name": os.path.basename(tr["file"])})
            print("   picture: %.2f beats = %.2f s" % (r["length"], r["length"] * beat_s))
        elif tr["kind"] == "audio":
            for c in sorted(tr["clips"], key=lambda c: clip_beat(c, beat_s)):
                pos = clip_beat(c, beat_s)
                head = 0.0
                if pos < 0:                      # a pre-roll or a riser that begins before the picture: lose the head
                    head, pos = -pos * beat_s, 0.0
                    if head > 0.1:
                        print("   !! %s loses its first %.2f s (starts before 1.1.1)" % (os.path.basename(c["file"]), head))
                r = L.send("create_arrangement_audio_clip", {"track_index": t, "path": placed_file(c, folder, head), "position": pos,
                                                             "warping": False, "name": c.get("name", "")})
                print("   %-28s at beat %6.2f (%.2f s)" % (r["name"][:28], pos, pos * beat_s))
        else:
            for uri in tr.get("load", []):
                L.safe_load(t, uri)
            print("   %d notes" % write_midi(L, t, tr, cue))
        if "db" in tr:
            L.set_volume_db(t, tr["db"])
        if tr.get("mute"):
            L.send("set_track_mute", {"track_index": t, "mute": True})
    if "--keep-default-tracks" not in sys.argv:
        for i, name in reversed(defaults):
            L.send("delete_track", {"track_index": i, "expect_name": name})
    for bt, name in cue.get("locators", []):
        try:                                     # a marker must never abort a finished build
            L.send("set_current_song_time", {"time": float(bt)}); time.sleep(0.8)
            L.send("create_locator", {"time": float(bt), "name": name})
        except Exception as e:
            print("   !! locator %r at beat %.2f not created (%s) - add it by hand or re-run --locators" % (name, bt, e))
    L.send("set_current_song_time", {"time": 0.0})
    L.send("switch_to_arrangement_view")
    print("built. Run --verify in ~30 s, then ask the user to save (Cmd-S).")


if __name__ == "__main__":
    main()
