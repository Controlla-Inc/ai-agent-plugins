"""Talk to Ableton Live through the (patched) AbletonMCP Remote Script socket.

Import it from other scripts (`from live import Live`) or run small commands:

  live.py tracks                         list tracks with devices + mixer
  live.py place-part <parts.json> <track> <part> <clip name>
  live.py place-audio <track> <file.wav> [--ref]   unwarped at beat 0 (--ref: muted via Utility)
  live.py verify                         tempo, arrangement clips, warping, REF mutes (waits 30 s first)
  live.py use-stem <part track> <ref track>   play the original stem, keep the MIDI part muted as an option
  live.py use-midi <part track> <ref track>   the reverse

MCP tool calls are too slow for thousands of notes; this writes straight to the socket.
"""
import json
import re
import socket
import sys
import time

HOST, PORT = "127.0.0.1", 9877
UTILITY, UTILITY_MUTE = "query:AudioFx#Utility", 10


def _num(s):
    return -120.0 if "inf" in s else float(re.findall(r"-?[\d.]+", s)[0])


class Live:
    def __init__(self, timeout=120):
        self.sock = socket.create_connection((HOST, PORT), timeout=timeout)

    def send(self, cmd, params=None):
        self.sock.sendall(json.dumps({"type": cmd, "params": params or {}}).encode())
        buf = b""
        while True:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError("socket closed")
            buf += chunk
            try:
                resp = json.loads(buf.decode())
                break
            except json.JSONDecodeError:
                continue
        if resp.get("status") == "error":
            raise RuntimeError(f"{cmd}: {resp.get('message')}")
        r = resp.get("result")
        return json.loads(r) if isinstance(r, str) and r[:1] in "{[" else r

    # ---- reading -------------------------------------------------------------------
    def track(self, t):
        return self.send("get_track_info", {"track_index": t})

    def track_count(self):
        return self.send("get_session_info")["track_count"]

    def all_devices(self):
        return {t: [d["name"] for d in self.track(t)["devices"]] for t in range(self.track_count())}

    def mixer(self, t):
        return self.send("set_mixer", {"track_index": t})

    # ---- devices -------------------------------------------------------------------
    def safe_load(self, t, uri):
        """Load a browser item and prove it landed on track t (loads can hot-swap or follow
        the selection onto another track). Returns the new device index."""
        before = self.all_devices()
        self.send("load_browser_item", {"track_index": t, "item_uri": uri})
        time.sleep(0.8)
        after = self.all_devices()
        strays = [k for k in after if k != t and after[k] != before.get(k)]
        if strays:
            raise RuntimeError(f"load of {uri} changed tracks {strays} instead of {t}: "
                               f"{[(k, before.get(k), after[k]) for k in strays]}")
        if len(after[t]) <= len(before[t]) and after[t] == before[t]:
            raise RuntimeError(f"load of {uri} did not change track {t}")
        return len(after[t]) - 1

    def delete_device(self, t, index, expect_name):
        return self.send("delete_device", {"track_index": t, "device_index": index, "expect_name": expect_name})

    # ---- mixer ---------------------------------------------------------------------
    def _bisect(self, t, target_db, key, idx=None):
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) / 2
            p = {"track_index": t}
            if key == "volume":
                p["volume"] = mid
            else:
                p["sends"] = {str(idx): mid}
            r = self.send("set_mixer", p)
            cur = _num(r["volume_str"] if key == "volume" else r["sends"][idx]["str"])
            lo, hi = (mid, hi) if cur < target_db else (lo, mid)
        return r["volume_str"] if key == "volume" else r["sends"][idx]["str"]

    def set_volume_db(self, t, db):
        return self._bisect(t, db, "volume")

    def set_send_db(self, t, send_index, db):
        return self._bisect(t, db, "send", send_index)

    def set_pan(self, t, pan):
        return self.send("set_mixer", {"track_index": t, "pan": pan})

    def volume_db(self, t):
        return _num(self.mixer(t)["volume_str"])

    # ---- clips ---------------------------------------------------------------------
    def clear_arrangement(self, t):
        for _ in self.send("get_arrangement_clips", {"track_index": t})["clips"]:
            self.send("delete_arrangement_clip", {"track_index": t, "clip_index": 0})

    def write_notes(self, t, slot, notes, length_beats, name):
        self.send("create_clip", {"track_index": t, "clip_index": slot, "length": float(length_beats)})
        for i in range(0, len(notes), 200):
            self.send("add_notes_to_clip", {"track_index": t, "clip_index": slot, "notes": [
                {"pitch": int(p), "start_time": float(s), "duration": float(d), "velocity": int(v), "mute": False}
                for p, s, d, v in notes[i:i + 200]]})
        self.send("set_clip_name", {"track_index": t, "clip_index": slot, "name": name})

    def place_part(self, t, notes, length_beats, name):
        """New Session clip in the first free slot, then it replaces the track's arrangement.
        Earlier versions stay in Session view so the user can A/B them."""
        slot = next(c["index"] for c in self.track(t)["clip_slots"] if not c["has_clip"])
        self.write_notes(t, slot, notes, length_beats, name)
        self.clear_arrangement(t)
        self.send("duplicate_session_clip_to_arrangement", {"track_index": t, "clip_index": slot, "destination_time": 0.0})
        return slot

    def place_audio(self, t, path, ref=False):
        """Import unwarped at beat 0. Live's auto-warp mis-stretches long stems and can flip
        warping on a few seconds after import, so: wait for analysis, force warping off on
        the Session clip, THEN copy to the arrangement (the copy inherits warping)."""
        slot = next(c["index"] for c in self.track(t)["clip_slots"] if not c["has_clip"])
        self.send("create_audio_clip", {"track_index": t, "clip_index": slot, "path": path, "warping": False})
        last, stable = None, 0
        for _ in range(30):
            time.sleep(1)
            c = self.track(t)["clip_slots"][slot]["clip"]
            cur = c["length"] if c else None
            stable = stable + 1 if cur == last else 0
            last = cur
            if stable >= 2:
                break
        time.sleep(2)
        self.send("set_clip_warping", {"track_index": t, "clip_index": slot, "warping": False})
        self.clear_arrangement(t)
        self.send("duplicate_session_clip_to_arrangement", {"track_index": t, "clip_index": slot, "destination_time": 0.0})
        if ref:
            self.mute_with_utility(t)
        return slot

    def mute_with_utility(self, t, mute=True):
        """The connector has no track-mute command; a Utility with Mute on does the job."""
        devs = [d["name"] for d in self.track(t)["devices"]]
        i = devs.index("Utility") if "Utility" in devs else self.safe_load(t, UTILITY)
        self.send("set_device_parameter", {"track_index": t, "device_index": i,
                                           "parameter_index": UTILITY_MUTE, "value": 1.0 if mute else 0.0})

    def use_stem(self, part_t, ref_t, stem=True):
        """Make the original stem the playing part (stem=True) or go back to the MIDI part.
        The other one stays on its track, muted, as the option. The playing track gets the
        part's pan and sends, so the space in the mix stays the same."""
        play, keep = (ref_t, part_t) if stem else (part_t, ref_t)
        self.mute_with_utility(play, False)
        self.mute_with_utility(keep, True)
        m = self.mixer(keep)
        self.send("set_mixer", {"track_index": play, "pan": m["pan"],
                                "sends": {str(i): s["value"] for i, s in enumerate(m["sends"])}})
        return self.track(play)["name"], self.track(keep)["name"]

    def add_locator(self, beat, name=None):
        # the playhead moves asynchronously; a combined call drops the cue at the OLD position
        self.send("set_current_song_time", {"time": float(beat)})
        time.sleep(0.3)
        return self.send("create_locator", {"time": float(beat), "name": name} if name else {"time": float(beat)})


def verify(live):
    time.sleep(30)  # late auto-warp shows up after a few seconds
    print("tempo", round(live.send("get_session_info")["tempo"], 2))
    arrs = {t: live.send("get_arrangement_clips", {"track_index": t})["clips"] for t in range(live.track_count())}
    midi_end = max([c["end_time"] for a in arrs.values() for c in a if c["is_midi_clip"]] or [0])
    for t in range(live.track_count()):
        tr = live.track(t)
        # an auto-warped stem ends far from the song end (its seconds read as beats)
        clips = " ".join(f"{c['start_time']:.0f}-{c['end_time']:.2f}"
                         f"{' CHECK-LENGTH' if c['is_audio_clip'] and midi_end and abs(c['end_time'] - midi_end) > 8 else ''}"
                         for c in arrs[t]) or "—"
        mute = ""
        for i, d in enumerate(tr["devices"]):
            if d["name"] == "Utility":
                ps = live.send("get_device_parameters", {"track_index": t, "device_index": i})["device"]["parameters"]
                muted = any(p["name"] == "Mute" and p["value"] == 1 for p in ps)
                # a Utility on a part track is a gain boost (mix.py), not a mute
                mute = "muted" if muted else ("NOT muted" if tr["name"].startswith("REF") else "")
        m = live.mixer(t)
        print(f"{t:>2} {tr['name']:<28} {clips:<18} {mute:<9} {m['volume_str']:>9} pan {m['pan']:+.2f} "
              f"sends {[s['str'] for s in m['sends']]} {[d['name'] for d in tr['devices']]}")


def main():
    live = Live()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tracks"
    if cmd == "tracks":
        for t in range(live.track_count()):
            m = live.mixer(t)
            print(t, live.track(t)["name"], [d["name"] for d in live.track(t)["devices"]], m["volume_str"], f"{m['pan']:+.2f}")
    elif cmd == "place-part":
        data = json.load(open(sys.argv[2]))
        t, part, name = int(sys.argv[3]), sys.argv[4], sys.argv[5]
        slot = live.place_part(t, data["parts"][part], data["length_beats"], name)
        print(f"track {t}: {part} -> slot {slot}, {len(data['parts'][part])} notes")
    elif cmd == "place-audio":
        t, path = int(sys.argv[2]), sys.argv[3]
        print("slot", live.place_audio(t, path, ref="--ref" in sys.argv))
    elif cmd in ("use-stem", "use-midi"):
        part_t, ref_t = int(sys.argv[2]), int(sys.argv[3])
        play, keep = live.use_stem(part_t, ref_t, stem=(cmd == "use-stem"))
        print(f"playing: {play}   muted option: {keep}")
    elif cmd == "verify":
        verify(live)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
