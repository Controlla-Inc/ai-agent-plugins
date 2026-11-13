---
description: One-time setup for the ableton plugin — installs the patched AbletonMCP connector, the Live Remote Script and the analysis environment, then walks you through the Live settings.
allowed-tools: Bash
---

Set up the ableton plugin (song-to-session) on this computer. Follow these steps in order and tell the user plainly what each one did.

1. Check prerequisites: `git --version` and `uv --version`. If `uv` is missing, show the user the install command `curl -LsSf https://astral.sh/uv/install.sh | sh`, ask before running it, then continue.
2. Run the installer that ships with this plugin:
   `bash "${CLAUDE_PLUGIN_ROOT}/skills/song-to-session/connector/install.sh"`
   If it says no Ableton User Library was found, ask the user to open Ableton Live once and re-run.
3. Run `bash "${CLAUDE_PLUGIN_ROOT}/skills/song-to-session/connector/install.sh" --check` and show the result.
4. The plugin already registers both connectors (`controlla` and `ableton`), so do NOT run `claude mcp add`. Tell the user to restart Claude Code after setup so the `ableton` connector starts now that it exists.
5. Tell the user the steps only they can do in Ableton Live:
   - Quit Live completely and reopen it (Live only loads Remote Scripts at startup).
   - Settings → Tempo & MIDI (older Live: "Link, Tempo & MIDI") → Control Surface: choose **AbletonMCP** (Input/Output: None).
   - Settings → Plug-Ins: turn on "Use VST3 Plug-In System Folders" (and Audio Units on macOS), then rescan.
6. Remind them of the other two requirements:
   - The **Controlla** connector signs in the first time it's used (a paid Controlla Voice plan; it uses their credits).
   - Song to MIDI runs through the Controlla connector; **Claude in Chrome** (signed in to voice.controlla.xyz) is only a fallback.

Finish with: "Setup done. Try: *make me a trap soul song with dreamy vocals and build it in Ableton*."
