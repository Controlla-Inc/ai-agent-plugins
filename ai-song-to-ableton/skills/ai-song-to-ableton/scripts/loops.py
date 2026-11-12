"""Fold the raw chord chart into ONE repeating loop per section.

Usage: loops.py <plan.json> <chart.json>

For every section in plan.json without a "loop", tries 1-, 2- and 4-bar loops (half-bar
slots), majority-votes each slot across the section's repeats, and keeps the shortest
loop that agrees nearly as well as a longer one. 7ths are folded into triads for the
vote – the voicing step adds the real colour back from the stems. Writes the loops into
plan.json and prints each with its agreement. Under ~70% agreement, listen/look again:
the section boundary may be wrong, or it genuinely doesn't loop (write it by hand).
"""
import json
import sys
from collections import Counter

from common import parse_chord, NAMES


def simple(ch):
    if not ch:
        return None
    r, q = parse_chord(ch)
    return NAMES[r] + ("m" if q.startswith("m") and not q.startswith("maj") else "")


def main():
    plan_path, chart = sys.argv[1], json.load(open(sys.argv[2]))
    plan = json.load(open(plan_path))
    slot = {}
    for s, d, ch in chart:
        t = s
        while t < s + d:
            slot[int(t // 2)] = simple(ch)
            t += 2
    for sec in plan["sections"]:
        if sec.get("loop"):
            continue
        a, b = sec["bars"]
        seq = [slot.get(i) for i in range((a - 1) * 2, b * 2)]
        best = None
        for L in (2, 4, 8):
            if L > len(seq):
                continue
            votes = [Counter(seq[j] for j in range(k, len(seq), L) if seq[j]) for k in range(L)]
            loop = [v.most_common(1)[0][0] if v else None for v in votes]
            known = [j for j in range(len(seq)) if seq[j]]
            agree = sum(seq[j] == loop[j % L] for j in known) / max(len(known), 1)
            if best is None or agree > best[0] + 0.08:
                best = (agree, loop)
        agree, loop = best
        merged = []
        for ch in loop:
            ch = ch or (merged[-1][0] if merged else None)
            if merged and merged[-1][0] == ch:
                merged[-1][1] += 2
            else:
                merged.append([ch, 2])
        sec["loop"] = merged
        print(f"{sec['name']:<12} bars {a:>3}-{b:<3} {agree:4.0%}  " + " | ".join(f"{c} {d}" for c, d in merged))
        if agree < 0.7:
            # long progressions (8-bar verses with a turnaround) don't fold into a short loop:
            # show the raw half-bar chart so the loop can be written by hand into plan.json
            for r in range(a, b + 1, 4):
                print("      " + " | ".join(f"{bar:>3}: {seq[(bar - a) * 2] or '-':<5} {seq[(bar - a) * 2 + 1] or '-':<5}"
                                          for bar in range(r, min(r + 4, b + 1))))
    json.dump(plan, open(plan_path, "w"), indent=1)


if __name__ == "__main__":
    main()
