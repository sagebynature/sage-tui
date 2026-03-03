# sage-tui Architecture

sage-tui is a Textual-based TUI for the Sage AI agent framework. It was recently refactored from a single 1,424-line `app.py` into focused modules.

## Module Dependency Graph

```
app.py (SageTUIApp)
  ├── messages.py        (custom Textual Message subclasses)
  ├── widgets.py         (all UI widget classes)
  │     ├── helpers.py   (format_tokens, fmt_args)
  │     └── instrumentation.py (_LOG_COLORS, _LOG_FMT)
  ├── modals.py          (PermissionScreen, OrchestrationScreen)
  ├── instrumentation.py (instrument_agent, _wire_interactive_permissions, TUILogHandler)
  │     └── messages.py
  └── helpers.py         (format_tokens)

cli.py (Click entry point)
  └── app.py (SageTUIApp)
```

No circular dependencies. `messages.py` and `helpers.py` are leaf modules.

## Event Flow

The app uses an event-driven architecture bridging sage-agent's typed event system with Textual's message system:

1. `instrument_agent()` subscribes to sage agent events via `agent.on(EventType, callback)`.
2. Callbacks convert sage events into Textual `Message` subclasses and post them via `app.post_message()`.
3. `SageTUIApp` has `on_<message_name>()` handlers that update widgets.

The event mapping:

- `sage.events.ToolStarted` -> `ToolCallStarted` message -> `on_tool_call_started()` -> creates `ToolEntry` widget
- `sage.events.ToolCompleted` -> `ToolCallCompleted` message -> `on_tool_call_completed()` -> updates `ToolEntry` result
- `sage.events.LLMStreamDelta` -> `StreamChunkReceived` message -> `on_stream_chunk_received()` -> appends to `AssistantEntry`
- `sage.events.LLMTurnStarted` -> `TurnStarted` message -> `on_turn_started()` -> updates status bar
- `sage.events.DelegationStarted` -> `DelegationEventStarted` message -> `on_delegation_event_started()` -> updates status panel

Internally generated messages:

- `AgentResponseReady` -- batch mode response complete
- `AgentError` -- `agent.run()` or `agent.stream()` failed
- `StreamFinished` -- streaming response complete
- `SessionTitleGenerated` -- background LLM title generation complete
- `_LogRecord` -- forwarded logging record from `TUILogHandler`

## Widget Hierarchy

```
SageTUIApp
  ├── Horizontal (#main-layout)
  │     ├── ChatPanel (#chat-panel)
  │     │     ├── Label (#chat-label) — "CHAT"
  │     │     ├── ChatScroll (#chat-scroll) — VerticalScroll with auto-pin
  │     │     │     ├── UserEntry* — user messages
  │     │     │     ├── ThinkingEntry* — animated indicator (removed when response starts)
  │     │     │     ├── ToolEntry* — collapsible tool call blocks
  │     │     │     └── AssistantEntry* — markdown-rendered responses
  │     │     └── HistoryInput (#chat-input) — multiline input with history
  │     └── StatusPanel (#status-panel) — hidden by default
  │           ├── Static (#session-section)
  │           ├── Static (#context-section) — usage bar
  │           ├── Static (#tokens-section) — breakdown
  │           ├── Static (#agent-section)
  │           ├── Collapsible (#skills-collapsible)
  │           │     └── Static (#skills-content)
  │           └── Static (#active-section)
  ├── LogPanel (#log-panel) — hidden by default
  │     ├── Label (#log-label) — "LOGS"
  │     └── RichLog (#log-output)
  └── StatusBar (#status-bar) — docked bottom
```

Widgets marked with `*` are dynamically mounted during conversation.

## CSS Strategy

- **app.tcss** -- loaded by `SageTUIApp` via `CSS_PATH = "app.tcss"`. Contains all presentational CSS (layout, colors, padding, borders).
- **DEFAULT_CSS on widgets** -- used ONLY for behavioral defaults that must apply regardless of context. Currently only `display: none` on `StatusPanel` and `LogPanel` (so they start hidden even in test apps that don't load `app.tcss`).

## Auto-Scroll Pin Logic

`ChatScroll` (a `VerticalScroll` subclass) tracks whether the user is "pinned" to the bottom:

- `watch_scroll_y()` reactively checks if `scroll_y >= max_scroll_y - 2`.
- If pinned: new content triggers `scroll_end(animate=False)` via `call_after_refresh`.
- If the user scrolled up: new content does NOT pull them back down.
- Sending a message always re-pins.
- The pin state is NOT re-checked per streaming chunk (would cause false un-pin during rapid streaming).

## Permission System

`_wire_interactive_permissions()` in `instrumentation.py` recursively replaces `PolicyPermissionHandler` instances on the agent and all subagents with `InteractivePermissionHandler`. This routes tool approval through the TUI's `PermissionScreen` modal instead of raising `PermissionError`.

The modal shows the tool name and key argument (command/url/path/file_path) and waits for Y/N input.

## Session Lifecycle

1. **Mount**: Generate UUID4 session ID, create Agent from config, wire permissions, instrument events, initialize status panel.
2. **Chat**: User submits query -> disable input -> show `ThinkingEntry` -> run agent (stream or batch) -> tool calls appear as `ToolEntry` -> response appears as `AssistantEntry` -> update stats -> re-enable input -> schedule background title generation.
3. **New Session** (Ctrl+N): Clear chat entries, cancel title task, generate new session ID, reset agent (clear history + usage).
4. **Unmount**: Remove log handler, restore logger config, close agent.

## Background Title Generation

After the first turn (and after context compaction), a fire-and-forget `asyncio.Task` calls the agent's provider to generate a short session title (max 50 chars). The task is cancelled if the user sends a new message or starts a new session before it completes.
