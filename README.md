# sage-tui

Interactive terminal user interface for the Sage AI agent framework.

## Features

- Split-screen layout with chat, status, and log panels
- Streaming and batch response modes with animated thinking indicator
- Collapsible tool call display with color-coded status (running, success, error)
- Markdown rendering for agent responses
- Permission modal for tool approval
- Parallel subagent orchestration
- Context window usage bar with color gradient
- Token breakdown and session cost tracking
- Auto-generated session titles via LLM
- Input history navigation
- Smart auto-scroll that respects manual scroll position
- Log forwarding to TUI panel

## Installation

```bash
uv add sage-tui
```

Or with pip:

```bash
pip install sage-tui
```

Requires Python 3.10 or later.

## Quick Start

```bash
# Point directly at an agent definition
sage-tui -c /path/to/AGENTS.md

# Or use a config.toml
sage-tui --config /path/to/config.toml

# Or set the env var and just run
export SAGE_CONFIG_PATH=/path/to/config.toml
sage-tui
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--agent-config`, `-c PATH` | Path to AGENTS.md or directory containing one. Inferred from config.toml if omitted. |
| `--config PATH` | Path to main config.toml. Also reads the `SAGE_CONFIG_PATH` env var. |
| `--verbose`, `-v` | Enable debug logging. |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Submit message |
| Shift+Enter / Ctrl+J | Insert newline |
| Up / Down | Navigate input history (single-line mode) |
| Ctrl+B | Toggle status panel |
| Ctrl+L | Toggle log panel |
| Ctrl+N | New session (clear chat, reset agent) |
| Ctrl+S | Toggle streaming / batch mode |
| Ctrl+O | Orchestrate subagents (if available) |
| Ctrl+Q | Quit |
| Y / N | Approve or deny in permission modal |

## Layout

The TUI is divided into four areas:

- **Chat panel** (left, flexible width) -- Conversation history with inline collapsible tool calls and a message input box at the bottom.
- **Status panel** (right, 40 columns, hidden by default) -- Session info, context window usage bar, token breakdown, agent info, skills, and active agents. Toggle with Ctrl+B.
- **Log panel** (bottom, hidden by default) -- Scrollable log viewer for the `sage.*` logging namespace. Toggle with Ctrl+L.
- **Status bar** (bottom, 1 line) -- Agent state, model name, stream mode indicator, token usage, cost, and keyboard hints.

## Configuration

There are three ways to configure which agent the TUI loads:

**1. Direct agent path**

```bash
sage-tui -c /path/to/AGENTS.md
```

Point at an AGENTS.md file or a directory that contains one.

**2. Via config.toml**

```bash
sage-tui --config /path/to/config.toml
```

The TUI reads the `agents_dir` and `primary` fields from config.toml to resolve the primary agent definition.

**3. Auto-discovery**

```bash
export SAGE_CONFIG_PATH=/path/to/config.toml
sage-tui
```

When no flags are given, the TUI reads the `SAGE_CONFIG_PATH` environment variable, locates config.toml, and resolves the primary agent from there.

A `.env` file in the working directory is loaded automatically via python-dotenv.

## Streaming vs Batch

The TUI supports two response modes, toggled at runtime with Ctrl+S. In **streaming** mode, tokens appear incrementally as the model generates them, with an animated thinking indicator while waiting. In **batch** mode, the full response is displayed only after generation completes. Streaming is the default.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
