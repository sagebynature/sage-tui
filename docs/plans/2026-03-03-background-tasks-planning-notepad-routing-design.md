# Design: Background Tasks, Planning, Notepad & Category Routing

**Date:** 2026-03-03
**Status:** Approved
**Scope:** sage-tui — surface new sage-agent 1.5.0 features in the TUI

---

## Overview

Update sage-tui to reflect four new sage-agent 1.5.0 capabilities:

1. **Background task completions** — inline chat cards when async delegations finish
2. **Plan state** — live task list in the Status panel
3. **Notepad** — collapsible working-memory section in the Status panel
4. **Category routing** — category badge in chat delegation messages and status bar

Reference design: oh-my-opencode (task notifications, plan display, notepad structure).

---

## Approach

**Event + post-tool refresh (Approach B)**

- Wire the new `BackgroundTaskCompleted` sage-agent event for inline cards
- Refresh plan/notepad after every `ToolCompleted` whose name starts with `plan_` or `notepad_`
- Extend `DelegationEventStarted` with `category: str | None` — read defensively from event
- Catch-all plan/notepad refresh in `_finish_turn`

---

## Section 1: New Messages (`messages.py`)

```python
class BackgroundTaskDone(Message):
    task_id: str
    agent_name: str
    status: str          # "completed" | "failed" | "cancelled"
    result: str | None
    error: str | None
    duration_s: float

class DelegationEventStarted(Message):  # existing — add field
    target: str
    task: str
    category: str | None = None  # NEW

class PlanStateChanged(Message):
    plan_name: str
    tasks: list[dict]    # [{"description": str, "status": str}, ...]

class NotepadChanged(Message):
    plan_name: str
    content: str         # notepad.read_all() output
```

`DelegationEventStarted` gains one optional field — no breaking change.

---

## Section 2: New Widget (`widgets.py`)

**`BackgroundTaskEntry`** — non-collapsible inline card:

```
◉ executor  [completed]  1.8s
  Found 3 relevant files in src/api/...
```

- Line 1: bold dot + agent name | color-coded status badge | dim duration
- Line 2: result preview (120 chars, dim) or error text (red) for failed tasks
- Status colors: `[green]completed` / `[red]failed` / `[dim]cancelled`
- Mounted via `chat.add_background_task()` in the chat scroll flow

CSS: `height: auto`, `padding: 0 1`, `margin-bottom: 1`, `border-left: solid $warning`

---

## Section 3: StatusPanel Additions (`widgets.py`)

### PLAN section

Rendered below ACTIVE AGENTS. Hidden when no active plans on disk.

```
PLAN  my-plan-name
  ✓ Research codebase structure
  ● Implement background tasks
  ○ Write tests
  ✗ Validate config parsing
```

- `✓` green = completed, `●` yellow = in_progress, `○` dim = pending, `✗` red = failed
- Task descriptions truncated to 30 chars
- Refreshed on `PlanStateChanged` and `_finish_turn`

### NOTEPAD section

Collapsible (like SKILLS), collapsed by default.

```
NOTEPAD  (my-plan-name)  ▶
```

When expanded: renders `notepad.read_all()` as a `Markdown` widget.
Refreshed on `NotepadChanged` and `_finish_turn`.

---

## Section 4: Instrumentation Changes (`instrumentation.py`)

1. Subscribe to `BackgroundTaskCompleted` event:
   - Call `agent._bg_manager.get(task_id)` for duration
   - Post `BackgroundTaskDone` message

2. Extend `on_delegation_started`:
   - Read `getattr(e, "category", None)` defensively
   - Include in `DelegationEventStarted`

---

## Section 5: App Changes (`app.py`)

1. **`on_background_task_done`** → `chat.add_background_task(...)` (new card inline)

2. **`on_delegation_event_started`** (extended):
   - Pass `category` to `StatusPanel.set_active_delegation()`
   - Update `StatusBar` with transient category badge when non-None

3. **`on_tool_call_completed`** (extended):
   - If `event.tool_name.startswith(("plan_", "notepad_"))`: read disk and post `PlanStateChanged` + `NotepadChanged`

4. **`_finish_turn`** (extended):
   - Catch-all: read `PlanStateManager().list_active()` and refresh plan/notepad sections

---

## Files Changed

| File | Change |
|------|--------|
| `sage_tui/messages.py` | Add `BackgroundTaskDone`, `PlanStateChanged`, `NotepadChanged`; extend `DelegationEventStarted` |
| `sage_tui/widgets.py` | Add `BackgroundTaskEntry`; extend `StatusPanel`, `ChatPanel`, `StatusBar` |
| `sage_tui/instrumentation.py` | Wire `BackgroundTaskCompleted`; extend delegation handler |
| `sage_tui/app.py` | Add 4 new/extended handlers; plan/notepad refresh logic |
| `sage_tui/app.tcss` | Add `BackgroundTaskEntry` rule |

---

## Non-Goals

- No interactive notepad editing in TUI
- No plan creation from TUI (agent-driven only)
- No polling / timer-based refresh
- No changes to permission system or orchestration modal
