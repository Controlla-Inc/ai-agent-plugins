"""First-pass mix from a mix.json: insert chains + EQ, level match to the reference stems,
then pan / reverb + delay sends / small nudges. Tracks are addressed by NAME, not index.

Usage:
  mix.py chains <mix.json>        EQ Eight (reused if present) + extra devices per track
  mix.py levels <mix.json>        match each part (or group) to its REF stem's playing level
  mix.py space  <mix.json>        pans, sends, fader nudges
  mix.py all    <mix.json>        the three, in that order

mix.json:
{
  "measure_at_beat": 128,              # a section where everything plays
  "calibrate_on": "Piano",             # a sustained part for the meter calibration (not drums)
  "tracks": {
    "Vocals": {"eq": [[1, "lowcut12", 100, 0, 0.71], [2, "bell", 300, -2.5, 0.9]],
               "load": ["query:AudioFx#Compressor:FileId_8183"],
               "pan": 0, "reverb_db": -14, "delay_db": -20, "nudge_db": 1.5},
    ...
  },
  "level_groups": {"keys": [["Piano", "Electric piano", "Jazz guitar"], "REF – Keys + guitar (stem)"], ...}
}
EQ band: [band 1-8, type, Hz, gain dB, Q]; types lowcut48 lowcut12 lowshelf bell notch highshelf highcut12 highcut48.
Sends: index 0 = Return A (reverb), 1 = Return B (delay) in Live's default set. Return
devices themselves cannot be edited through the connector – leave Live's defaults.

Every load goes through Live.safe_load, which raises if a device lands on another track
(this happened: a Drum Rack got hot-swapped and vocal compressors landed on the drums).
"""
import json
import math
import sys
import time

from live import Live

EQ = "query:AudioFx#EQ%20Eight"
TYPES = {k: i for i, k in enumerate(["lowcut48", "lowcut12", "lowshelf", "bell", "notch", "highshelf", "highcut12", "highcut48"])}


def fnorm(hz):
    return math.log(hz / 10.0) / math.log(2200.0)


def qnorm(q):
    return max(0.0, min(1.0, math.log(q / 0.1) / math.log(180.0)))


def index_by_name(live):
    return {live.track(t)["name"]: t for t in range(live.track_count())}


def chains(live, cfg):
    idx = index_by_name(live)
    for name, spec in cfg["tracks"].items():
        t = idx[name]
        devs = [d["name"] for d in live.track(t)["devices"]]
        if spec.get("eq"):
            di = devs.index("EQ Eight") if "EQ Eight" in devs else live.safe_load(t, EQ)
            p = lambda i, v: live.send("set_device_parameter", {"track_index": t, "device_index": di, "parameter_index": i, "value": v})
            for k in range(1, 9):
                p(4 + 10 * (k - 1), 0.0)
            for band, typ, hz, gain, q in spec["eq"]:
                b = 4 + 10 * (band - 1)
                p(b, 1.0); p(b + 1, float(TYPES[typ])); p(b + 2, fnorm(hz)); p(b + 3, float(gain)); p(b + 4, qnorm(q))
        for uri in spec.get("load", []):
            live.safe_load(t, uri)
        print(f"{t:>2} {name:<24} {[d['name'] for d in live.track(t)['devices']]}")


def _measure(live, beat, seconds=10.0):
    # Live starts playback from its start marker, not the playhead: jump AFTER starting
    live.send("start_playback")
    time.sleep(0.3)
    live.send("set_current_song_time", {"time": beat})
    time.sleep(1.0)
    now = live.send("get_meters")["time"]
    if not beat <= now < beat + 8:
        live.send("stop_playback")
        raise RuntimeError(f"playhead at {now:.1f}, expected ~{beat} – measurement would be of the wrong section")
    acc, n, end = {}, 0, time.time() + seconds
    while time.time() < end:
        for i, tr in enumerate(live.send("get_meters")["tracks"]):
            acc[i] = acc.get(i, 0.0) + max(tr["l"], tr["r"]) ** 2
        n += 1
        time.sleep(0.05)
    live.send("stop_playback")
    return {i: math.sqrt(v / n) for i, v in acc.items()}


UTILITY, UTIL_GAIN = "query:AudioFx#Utility", 9  # Utility "Output"/Gain: 0 = 0 dB, 1 ≈ +35 dB


def _set_boost(live, t, db):
    devs = [d["name"] for d in live.track(t)["devices"]]
    i = devs.index("Utility") if "Utility" in devs else live.safe_load(t, UTILITY)
    live.send("set_device_parameter", {"track_index": t, "device_index": i, "parameter_index": UTIL_GAIN, "value": db / 35.0})
    # A boost Utility must never be muted (Mute = param 10 is how REF tracks are silenced;
    # on "Lagos Rooftop" the drums' boost Utility came up muted and level matching chased silence).
    live.send("set_device_parameter", {"track_index": t, "device_index": i, "parameter_index": 10, "value": 0.0})


def levels(live, cfg):
    """Master is pulled to -inf while measuring (nothing audible) and REF mutes are lifted
    only for the measurement; both are restored even on error."""
    idx = index_by_name(live)
    groups = {k: ([idx[p] for p in parts], idx[ref]) for k, (parts, ref) in cfg["level_groups"].items()}
    refs = {r for _, r in groups.values()}
    beat = float(cfg.get("measure_at_beat", 0))
    master = live.mixer(-1)["volume"]
    if master < 0.05:  # never "restore" a silent master (a debug run once left it at -inf)
        master = 0.85  # Live's 0 dB
    live.send("set_mixer", {"track_index": -1, "volume": 0.0})
    for r in refs:
        live.mute_with_utility(r, False)
    try:
        # Re-runs start clean: drop any Utility boost a previous run left on a part.
        for parts, _ in groups.values():
            for p in parts:
                if "Utility" in [d["name"] for d in live.track(p)["devices"]]:
                    _set_boost(live, p, 0.0)
        # Calibrate on a SUSTAINED part (keys/pads), never drums: bursty drum meters once
        # gave a < b, a negative k, and every correction then went the wrong way.
        cal_name = cfg.get("calibrate_on")
        cal = idx[cal_name] if cal_name else groups[next(iter(groups))][0][0]
        start = live.volume_db(cal)
        live.set_volume_db(cal, 0.0)
        a = _measure(live, beat)[cal]
        live.set_volume_db(cal, -6.0)
        b = _measure(live, beat)[cal]
        live.set_volume_db(cal, start)
        if not a > b * 1.05:  # Live meters are compressed: 6 dB moves them only ~10-30%
            raise RuntimeError(f"calibration failed on track {cal}: 0 dB read {a:.4g}, -6 dB read {b:.4g} – "
                               "pick a steadier 'calibrate_on' part or another measure_at_beat")
        k = 6.0 / math.log(a / b)  # meter units -> dB
        print(f"calibrated on track {cal}: k={k:.2f}")
        to_db = lambda v: k * math.log(max(v, 1e-4))
        boost = {}  # extra gain beyond the fader's +6 dB lives on a Utility (quiet stock presets need it)
        for rnd in range(4):
            m = _measure(live, beat)
            worst = 0.0
            for name, (parts, ref) in groups.items():
                g = 10 * math.log10(sum(10 ** (to_db(m[p]) / 10) for p in parts))
                delta = to_db(m[ref]) - g
                worst = max(worst, abs(delta))
                for p in parts:
                    total = live.volume_db(p) + boost.get(p, 0.0) + delta
                    live.set_volume_db(p, max(-30.0, min(6.0, total)))
                    if total > 6.0 or boost.get(p):
                        boost[p] = min(35.0, max(0.0, total - 6.0))
                        _set_boost(live, p, boost[p])
                print(f"round {rnd + 1} {name:<8} part {g:6.1f} vs ref {to_db(m[ref]):6.1f} -> {delta:+.1f} dB"
                      + (f" (utility +{max(boost.get(p, 0) for p in parts):.1f} dB)" if any(boost.get(p) for p in parts) else ""))
            if worst < 1.0:
                break
    finally:
        for r in refs:
            live.mute_with_utility(r, True)
        live.send("set_mixer", {"track_index": -1, "volume": master})
        live.send("stop_playback")
        live.send("set_current_song_time", {"time": 0.0})


def space(live, cfg):
    idx = index_by_name(live)
    for name, spec in cfg["tracks"].items():
        t = idx[name]
        if "pan" in spec:
            live.set_pan(t, spec["pan"])
        if spec.get("reverb_db") is not None:
            live.set_send_db(t, 0, spec["reverb_db"])
        if spec.get("delay_db") is not None:
            live.set_send_db(t, 1, spec["delay_db"])
        if spec.get("nudge_db"):
            live.set_volume_db(t, live.volume_db(t) + spec["nudge_db"])
        m = live.mixer(t)
        print(f"{t:>2} {name:<24} {m['volume_str']:>9} pan {m['pan']:+.2f} sends {[s['str'] for s in m['sends']]}")


def main():
    cmd, cfg = sys.argv[1], json.load(open(sys.argv[2]))
    live = Live()
    for step in (("chains", "levels", "space") if cmd == "all" else (cmd,)):
        print(f"== {step}")
        {"chains": chains, "levels": levels, "space": space}[step](live, cfg)


if __name__ == "__main__":
    main()
