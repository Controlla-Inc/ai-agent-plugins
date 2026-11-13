"""Build a Drum Rack preset (.adg) from one-shot WAVs, using a Core Library kit as the template.

Usage: make_rack.py <template.adg> <out.adg> <note>=<wav> [<note>=<wav> ...]

Every pad is cloned from the template's C1 pad (plain Simpler, no transpose, no
filter, no pad FX), then pointed at the given file with its real length.
"""
import gzip
import os
import re
import sys

import soundfile as sf


def fileref(path, id_attr=""):
    return (f'<FileRef{id_attr}>\n<RelativePathType Value="0" />\n<RelativePath Value="" />\n'
            f'<Path Value="{path}" />\n<Type Value="2" />\n<LivePackName Value="" />\n'
            f'<LivePackId Value="" />\n<OriginalFileSize Value="{os.path.getsize(path)}" />\n'
            f'<OriginalCrc Value="0" />\n<SourceHint Value="" />\n</FileRef>')


def pad(template, idx, note, path):
    info = sf.info(path)
    frames, sr = info.frames, info.samplerate
    name = os.path.splitext(os.path.basename(path))[0]
    p = template
    p = re.sub(r'^<DrumBranchPreset Id="\d+">', f'<DrumBranchPreset Id="{idx}">', p)
    p = re.sub(r'(<DrumBranchPreset Id="\d+">\s*<Name Value=")[^"]*"', rf'\g<1>{name}"', p, count=1)
    p = re.sub(r'<ReceivingNote Value="\d+"', f'<ReceivingNote Value="{128 - note}"', p)
    p = re.sub(r'(<MultiSamplePart [^>]*>\s*<LomId Value="0" />\s*<Name Value=")[^"]*"', rf'\g<1>{name}"', p)
    p = re.sub(r'<SampleEnd Value="\d+"', f'<SampleEnd Value="{frames - 1}"', p)
    p = re.sub(r'(<(?:SustainLoop|ReleaseLoop)>\s*<Start Value="0" />\s*<End Value=")\d+"', rf'\g<1>{frames - 1}"', p)
    # only the sample references (SampleRef + its OriginalFileRef); leave device PresetRefs alone
    p = re.sub(r'<SampleRef>.*?</SampleRef>',
               lambda m: re.sub(r'<FileRef( Id="\d+")?>.*?</FileRef>', lambda f: fileref(path, f.group(1) or ""), m.group(0), flags=re.S),
               p, flags=re.S)
    p = re.sub(r'<BrowserContentPath Value="[^"]*"', '<BrowserContentPath Value=""', p)
    p = re.sub(r'<DefaultDuration Value="\d+"', f'<DefaultDuration Value="{frames}"', p)
    p = re.sub(r'<DefaultSampleRate Value="\d+"', f'<DefaultSampleRate Value="{sr}"', p)
    # stale analysis from the template sample
    p = re.sub(r'<SlicePoints>.*?</SlicePoints>', '<SlicePoints />', p, flags=re.S)
    p = re.sub(r'<WarpMarkers>.*?</WarpMarkers>', '<WarpMarkers />', p, flags=re.S)
    return p


def main():
    src, dst = sys.argv[1], sys.argv[2]
    pads = sorted((int(a.split("=", 1)[0]), a.split("=", 1)[1]) for a in sys.argv[3:])
    x = gzip.open(src).read().decode()
    branches = list(re.finditer(r'<DrumBranchPreset Id="\d+">.*?</DrumBranchPreset>', x, re.S))
    template = next(b.group(0) for b in branches
                    if re.search(r'<ReceivingNote Value="92"', b.group(0)))  # C1
    new = "\n".join(pad(template, i, n, p) for i, (n, p) in enumerate(pads))
    out = x[:branches[0].start()] + new + x[branches[-1].end():]
    with gzip.open(dst, "wb") as f:
        f.write(out.encode())
    print(f"wrote {dst}: {len(pads)} pads")


if __name__ == "__main__":
    main()
