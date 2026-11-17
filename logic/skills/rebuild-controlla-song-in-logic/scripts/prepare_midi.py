#!/usr/bin/env python3
"""Non-destructive MIDI preparation. Requires mido; outputs require audition."""
import argparse
import bisect
import collections
import json
from pathlib import Path
import mido


def absolute(track):
    tick = 0
    for msg in track:
        tick += msg.time
        yield tick, msg


def track_from(events):
    tr, last = mido.MidiTrack(), 0
    for tick, msg in sorted(events, key=lambda x: (x[0], x[1].type == 'note_on')):
        tick = int(tick)
        tr.append(msg.copy(time=tick-last))
        last = tick
    return tr


def retime(src, bpm):
    tempos = [(0, 500000)]
    for tick, msg in absolute(mido.merge_tracks(src.tracks)):
        if msg.type == 'set_tempo':
            tempos.append((tick, msg.tempo))
    starts, seconds, values = [], [], []
    last, elapsed, tempo = 0, 0.0, 500000
    for tick, value in tempos:
        elapsed += mido.tick2second(tick-last, src.ticks_per_beat, tempo)
        starts.append(tick); seconds.append(elapsed); values.append(value)
        last, tempo = tick, value
    out = mido.MidiFile(ticks_per_beat=src.ticks_per_beat)
    out.tracks.append(mido.MidiTrack([mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm))]))
    for tr in src.tracks:
        ev = []
        for tick, msg in absolute(tr):
            if msg.type == 'set_tempo':
                continue
            i = bisect.bisect_right(starts, tick)-1
            sec = seconds[i]+mido.tick2second(tick-starts[i], src.ticks_per_beat, values[i])
            ev.append((round(sec*bpm*src.ticks_per_beat/60), msg))
        out.tracks.append(track_from(ev))
    return out


def notes(track):
    active, result = collections.defaultdict(collections.deque), []
    for tick, msg in absolute(track):
        if msg.type == 'note_on' and msg.velocity:
            active[(msg.channel, msg.note)].append((tick, msg.velocity))
        elif msg.type in ('note_on', 'note_off'):
            q = active[(msg.channel, msg.note)]
            if q:
                start, velocity = q.popleft()
                if tick > start:
                    result.append((start, tick, msg.note, velocity, msg.channel))
    if any(active.values()):
        raise ValueError('Unclosed notes: repair the source before simplification')
    return result


def simplify(src, index, maximum):
    if any(m.type == 'time_signature' and (m.numerator, m.denominator) != (4, 4)
           for tr in src.tracks for m in tr):
        raise ValueError('Simplification requires constant 4/4')
    ns = notes(src.tracks[index])
    if not ns:
        raise ValueError('Selected track contains no notes')
    if any(ch == 9 for *_, ch in ns):
        raise ValueError('Select a harmonic track, not percussion')
    width, ev = src.ticks_per_beat*4, []
    ev.append((0, mido.MetaMessage('track_name', name='Simple held notes - audition required')))
    # Carry the source tempo map and meter into a separate conductor track.
    conductor = [(t, m) for t, m in absolute(mido.merge_tracks(src.tracks))
                 if m.type in ('set_tempo', 'time_signature', 'key_signature')]
    for bar in range((max(n[1] for n in ns)+width-1)//width):
        start, end = bar*width, (bar+1)*width
        local = [n for n in ns if n[0] < end and n[1] > start]
        if not local:
            continue
        weights = collections.Counter()
        for a, b, pitch, vel, _ in local:
            weights[pitch % 12] += (min(b, end)-max(a, start))*vel
        chosen = [pc for pc, weight in weights.most_common(maximum)
                  if weight >= max(weights.values())*.48]
        onset = max(start, min(n[0] for n in local))
        stop = min(end, max(n[1] for n in local))-max(1, width//40)
        for pc in chosen:
            candidates = [n for n in local if n[2] % 12 == pc]
            best = max(candidates, key=lambda n: (min(n[1], end)-max(n[0], start))*n[3])
            pitch = best[2]
            while pitch < 52: pitch += 12
            while pitch > 76: pitch -= 12
            if stop <= onset:
                continue
            ev.extend([(onset, mido.Message('note_on', note=pitch, velocity=best[3], channel=best[4])),
                       (stop, mido.Message('note_off', note=pitch, channel=best[4]))])
    out = mido.MidiFile(ticks_per_beat=src.ticks_per_beat)
    out.tracks.extend([track_from(conductor), track_from(ev)])
    return out


def drums(src, mapping):
    if any(m.type == 'note_on' and m.velocity and m.channel != 9
           for tr in src.tracks for m in tr):
        raise ValueError('Supply isolated channel-10 drum MIDI; melodic/non-drum notes detected')
    observed = {m.note for tr in src.tracks for m in tr if m.type == 'note_on' and m.velocity}
    missing = observed-mapping.keys()
    if missing:
        raise ValueError(f'Unmapped source notes: {sorted(missing)}')
    if not observed:
        raise ValueError('No drum notes found')
    if any(not 0 <= n <= 127 for pair in mapping.items() for n in pair):
        raise ValueError('MIDI notes must be 0..127')
    out = mido.MidiFile(ticks_per_beat=src.ticks_per_beat)
    for tr in src.tracks:
        ev = []
        for tick, msg in absolute(tr):
            if msg.type == 'program_change':
                continue
            if msg.type in ('note_on', 'note_off'):
                if msg.note not in mapping:
                    raise ValueError(f'Unmapped note-off: {msg.note}')
                msg = msg.copy(note=mapping[msg.note], channel=9)
            ev.append((tick, msg))
        out.tracks.append(track_from(ev))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['retime', 'simplify', 'drums'])
    p.add_argument('source', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--bpm', type=float); p.add_argument('--track', type=int, default=0)
    p.add_argument('--max-notes', type=int, default=3); p.add_argument('--map', type=Path)
    a = p.parse_args()
    if a.output.exists(): p.error('Output already exists; choose a new path')
    src = mido.MidiFile(a.source)
    if src.type == 2 or src.ticks_per_beat <= 0: p.error('Require synchronous PPQ MIDI')
    if a.mode == 'retime':
        if a.bpm is None or not 20 <= a.bpm <= 400: p.error('Supply --bpm 20..400')
        out = retime(src, a.bpm)
    elif a.mode == 'simplify':
        if not 0 <= a.track < len(src.tracks) or not 1 <= a.max_notes <= 6:
            p.error('Invalid track index or maximum note count')
        out = simplify(src, a.track, a.max_notes)
    else:
        if a.map is None: p.error('Supply an explicit --map JSON file')
        out = drums(src, {int(k): int(v) for k, v in json.loads(a.map.read_text()).items()})
    out.save(a.output)
    print(json.dumps({'output': str(a.output), 'tracks': len(out.tracks),
                      'note_ons': sum(m.type == 'note_on' and m.velocity > 0 for tr in out.tracks for m in tr)}))


if __name__ == '__main__':
    main()
