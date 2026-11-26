"""Play the cue once with the MASTER pulled to silence and read every track's meter.

Usage: meter_pass.py cue.json [--sections 0,5,9,16,20,24]
Catches what you cannot hear from here: a silent track (instrument failed to load, clip
missing), a track that only wakes up in the wrong section, and tracks far hotter than the
rest. Meters are peak-ish and compressed (6 dB moves them ~10-30 %), so read them as
"silent / present / loud", not as dB. The master is restored even on error.
"""
import json, os, sys, time
import numpy as np
for _d in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "song-to-session", "scripts"),
           os.path.expanduser("~/.claude/skills/ai-song-to-ableton/scripts")):
    if os.path.isdir(_d):
        sys.path.insert(0, _d)
        break
from live import Live  # noqa: E402

cue = json.load(open(sys.argv[1]))
edges = [float(x) for x in sys.argv[sys.argv.index("--sections") + 1].split(",")] if "--sections" in sys.argv \
    else sorted({0.0, float(cue["length_beats"])} | {round(b) for b, _ in cue.get("locators", []) if b < cue["length_beats"]})
L = Live()
master = L.mixer(-1)["volume"]
L.send("set_mixer", {"track_index": -1, "volume": 0.0})
rows = []
try:
    L.send("start_playback"); time.sleep(0.2)
    L.send("set_current_song_time", {"time": 0.0})       # playback starts at Live's start marker, not the playhead
    end = cue["length_beats"] * 60.0 / cue["bpm"]
    t0 = time.time()
    while time.time() - t0 < end + 0.5:
        r = L.send("get_meters")
        rows.append((r["time"], [max(x["l"], x["r"]) for x in r["tracks"]]))
        time.sleep(0.06)
    names = [x["name"] for x in r["tracks"]]
finally:
    L.send("stop_playback")
    L.send("set_mixer", {"track_index": -1, "volume": master if master > 0.05 else 0.85})
    L.send("set_current_song_time", {"time": 0.0})
T = np.array([r[0] for r in rows]); A = np.array([r[1] for r in rows])
segs = list(zip(edges[:-1], edges[1:]))
print("%-44s" % "peak meter per section (beats)", " ".join("%4g-%-4g" % s for s in segs))
for i, n in enumerate(names):
    vals = [A[(T >= a) & (T < b), i].max() if ((T >= a) & (T < b)).any() else float("nan") for a, b in segs]
    flag = "  <-- SILENT" if np.nanmax(vals) < 0.01 and "REF" not in n and "VIDEO" not in n else ""
    print("%-44s" % n[:44], " ".join("  %5.2f  " % v for v in vals) + flag)
