#!/usr/bin/env python3
"""Convert to PCM and end-pad. Does not detect or correct source offsets."""
import argparse
import json
from pathlib import Path
import subprocess
import wave


def convert(source, dest, rate):
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(source),
                    '-ar', str(rate), '-ac', '2', '-c:a', 'pcm_s24le', str(dest)], check=True)
    with wave.open(str(dest), 'rb') as w:
        return w.getparams(), w.readframes(w.getnframes())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--sample-rate', type=int, default=44100)
    p.add_argument('--reference', type=Path)
    a = p.parse_args()
    if a.output_dir.exists(): p.error('Output directory must not exist')
    sources = sorted(x for x in a.input_dir.iterdir()
                     if x.suffix.lower() in ('.wav', '.mp3', '.flac', '.aiff', '.aif', '.m4a', '.ogg'))
    if not sources: p.error('No supported audio files found')
    if len({x.stem.casefold() for x in sources}) != len(sources): p.error('Duplicate output names')
    if not 8000 <= a.sample_rate <= 192000: p.error('Invalid sample rate')
    a.output_dir.mkdir(parents=True)
    rows, target = [], 0
    for source in sources:
        dest = a.output_dir/(source.stem+'.wav')
        params, data = convert(source, dest, a.sample_rate)
        rows.append((source, dest, params, data)); target = max(target, params.nframes)
    if a.reference:
        ref = a.output_dir/'_reference_temporary.wav'
        if ref.exists(): raise ValueError('Reserved temporary reference filename collision')
        params, _ = convert(a.reference, ref, a.sample_rate)
        target = max(target, params.nframes); ref.unlink()
    audit = []
    for source, dest, params, data in rows:
        padding = target-params.nframes
        with wave.open(str(dest), 'wb') as w:
            w.setparams(params)
            w.writeframes(data+b'\0'*(padding*params.nchannels*params.sampwidth))
        with wave.open(str(dest), 'rb') as w:
            assert w.getnframes() == target
        audit.append({'source': str(source), 'output': str(dest),
                      'source_frames_after_conversion': params.nframes, 'end_padding_frames': padding})
    manifest = {'sample_rate': a.sample_rate, 'channels': 2, 'bit_depth': 24,
                'frames': target, 'duration_seconds': target/a.sample_rate,
                'leading_silence_preserved': True, 'synchronization_verified': False, 'stems': audit}
    (a.output_dir/'alignment-audit.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'stems': len(rows), 'frames': target, 'synchronization_verified': False}))


if __name__ == '__main__':
    main()
