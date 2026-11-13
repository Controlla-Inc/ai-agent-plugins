# Controlla plugins for AI agents

Make music with your AI agent. These plugins connect agents like Claude Code, Codex, Cursor and
GitHub Copilot to [Controlla Voice](https://voice.controlla.xyz/mcp) and your DAW.

Each plugin folder is packaged two ways:

- **Claude Code plugin**: `.claude-plugin/plugin.json`, `.mcp.json` and `commands/`
- **[Agent Plugins 1.0](https://agent-plugins.org/specification)** (the open format other agents
  read): `plugin.json`, `mcp.json` and `skills/`

The skills follow the open [Agent Skills](https://agentskills.io) format, so both packages share
the same skill.

## ableton

Ask your agent for a song (or give it one) and it builds a ~70%-finished, editable **Ableton Live**
session. It generates the song with Controlla, splits stems, transcribes the parts to MIDI on your
own instruments, clones the drum kit into a Drum Rack, lines everything up on the grid, puts the
original stems underneath as muted references, and does a first mix. Using Logic Pro instead? It
exports the same draft as a MIDI file, aligned stems, the drum kit and a README.

> *"Make me a trap soul song with dreamy vocals, use my AI voice, and build it in Ableton."*

### Install in Claude Code

Run this in Claude Code (version 2.1.275 or later):

```
/plugin install ableton --marketplace Controlla-Inc/ai-agent-plugins
```

On an older Claude Code, run these two commands **one at a time**:

```
/plugin marketplace add Controlla-Inc/ai-agent-plugins
```

```
/plugin install ableton@controlla
```

Then run the one-time setup:

```
/ableton:setup
```

### Install in other agents

Add the `ableton/` folder as an Agent Plugins plugin, the way your agent installs them. Then ask the
agent to run the one-time setup, which is the same script `/ableton:setup` runs:

```bash
bash ableton/skills/song-to-session/connector/install.sh
bash ableton/skills/song-to-session/connector/install.sh --check
```

### You need

- Ableton Live 12.0.5 or newer (Standard or Suite), on macOS or Windows
- A paid [Controlla Voice](https://voice.controlla.xyz) plan. The Controlla connector signs in on
  first use and spends your credits.
- `git` and [`uv`](https://docs.astral.sh/uv/). In Claude Code, `/ableton:setup` helps install `uv`.
- Optional: [Claude in Chrome](https://claude.com/chrome), signed in to voice.controlla.xyz. It's
  only a fallback if the connector's Song to MIDI step misbehaves.

### What gets installed

- The plugin registers two connectors: **Controlla** (`https://api.controlla.xyz/mcp`) and
  **AbletonMCP**.
- Setup downloads the community [AbletonMCP](https://github.com/ahujasid/ableton-mcp) connector
  (MIT), pinned to a reviewed commit with a small patch (mixer, meters, safer device loading). It
  copies the Remote Script into your Ableton User Library and creates a Python environment for the
  analysis scripts. AbletonMCP's telemetry and dataset uploads are switched off.

After setup, restart your agent, quit and reopen Live, and pick **AbletonMCP** under
Settings → Tempo & MIDI → Control Surface (on older Live versions the page is called "Link, Tempo & MIDI").

### Upgrading from `ai-song-to-ableton`

This plugin used to be called `ai-song-to-ableton`, with the setup command `/setup-ableton`. To
switch in Claude Code, run these one at a time:

```
/plugin uninstall ai-song-to-ableton@controlla
```

```
/plugin marketplace update controlla
```

```
/plugin install ableton@controlla
```

You don't need to run setup again: the connector and the analysis
environment stay where they are.
