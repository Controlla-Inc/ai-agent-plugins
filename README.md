# Controlla plugins for Claude Code

Make music with Claude. These plugins connect [Claude Code](https://claude.com/claude-code) to
[Controlla Voice](https://voice.controlla.xyz/mcp) and your DAW.

## Install

In Claude Code:

```
/plugin marketplace add Controlla-Inc/claude-plugins
/plugin install ai-song-to-ableton@controlla
/setup-ableton
```

## ai-song-to-ableton

Ask Claude for a song (or give it one) and it builds a ~70%-finished, editable **Ableton Live**
session: generates the song with Controlla, splits stems, transcribes the parts to MIDI on your
own instruments, clones the drum kit into a Drum Rack, lines everything up on the grid, puts the
original stems underneath as muted references, and does a first mix. Using Logic Pro instead? It exports the same draft as a MIDI file, aligned
stems, the drum kit and a README.

> *"Make me a trap soul song with dreamy vocals, use my AI voice, and build it in Ableton."*

**You need**

- Ableton Live 12.0.5 or newer (Standard or Suite), macOS or Windows
- A paid [Controlla Voice](https://voice.controlla.xyz) plan — the Controlla connector signs in on first use and uses your credits
- Optional: [Claude in Chrome](https://claude.com/chrome), signed in to voice.controlla.xyz — only a fallback if the connector's Song to MIDI step misbehaves
- `git` and [`uv`](https://docs.astral.sh/uv/) (`/setup-ableton` helps install `uv`)

**What gets installed**

- The plugin registers two connectors: **Controlla** (`https://api.controlla.xyz/mcp`) and **AbletonMCP**.
- `/setup-ableton` downloads the community [AbletonMCP](https://github.com/ahujasid/ableton-mcp)
  connector (MIT) pinned to a reviewed commit with a small patch (mixer, meters, safer device
  loading), copies its Remote Script into your Ableton User Library, and creates a Python
  environment for the analysis scripts. AbletonMCP's telemetry and dataset uploads are switched off.

After setup, restart Claude Code, quit and reopen Live, and pick **AbletonMCP** under
Settings → Link, Tempo & MIDI → Control Surface.
