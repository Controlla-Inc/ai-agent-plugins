"""Read a video's edit: cuts, a contact sheet, and the tempo whose beats land on the cuts.

Usage: cut_map.py <video> <outdir> [--thresh 0.2] [--bpm-range 70 180] [--weights t=w,...]
                  [--bpm 113 --offset 0.0]   (skip the search and just print the beat map)

Writes <outdir>/cuts.json  {duration, fps, cuts:[{t, score}], tempo:{bpm, offset, beat_s},
                            map:[{t, beat, nearest, miss_ms}]}
       <outdir>/sheet.jpg  4 frames per second, 8 per row (index i = i/4 s) - LOOK at it:
                           the cue is written from what happens in each shot, not from numbers.

Tempo search: every candidate BPM x phase is scored by the weighted squared distance of each
cut to the nearest beat. Cuts the story hangs on (the title card, the biggest reveal) should
get a higher weight (--weights 8.5=3,4.77=2). Phase 0 is preferred when it is nearly as good,
so the video can sit at 1.1.1 and the title lands on a bar line. Half/double tempos fit the
same cuts - choose by feel (trailers: 100-130 felt in half time works well).
"""
import argparse, json, re, subprocess, sys
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(video):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=r_frame_rate:format=duration", "-of", "json", video])
    j = json.loads(r.stdout)
    n, d = j["streams"][0]["r_frame_rate"].split("/")
    return float(j["format"]["duration"]), float(n) / float(d)


def detect(video, thresh):
    r = run(["ffmpeg", "-hide_banner", "-i", video, "-vf",
             f"select='gt(scene,{thresh})',metadata=print", "-an", "-f", "null", "-"])
    ts = re.findall(r"pts_time:([\d.]+)", r.stderr)
    sc = re.findall(r"scene_score=([\d.]+)", r.stderr)
    cuts = [{"t": round(float(t), 3), "score": round(float(s), 3)} for t, s in zip(ts, sc)]
    out = []                       # a flash or dissolve fires on several frames in a row: keep the strongest
    for c in cuts:
        if out and c["t"] - out[-1]["t"] < 0.25:
            if c["score"] > out[-1]["score"]:
                out[-1] = c
        else:
            out.append(c)
    return [c for c in out if c["t"] > 0.1]


def fit(times, weights, lo, hi):
    best = []
    for b10 in range(int(lo * 10), int(hi * 10) + 1):
        bpm = b10 / 10.0
        beat = 60.0 / bpm
        for k in range(int(beat * 100)):
            off = k / 100.0
            e = sum(w * (((t - off) / beat) - round((t - off) / beat)) ** 2 * beat * beat
                    for t, w in zip(times, weights))
            best.append((e + (0.0 if off == 0 else 0.004), bpm, off))
    best.sort()
    keep = []
    for e, bpm, off in best:
        if all(abs(bpm - k[1]) > 2.5 for k in keep):
            keep.append((e, bpm, off))
        if len(keep) == 8:
            break
    return keep


def beat_map(times, bpm, off):
    beat = 60.0 / bpm
    rows = []
    for t in times:
        b = (t - off) / beat
        q = round(b * 4) / 4
        rows.append({"t": t, "beat": round(b, 3), "bar_beat": "%d.%d" % (int(b // 4) + 1, int(b % 4) + 1),
                     "nearest_16th": q, "miss_ms": round((b - round(b)) * beat * 1000)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("outdir")
    ap.add_argument("--thresh", type=float, default=0.2)
    ap.add_argument("--bpm-range", type=float, nargs=2, default=[70, 180])
    ap.add_argument("--weights", default="")
    ap.add_argument("--bpm", type=float); ap.add_argument("--offset", type=float, default=0.0)
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    dur, fps = probe(a.video)
    cuts = detect(a.video, a.thresh)
    run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", "fps=4,scale=320:-1,tile=8x%d" % (int(dur * 4) // 8 + 1),
         "-frames:v", "1", str(out / "sheet.jpg")])
    times = [c["t"] for c in cuts]
    wmap = {float(k): float(v) for k, v in (p.split("=") for p in a.weights.split(",") if p)}
    weights = [next((w for k, w in wmap.items() if abs(k - t) < 0.06), 1.0) for t in times]
    print("duration %.3f s, %.2f fps, %d cuts" % (dur, fps, len(cuts)))
    for c, w in zip(cuts, weights):
        print("  %6.3f s  score %.2f  weight %.1f" % (c["t"], c["score"], w))
    if a.bpm:
        bpm, off = a.bpm, a.offset
    else:
        cands = fit(times, weights, *a.bpm_range)
        print("tempo candidates (error, bpm, offset s, cuts in beats):")
        for e, bpm_, off_ in cands:
            print("  %.4f  %6.1f  %.2f  %s" % (e, bpm_, off_, [round((t - off_) / (60 / bpm_), 2) for t in times]))
        _, bpm, off = cands[0]
    rows = beat_map(times, bpm, off)
    print("beat map at %.2f BPM, offset %.2f s:" % (bpm, off))
    for r in rows:
        print("  %6.3f s -> beat %7.3f (bar.beat %s)  miss %+d ms" % (r["t"], r["beat"], r["bar_beat"], r["miss_ms"]))
    json.dump({"video": a.video, "duration": dur, "fps": fps, "cuts": cuts,
               "tempo": {"bpm": bpm, "offset": off, "beat_s": 60.0 / bpm}, "map": rows},
              open(out / "cuts.json", "w"), indent=1)


if __name__ == "__main__":
    main()
