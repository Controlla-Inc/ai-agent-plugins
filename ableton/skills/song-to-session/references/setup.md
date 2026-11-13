# One-time setup

Walk the user through this once; afterwards `bash connector/install.sh --check` should show
everything present.

## What's needed

| Piece | Why |
|---|---|
| Ableton Live 12.0.5 or newer (Standard is enough; Intro lacks track count) | `create_audio_clip` needs 12.0.5 |
| Controlla Voice account + its Claude connector | song generation, stems, drum kit clone |
| Claude in Chrome, signed in to voice.controlla.xyz | Song to MIDI has no connector tool yet |
| `uv` (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) and `git` | install script |

Logic Pro can't be used: it has no API that lets Claude create tracks, write MIDI or load
plugins. Ableton has a Python Remote Script API, which the AbletonMCP connector uses.

## Install

If this skill came from the **ableton plugin** (`ableton@controlla`), run `/ableton:setup` — it does all of
the below and the plugin already registers both connectors. Otherwise, from this skill's folder:

```bash
bash connector/install.sh
```

It:
1. clones the community connector `ahujasid/ableton-mcp` (MIT) to `~/.local/share/ableton-mcp`,
   pinned to the reviewed commit `9dddc7b`, and applies `ableton-mcp-local-patches.diff`;
2. copies the patched Remote Script into `<User Library>/Remote Scripts/AbletonMCP/`;
3. creates the analysis venv at `~/.local/share/ai-song-to-ableton/venv` (librosa, pretty_midi, soundfile).

Then (standalone skill only — the plugin does this for you) register the MCP server with telemetry **and** dataset uploads switched off (upstream
can otherwise send usage data and session snapshots to the author's backend):

```bash
claude mcp add ableton --scope user \
  -e DISABLE_TELEMETRY=true -e ABLETON_MCP_DISABLE_TELEMETRY=true -e ABLETON_MCP_DISABLE_DATASET=true \
  -- ~/.local/share/ableton-mcp/.venv/bin/ableton-mcp
```

## In Live

1. Quit Live completely and reopen it (Remote Script code is only read at startup).
2. Settings → Tempo & MIDI (older Live: "Link, Tempo & MIDI") → Control Surface: **AbletonMCP**, Input/Output: None.
3. Settings → Plug-Ins: turn on "Use VST3 Plug-In System Folders" (and AU on macOS) and
   rescan, so the user's plugins show in the browser and can be loaded by URI.
4. Check: `~/.local/share/ai-song-to-ableton/venv/bin/python scripts/live.py tracks` lists tracks.

## What the patch adds to the connector

| Command | Why |
|---|---|
| `create_audio_clip(..., warping=False)` | auto-warp stretches long stems to a guessed tempo |
| `set_clip_warping` | Live can re-enable warping after analysis; force it off before copying to the arrangement |
| `delete_arrangement_clip` | replace a part without leaving old clips under it |
| `set_mixer` (volume / pan / sends, `-1` = master, `return_index`) | mixing; returns dB strings |
| `get_meters` | level matching against reference stems |
| `delete_device` (with `expect_name` guard) | remove a misplaced device safely |
| `load_browser_item` on track `-1` | master-bus plugins |
| hot-swap guard in `load_browser_item` | a pending hot-swap once replaced a Drum Rack on another track; now it exits hot-swap mode and raises if a load lands on the wrong track |

## Finding browser URIs

`get_browser_tree` / `get_browser_items_at_path` (MCP tools) list items with their URIs:
plugins look like `query:Plugins#VST3:<Vendor>:<Name>`, Live devices like
`query:AudioFx#EQ%20Eight`, presets like `query:AudioFx#Compressor:FileId_8183`, User
Library presets like `query:UserLibrary#Presets:Instruments:Drum%20Rack:<file>.adg`.
FileId numbers can differ between Live versions — look them up rather than reusing.
