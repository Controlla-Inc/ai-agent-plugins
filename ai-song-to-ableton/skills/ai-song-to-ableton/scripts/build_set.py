"""Build the draft in the OPEN Live set (start from a fresh, empty default set) from a layout.

Usage: build_set.py <layout.json> <parts.json> [plan.json]

layout.json:
{
  "tracks": [                                   # final order, top to bottom
    {"kind": "midi",  "name": "Drums",   "part": "Drums", "load": ["query:UserLibrary#Presets:Instruments:Drum%20Rack:..."]},
    {"kind": "ref",   "name": "REF – Drums (stem)", "file": "/abs/aligned/drums.wav"},
    {"kind": "midi",  "name": "Bass",    "part": "Bass",  "load": ["query:Sounds#Bass:FileId_6589"]},
    {"kind": "audio", "name": "Vocals",  "file": "/abs/aligned/vocals.wav"},
    {"kind": "ref",   "name": "REF – Full original mix", "file": "/abs/aligned/full.wav"}
  ],
  "master": ["query:AudioFx#Glue%20Compressor"]  # optional
}
"ref" = audio muted with a Utility, placed directly under the part it references, so the
user can solo-compare. With plan.json, a locator is added at every section start.
Tempo comes from parts.json. Every load is verified (Live.safe_load).
"""
import json
import sys

from live import Live


def ensure_track(live, t, midi):
    """Reuse the default set's empty track at t if its type matches, else insert one."""
    if t < live.track_count():
        tr = live.track(t)
        if tr["is_midi_track"] == midi and not tr["devices"] and not any(c["has_clip"] for c in tr["clip_slots"]):
            return
    live.send("create_midi_track" if midi else "create_audio_track", {"index": t})


def main():
    layout, parts = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
    plan = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    live = Live()
    live.send("set_tempo", {"tempo": parts["bpm"]})
    for t, row in enumerate(layout["tracks"]):
        midi = row["kind"] == "midi"
        ensure_track(live, t, midi)
        live.send("set_track_name", {"track_index": t, "name": row["name"]})
        for uri in row.get("load", []):
            live.safe_load(t, uri)
        if midi:
            notes = parts["parts"][row["part"]]
            live.place_part(t, notes, parts["length_beats"], row.get("clip", row["name"]))
            print(f"{t:>2} {row['name']}: {len(notes)} notes")
        else:
            live.place_audio(t, row["file"], ref=row["kind"] == "ref")
            print(f"{t:>2} {row['name']}: audio{' (muted ref)' if row['kind'] == 'ref' else ''}")
    for uri in layout.get("master", []):
        live.send("load_browser_item", {"track_index": -1, "item_uri": uri})
    if plan:
        for sec in plan["sections"]:
            live.add_locator((sec["bars"][0] - 1) * 4.0, sec["name"])
    live.send("set_current_song_time", {"time": 0.0})
    print("done – run `live.py verify` to catch late auto-warp")


if __name__ == "__main__":
    main()
