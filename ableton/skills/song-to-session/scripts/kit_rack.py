"""Turn a Controlla Drum Kit Clone folder into a Live Drum Rack preset.

Usage: kit_rack.py <kit_dir> "<Song Title>" [--prefix ABC]

Copies the one-shots into <User Library>/Samples/Controlla Kits/<Song Title>/ and writes
<User Library>/Presets/Instruments/Drum Rack/CV Drums – <Song Title>.adg with the top-
ranked kick/snare/hat on the General MIDI notes drums_midi.py writes (36/38/42) and the
alternates on the free pads around them. Load it with the browser URI it prints.

The connector cannot drop samples onto pads, so the rack is written as a file: each pad
is a clone of the C1 pad of Live's Core Library "Boom Bap Kit" (plain Simpler) pointed at
our sample (see make_rack.py for the details that make Live accept it).
"""
import glob
import os
import shutil
import subprocess
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = "Contents/App-Resources/Core Library/Racks/Drum Racks/Sampled/Boom Bap Kit.adg"
# GM core first, alternates on the remaining pads
SLOTS = {"kick": [36, 41, 43, 45, 47], "snare": [38, 37, 39, 40, 50], "hihat": [42, 44, 48, 51, 52, 53],
         "open_cymbal": [46, 49, 55, 57]}  # 46 open hat (drums_midi "openhat"), 49 crash


def user_library():
    for c in ("~/Music/Ableton/User Library", "~/Documents/Ableton/User Library"):
        p = os.path.expanduser(c)
        if os.path.isdir(p):
            return p
    sys.exit("No Ableton User Library found")


def template():
    found = sorted(glob.glob(f"/Applications/Ableton Live 12*.app/{CORE}"))
    if not found:
        sys.exit("Boom Bap Kit.adg not found in /Applications/Ableton Live 12*.app – install the Core Library")
    return found[-1]


def main():
    kit, title = sys.argv[1], sys.argv[2]
    prefix = sys.argv[sys.argv.index("--prefix") + 1] if "--prefix" in sys.argv else "".join(w[0] for w in title.split()).upper()
    lib = user_library()
    sdir = os.path.join(lib, "Samples", "Controlla Kits", title)
    rdir = os.path.join(lib, "Presets", "Instruments", "Drum Rack")
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(rdir, exist_ok=True)
    args, used = [], set()
    for kind, notes in SLOTS.items():
        files = sorted(glob.glob(os.path.join(kit, f"{kind}_*.wav")))  # ranked best-first by Controlla
        for note, f in zip(notes, files):
            if note in used:
                continue
            dst = os.path.join(sdir, f"{prefix} {os.path.basename(f)}")
            shutil.copy2(f, dst)
            args.append(f"{note}={dst}")
            used.add(note)
    out = os.path.join(rdir, f"CV Drums – {title}.adg")
    subprocess.run([sys.executable, os.path.join(HERE, "make_rack.py"), template(), out, *args], check=True)
    print("pads:", ", ".join(a.split("=")[0] + "=" + os.path.basename(a.split("=", 1)[1]) for a in args))
    print("browser URI:", "query:UserLibrary#Presets:Instruments:Drum%20Rack:" + quote(f"CV Drums – {title}.adg"))


if __name__ == "__main__":
    main()
