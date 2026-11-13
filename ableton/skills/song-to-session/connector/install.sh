#!/usr/bin/env bash
# Install the AbletonMCP connector with this skill's local patches, plus the
# Python analysis environment the skill's scripts use. Safe to re-run.
#
#   bash install.sh            # install / update everything
#   bash install.sh --check    # only report what is installed
#
# Needs: git, uv (https://docs.astral.sh/uv/), Ableton Live 12.0.5+ (macOS or Windows+Git Bash).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="$(dirname "$HERE")"
REPO_URL="https://github.com/ahujasid/ableton-mcp.git"
PIN="9dddc7bd5b95412510fdeb745949e3bf23f3fd8a"   # the commit the patch was written and reviewed against
DEST="${ABLETON_MCP_HOME:-$HOME/.local/share/ableton-mcp}"
VENV="${AI_SONG_VENV:-$HOME/.local/share/ai-song-to-ableton/venv}"

find_user_library() {
  for c in "$HOME/Music/Ableton/User Library" "$HOME/Documents/Ableton/User Library"; do
    [ -d "$c" ] && { echo "$c"; return; }
  done
  echo ""
}

LIB="$(find_user_library)"

if [ "${1:-}" = "--check" ]; then
  echo "connector repo : $([ -d "$DEST/.git" ] && git -C "$DEST" rev-parse --short HEAD || echo missing)"
  echo "patched        : $([ -d "$DEST" ] && grep -q '_set_mixer' "$DEST/AbletonMCP_Remote_Script/__init__.py" 2>/dev/null && echo yes || echo no)"
  echo "remote script  : $([ -n "$LIB" ] && grep -q '_set_mixer' "$LIB/Remote Scripts/AbletonMCP/__init__.py" 2>/dev/null && echo "installed in $LIB" || echo missing)"
  echo "analysis venv  : $([ -x "$VENV/bin/python" ] && echo "$VENV" || echo missing)"
  exit 0
fi

command -v uv >/dev/null || { echo "uv is required: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }

# 1. connector source at the pinned commit + patch
if [ ! -d "$DEST/.git" ]; then
  git clone --quiet "$REPO_URL" "$DEST"
fi
git -C "$DEST" fetch --quiet origin
if ! grep -q '_set_mixer' "$DEST/AbletonMCP_Remote_Script/__init__.py" 2>/dev/null; then
  git -C "$DEST" checkout --quiet "$PIN"
  git -C "$DEST" apply "$HERE/ableton-mcp-local-patches.diff"
  echo "patched AbletonMCP at ${PIN:0:7}"
else
  echo "AbletonMCP already patched"
fi
(cd "$DEST" && uv sync --quiet)

# 2. Remote Script into Live's User Library
if [ -z "$LIB" ]; then
  echo "!! No Ableton User Library found. Open Live once, then re-run."; exit 1
fi
mkdir -p "$LIB/Remote Scripts/AbletonMCP"
cp "$DEST/AbletonMCP_Remote_Script/__init__.py" "$LIB/Remote Scripts/AbletonMCP/__init__.py"
rm -rf "$LIB/Remote Scripts/AbletonMCP/__pycache__"
echo "Remote Script -> $LIB/Remote Scripts/AbletonMCP"

# 3. analysis environment for the skill's scripts
if [ ! -x "$VENV/bin/python" ]; then
  uv venv --quiet --python 3.12 "$VENV"
fi
uv pip install --quiet --python "$VENV/bin/python" -r "$SKILL/scripts/requirements.txt"
echo "analysis venv -> $VENV"

cat <<EOF

Next:
  1. Installed via the ableton plugin (ableton@controlla)? The connector is already registered —
     just restart Claude Code. Otherwise register it (telemetry + dataset uploads off):
       claude mcp add ableton --scope user \\
         -e DISABLE_TELEMETRY=true -e ABLETON_MCP_DISABLE_TELEMETRY=true -e ABLETON_MCP_DISABLE_DATASET=true \\
         -- "$DEST/.venv/bin/ableton-mcp"
  2. QUIT Live completely and reopen it (Live only loads Remote Script code at startup).
  3. Live > Settings > Link, Tempo & MIDI > Control Surface: pick "AbletonMCP" (Input/Output: None).
EOF
