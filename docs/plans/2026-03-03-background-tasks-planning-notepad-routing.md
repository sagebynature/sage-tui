# Background Tasks, Planning, Notepad & Category Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface sage-agent 1.5.0 features (background tasks, plan state, notepad, category routing) in the TUI.

**Architecture:** Event-driven — wire `BackgroundTaskCompleted` for inline chat cards; read `PlanStateManager` / `Notepad` from disk after plan/notepad tool calls and at turn end; extend `DelegationEventStarted` with an optional `category` field read defensively from the agent event.

**Tech Stack:** Python 3.10+, Textual, sage-agent 1.5.0rc1 (`sage.events.BackgroundTaskCompleted`, `sage.planning.state.PlanStateManager`, `sage.planning.notepad.Notepad`), pytest-asyncio

---

## Task 1: Extend messages.py

**Files:**
- Modify: `sage_tui/messages.py`
- Test: `tests/test_messages.py` (create)

### Step 1: Write failing tests

```python
# tests/test_messages.py
from sage_tui.messages import (
    BackgroundTaskDone,
    DelegationEventStarted,
    NotepadChanged,
    PlanStateChanged,
)


def test_background_task_done_fields() -> None:
    msg = BackgroundTaskDone(
        task_id="abc123",
        agent_name="executor",
        status="completed",
        result="done",
        error=None,
        duration_s=1.8,
    )
    assert msg.task_id == "abc123"
    assert msg.agent_name == "executor"
    assert msg.status == "completed"
    assert msg.result == "done"
    assert msg.error is None
    assert msg.duration_s == 1.8


def test_background_task_done_failed() -> None:
    msg = BackgroundTaskDone(
        task_id="x",
        agent_name="worker",
        status="failed",
        result=None,
        error="timeout",
        duration_s=0.5,
    )
    assert msg.status == "failed"
    assert msg.error == "timeout"
    assert msg.result is None


def test_delegation_event_started_has_category() -> None:
    msg = DelegationEventStarted(target="coder", task="write tests", category="quick")
    assert msg.category == "quick"


def test_delegation_event_started_category_defaults_none() -> None:
    msg = DelegationEventStarted(target="coder", task="write tests")
    assert msg.category is None


def test_plan_state_changed_fields() -> None:
    tasks = [{"description": "Do X", "status": "pending"}]
    msg = PlanStateChanged(plan_name="my-plan", tasks=tasks)
    assert msg.plan_name == "my-plan"
    assert msg.tasks == tasks


def test_notepad_changed_fields() -> None:
    msg = NotepadChanged(plan_name="my-plan", content="### learnings\nnotes here")
    assert msg.plan_name == "my-plan"
    assert "learnings" in msg.content
```

### Step 2: Run to verify failure

```bash
cd /home/sachoi/sagebynature/sage-tui
uv run pytest tests/test_messages.py -v
```

Expected: ImportError — `BackgroundTaskDone`, `PlanStateChanged`, `NotepadChanged` don't exist yet; `DelegationEventStarted` missing `category`.

### Step 3: Implement — add new messages and extend DelegationEventStarted

In `sage_tui/messages.py`:

**Replace** `DelegationEventStarted`:
```python
class DelegationEventStarted(Message):
    """Emitted when the agent delegates to a subagent."""

    def __init__(self, target: str, task: str, category: str | None = None) -> None:
        super().__init__()
        self.target = target
        self.task = task
        self.category = category
```

**Add** after `SessionTitleGenerated`:
```python
class BackgroundTaskDone(Message):
    """Emitted when a background task completes, fails, or is cancelled."""

    def __init__(
        self,
        task_id: str,
        agent_name: str,
        status: str,
        result: str | None,
        error: str | None,
        duration_s: float,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.agent_name = agent_name
        self.status = status
        self.result = result
        self.error = error
        self.duration_s = duration_s


class PlanStateChanged(Message):
    """Emitted when plan state on disk has been refreshed."""

    def __init__(self, plan_name: str, tasks: list[dict]) -> None:
        super().__init__()
        self.plan_name = plan_name
        self.tasks = tasks


class NotepadChanged(Message):
    """Emitted when notepad content on disk has been refreshed."""

    def __init__(self, plan_name: str, content: str) -> None:
        super().__init__()
        self.plan_name = plan_name
        self.content = content
```

### Step 4: Run tests to verify pass

```bash
uv run pytest tests/test_messages.py -v
```

Expected: 7 tests PASS.

### Step 5: Commit

```bash
git add sage_tui/messages.py tests/test_messages.py
git commit -m "feat: add BackgroundTaskDone, PlanStateChanged, NotepadChanged messages; extend DelegationEventStarted with category"
```

---

## Task 2: BackgroundTaskEntry widget + ChatPanel.add_background_task

**Files:**
- Modify: `sage_tui/widgets.py`
- Modify: `sage_tui/app.tcss`
- Test: `tests/test_app.py` (add tests)

### Step 1: Write failing tests

Add these tests to `tests/test_app.py`:

```python
# Add to imports at top of test_app.py
from sage_tui.widgets import BackgroundTaskEntry  # noqa: F401 – will exist after impl


async def test_background_task_entry_completed_mounts(widget_app) -> None:
    app = widget_app(BackgroundTaskEntry("executor", "completed", "all done", None, 1.8))
    async with app.run_test():
        widget = app.query_one(BackgroundTaskEntry)
        assert widget is not None


async def test_background_task_entry_failed_mounts(widget_app) -> None:
    app = widget_app(BackgroundTaskEntry("worker", "failed", None, "timeout", 0.5))
    async with app.run_test():
        widget = app.query_one(BackgroundTaskEntry)
        assert widget._status == "failed"
        assert widget._error == "timeout"


async def test_background_task_entry_result_truncated(widget_app) -> None:
    long_result = "x" * 200
    app = widget_app(BackgroundTaskEntry("agent", "completed", long_result, None, 0.1))
    async with app.run_test():
        widget = app.query_one(BackgroundTaskEntry)
        assert widget._result is not None
        assert len(widget._result) == 200  # stored full; rendering truncates


async def test_chat_panel_add_background_task(widget_app) -> None:
    app = widget_app(ChatPanel(id="chat"))
    async with app.run_test() as pilot:
        panel = app.query_one(ChatPanel)
        panel.add_background_task("executor", "completed", "result text", None, 1.2)
        await pilot.pause()
        assert len(app.query(BackgroundTaskEntry)) == 1
```

### Step 2: Run to verify failure

```bash
uv run pytest tests/test_app.py::test_background_task_entry_completed_mounts tests/test_app.py::test_background_task_entry_failed_mounts tests/test_app.py::test_background_task_entry_result_truncated tests/test_app.py::test_chat_panel_add_background_task -v
```

Expected: ImportError on `BackgroundTaskEntry`.

### Step 3: Implement BackgroundTaskEntry in widgets.py

Add after `ToolEntry` class:

```python
class BackgroundTaskEntry(Widget):
    """Inline card for a completed background task. Non-collapsible."""

    def __init__(
        self,
        agent_name: str,
        status: str,
        result: str | None,
        error: str | None,
        duration_s: float,
    ) -> None:
        super().__init__()
        self._agent_name = agent_name
        self._status = status
        self._result = result
        self._error = error
        self._duration_s = duration_s

    def compose(self) -> ComposeResult:
        status_colors = {"completed": "green", "failed": "red", "cancelled": "dim"}
        color = status_colors.get(self._status, "dim")
        dot = "\u25ce" if self._status == "cancelled" else "\u25cf"
        duration = f"  [dim]{self._duration_s:.1f}s[/dim]"
        header = (
            f"[{color}]{dot}[/{color}]"
            f" [bold]{self._agent_name}[/bold]"
            f"  [{color}]{self._status}[/{color}]{duration}"
        )
        if self._status == "failed" and self._error:
            preview = self._error[:120] + "\u2026" if len(self._error) > 120 else self._error
            body = f"  [red]{preview}[/red]"
        elif self._result:
            preview = self._result[:120] + "\u2026" if len(self._result) > 120 else self._result
            body = f"  [dim]{preview}[/dim]"
        else:
            body = ""
        yield Static(header, id="bg-header")
        if body:
            yield Static(body, id="bg-body")
```

### Step 4: Add add_background_task to ChatPanel

In `ChatPanel.clear_entries`, after the existing methods, add:

```python
def add_background_task(
    self,
    agent_name: str,
    status: str,
    result: str | None,
    error: str | None,
    duration_s: float,
) -> BackgroundTaskEntry:
    """Append a BackgroundTaskEntry card inline in the chat scroll."""
    scroll = self.query_one("#chat-scroll", VerticalScroll)
    entry = BackgroundTaskEntry(agent_name, status, result, error, duration_s)
    scroll.mount(entry)
    self.call_after_refresh(self._maybe_scroll_end)
    return entry
```

### Step 5: Add CSS for BackgroundTaskEntry in app.tcss

Add after `ToolEntry` block:

```css
/* -- BackgroundTaskEntry -- */
BackgroundTaskEntry {
    height: auto;
    padding: 0 1;
    margin-bottom: 1;
    border-left: solid $warning;
}
```

### Step 6: Run tests

```bash
uv run pytest tests/test_app.py::test_background_task_entry_completed_mounts tests/test_app.py::test_background_task_entry_failed_mounts tests/test_app.py::test_background_task_entry_result_truncated tests/test_app.py::test_chat_panel_add_background_task -v
```

Expected: 4 PASS.

### Step 7: Run full suite to check no regressions

```bash
uv run pytest tests/ -v
```

Expected: all existing tests still PASS.

### Step 8: Commit

```bash
git add sage_tui/widgets.py sage_tui/app.tcss tests/test_app.py
git commit -m "feat: add BackgroundTaskEntry widget and ChatPanel.add_background_task"
```

---

## Task 3: StatusPanel — PLAN and NOTEPAD sections

**Files:**
- Modify: `sage_tui/widgets.py` (StatusPanel)
- Test: `tests/test_app.py` (add tests)

### Step 1: Write failing tests

Add to `tests/test_app.py`:

```python
async def test_status_panel_update_plan_shows_tasks(widget_app, mock_agent) -> None:
    app = widget_app(StatusPanel(id="status"))
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.display = True
        panel.set_session("abcd1234abcd1234abcd1234abcd1234", "")
        panel.initialize(mock_agent)
        tasks = [
            {"description": "Research codebase", "status": "completed"},
            {"description": "Implement feature", "status": "in_progress"},
            {"description": "Write tests", "status": "pending"},
        ]
        panel.update_plan("my-plan", tasks)
        plan_widget = panel.query_one("#plan-section", Static)
        assert plan_widget is not None


async def test_status_panel_clear_plan_hides_section(widget_app, mock_agent) -> None:
    app = widget_app(StatusPanel(id="status"))
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.display = True
        panel.set_session("abcd1234abcd1234abcd1234abcd1234", "")
        panel.initialize(mock_agent)
        panel.clear_plan()
        plan_widget = panel.query_one("#plan-section", Static)
        assert plan_widget.display is False


async def test_status_panel_update_notepad_sets_content(widget_app, mock_agent) -> None:
    app = widget_app(StatusPanel(id="status"))
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.display = True
        panel.set_session("abcd1234abcd1234abcd1234abcd1234", "")
        panel.initialize(mock_agent)
        panel.update_notepad("my-plan", "### learnings\nKey insight here")
        collapsible = panel.query_one("#notepad-collapsible", Collapsible)
        assert collapsible is not None


async def test_status_panel_set_active_delegation_with_category(widget_app, mock_agent) -> None:
    app = widget_app(StatusPanel(id="status"))
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.display = True
        panel.set_session("abcd1234abcd1234abcd1234abcd1234", "")
        panel.initialize(mock_agent)
        # Should not raise; category shown inline
        panel.set_active_delegation("coder", "write tests", category="quick")
```

### Step 2: Run to verify failure

```bash
uv run pytest tests/test_app.py::test_status_panel_update_plan_shows_tasks tests/test_app.py::test_status_panel_clear_plan_hides_section tests/test_app.py::test_status_panel_update_notepad_sets_content tests/test_app.py::test_status_panel_set_active_delegation_with_category -v
```

Expected: FAIL — `#plan-section`, `#notepad-collapsible` don't exist; `set_active_delegation` missing `category` param.

### Step 3: Implement StatusPanel changes

**3a. Update `StatusPanel.compose`** — add two new sections after `#active-section`:

```python
def compose(self) -> ComposeResult:
    yield Static("", id="session-section", classes="section")
    yield Static("", id="context-section", classes="section")
    yield Static("", id="tokens-section", classes="section")
    yield Static("", id="agent-section", classes="section")
    with Collapsible(
        title="SKILLS", collapsed=True, id="skills-collapsible", classes="section"
    ):
        yield Static("", id="skills-content")
    yield Static("", id="active-section", classes="section")
    yield Static("", id="plan-section", classes="section")
    with Collapsible(
        title="NOTEPAD", collapsed=True, id="notepad-collapsible", classes="section"
    ):
        yield Markdown("", id="notepad-content")
```

**3b. Add `update_plan`, `clear_plan`, `update_notepad` methods:**

```python
def update_plan(self, plan_name: str, tasks: list[dict]) -> None:
    """Render plan task list in the PLAN section."""
    _STATUS_ICONS = {
        "completed": ("[green]\u2713[/green]", "green"),
        "in_progress": ("[yellow]\u25cf[/yellow]", "yellow"),
        "pending": ("[dim]\u25cb[/dim]", "dim"),
        "failed": ("[red]\u2717[/red]", "red"),
    }
    lines = [f"[bold]PLAN[/bold]  [dim]{plan_name}[/dim]"]
    for t in tasks:
        icon, color = _STATUS_ICONS.get(t["status"], ("[dim]\u25cb[/dim]", "dim"))
        desc = t["description"]
        if len(desc) > 30:
            desc = desc[:27] + "\u2026"
        lines.append(f"  {icon} [{color}]{desc}[/{color}]")
    widget = self.query_one("#plan-section", Static)
    widget.update("\n".join(lines))
    widget.display = True

def clear_plan(self) -> None:
    """Hide the PLAN section when no active plans exist."""
    self.query_one("#plan-section", Static).display = False

def update_notepad(self, plan_name: str, content: str) -> None:
    """Update notepad collapsible with latest content."""
    collapsible = self.query_one("#notepad-collapsible", Collapsible)
    collapsible.title = f"NOTEPAD  [dim]({plan_name})[/dim]"
    self.query_one("#notepad-content", Markdown).update(content)
```

**3c. Extend `set_active_delegation`** to accept optional `category`:

```python
def set_active_delegation(self, target: str, task: str, category: str | None = None) -> None:
    preview = task[:45] + "\u2026" if len(task) > 45 else task
    cat_badge = f"  [cyan][{category}][/cyan]" if category else ""
    self.query_one("#active-section", Static).update(
        f"[bold]ACTIVE AGENTS[/bold]\n"
        f"  [yellow]\u21b3[/yellow] {target}{cat_badge}  [dim]{preview!r}[/dim]"
    )
```

**3d. Call `clear_plan()` in `initialize()`** so the section starts hidden:

In `initialize`, after `self.clear_active_delegation()`, add:
```python
self.clear_plan()
```

### Step 4: Run tests

```bash
uv run pytest tests/test_app.py::test_status_panel_update_plan_shows_tasks tests/test_app.py::test_status_panel_clear_plan_hides_section tests/test_app.py::test_status_panel_update_notepad_sets_content tests/test_app.py::test_status_panel_set_active_delegation_with_category -v
```

Expected: 4 PASS.

### Step 5: Run full suite

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

### Step 6: Commit

```bash
git add sage_tui/widgets.py tests/test_app.py
git commit -m "feat: add PLAN and NOTEPAD sections to StatusPanel; extend set_active_delegation with category"
```

---

## Task 4: StatusBar category badge

**Files:**
- Modify: `sage_tui/widgets.py` (StatusBar)
- Test: `tests/test_app.py` (add test)

### Step 1: Write failing test

Add to `tests/test_app.py`:

```python
async def test_status_bar_shows_category_when_set(widget_app) -> None:
    from sage_tui.widgets import StatusBar

    app = widget_app(StatusBar(id="bar"))
    async with app.run_test() as pilot:
        bar = app.query_one(StatusBar)
        bar.set_state("Streaming\u2026", "sage", "gpt-4o", False, streaming_mode=True)
        bar.set_active_category("deep")
        await pilot.pause()
        assert bar._active_category == "deep"

async def test_status_bar_clears_category(widget_app) -> None:
    from sage_tui.widgets import StatusBar

    app = widget_app(StatusBar(id="bar"))
    async with app.run_test() as pilot:
        bar = app.query_one(StatusBar)
        bar.set_active_category("deep")
        bar.set_active_category(None)
        await pilot.pause()
        assert bar._active_category is None
```

### Step 2: Run to verify failure

```bash
uv run pytest tests/test_app.py::test_status_bar_shows_category_when_set tests/test_app.py::test_status_bar_clears_category -v
```

Expected: FAIL — `set_active_category` doesn't exist.

### Step 3: Implement in StatusBar

Add to `StatusBar`:

```python
_active_category: str | None = None

def set_active_category(self, category: str | None) -> None:
    self._active_category = category
    self._refresh()
```

In `StatusBar._refresh`, add the category badge after `stream_badge`:

```python
cat_badge = (
    f" [cyan dim][{self._active_category}][/cyan dim]"
    if self._active_category
    else ""
)
```

And include `{cat_badge}` in the `self.update(...)` call, after `{stream_badge}`:

```python
self.update(
    f"[{colour}]\u25cf {self._state}[/{colour}]  [bold]{self._agent_name}[/bold]"
    f" ([dim]{self._model}[/dim]){stream_badge}{cat_badge}    "
    f"[{token_colour}]{token_str}[/{token_colour}]{cost_str}    "
    f"[dim]ctrl+b: status  ctrl+n: new session  ctrl+s: stream  ctrl+l: logs  ctrl+q: quit[/dim]{hint}"
)
```

### Step 4: Run tests

```bash
uv run pytest tests/test_app.py::test_status_bar_shows_category_when_set tests/test_app.py::test_status_bar_clears_category -v
```

Expected: 2 PASS.

### Step 5: Run full suite

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

### Step 6: Commit

```bash
git add sage_tui/widgets.py tests/test_app.py
git commit -m "feat: add category badge to StatusBar"
```

---

## Task 5: Instrumentation wiring

**Files:**
- Modify: `sage_tui/instrumentation.py`
- Test: `tests/test_instrumentation.py` (create)

### Step 1: Write failing tests

```python
# tests/test_instrumentation.py
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sage_tui.messages import BackgroundTaskDone, DelegationEventStarted


@pytest.mark.asyncio
async def test_instrument_agent_wires_background_task_completed() -> None:
    from sage_tui.instrumentation import instrument_agent

    mock_app = MagicMock()
    mock_app.post_message = MagicMock()

    mock_agent = MagicMock()
    mock_agent.on = MagicMock()

    # Capture registered handlers by event class
    handlers = {}

    def capture_on(event_class, callback):
        handlers[event_class] = callback

    mock_agent.on.side_effect = capture_on

    # Mock _bg_manager
    from sage.coordination.background import BackgroundTaskInfo

    task_info = BackgroundTaskInfo(
        task_id="t1",
        agent_name="executor",
        status="completed",
        created_at=time.time() - 2.0,
        completed_at=time.time(),
        result="done",
        error=None,
    )
    mock_agent._bg_manager = MagicMock()
    mock_agent._bg_manager.get = MagicMock(return_value=task_info)

    instrument_agent(mock_agent, mock_app)

    # Find BackgroundTaskCompleted handler
    from sage.events import BackgroundTaskCompleted

    assert BackgroundTaskCompleted in handlers

    # Fire the event
    event = BackgroundTaskCompleted(
        task_id="t1", agent_name="executor", status="completed", result="done", error=None
    )
    await handlers[BackgroundTaskCompleted](event)

    # Verify BackgroundTaskDone posted
    call_args = mock_app.post_message.call_args_list
    bg_messages = [c for c in call_args if isinstance(c.args[0], BackgroundTaskDone)]
    assert len(bg_messages) == 1
    msg = bg_messages[0].args[0]
    assert msg.agent_name == "executor"
    assert msg.status == "completed"
    assert msg.result == "done"
    assert msg.duration_s >= 0.0


@pytest.mark.asyncio
async def test_instrument_agent_delegation_includes_category() -> None:
    from sage_tui.instrumentation import instrument_agent

    mock_app = MagicMock()
    mock_app.post_message = MagicMock()

    mock_agent = MagicMock()
    mock_agent.on = MagicMock()
    mock_agent._bg_manager = MagicMock()
    mock_agent._bg_manager.get = MagicMock(return_value=None)

    handlers = {}

    def capture_on(event_class, callback):
        handlers[event_class] = callback

    mock_agent.on.side_effect = capture_on

    instrument_agent(mock_agent, mock_app)

    from sage.events import DelegationStarted

    # Event with category field
    event = MagicMock(spec=DelegationStarted)
    event.target = "coder"
    event.task = "write tests"
    event.category = "quick"

    await handlers[DelegationStarted](event)

    call_args = mock_app.post_message.call_args_list
    deleg_messages = [c for c in call_args if isinstance(c.args[0], DelegationEventStarted)]
    assert len(deleg_messages) == 1
    msg = deleg_messages[0].args[0]
    assert msg.category == "quick"


@pytest.mark.asyncio
async def test_instrument_agent_delegation_category_defaults_none_when_absent() -> None:
    from sage_tui.instrumentation import instrument_agent

    mock_app = MagicMock()
    mock_app.post_message = MagicMock()

    mock_agent = MagicMock()
    mock_agent.on = MagicMock()
    mock_agent._bg_manager = MagicMock()
    mock_agent._bg_manager.get = MagicMock(return_value=None)

    handlers = {}

    def capture_on(event_class, callback):
        handlers[event_class] = callback

    mock_agent.on.side_effect = capture_on

    instrument_agent(mock_agent, mock_app)

    from sage.events import DelegationStarted

    # Event WITHOUT category field (older event)
    event = MagicMock(spec=DelegationStarted)
    event.target = "coder"
    event.task = "write tests"
    del event.category  # ensure attribute doesn't exist

    await handlers[DelegationStarted](event)

    call_args = mock_app.post_message.call_args_list
    deleg_messages = [c for c in call_args if isinstance(c.args[0], DelegationEventStarted)]
    assert len(deleg_messages) == 1
    assert deleg_messages[0].args[0].category is None
```

### Step 2: Run to verify failure

```bash
uv run pytest tests/test_instrumentation.py -v
```

Expected: FAIL — `BackgroundTaskCompleted` not wired; `DelegationEventStarted` missing category.

### Step 3: Implement instrumentation changes

In `sage_tui/instrumentation.py`:

**Add import** at top of the `from sage.events import ...` block:
```python
from sage.events import (
    BackgroundTaskCompleted,
    DelegationStarted,
    LLMStreamDelta,
    LLMTurnStarted,
    ToolCompleted,
    ToolStarted,
)
```

**Replace** `on_delegation_started`:
```python
async def on_delegation_started(e: DelegationStarted) -> None:
    category = getattr(e, "category", None)
    app.post_message(DelegationEventStarted(e.target, e.task, category=category))
```

**Add** `on_background_task_completed` and wire it:
```python
async def on_background_task_completed(e: BackgroundTaskCompleted) -> None:
    info = agent._bg_manager.get(e.task_id)
    if info is not None and info.completed_at is not None:
        duration_s = info.completed_at - info.created_at
    else:
        duration_s = 0.0
    app.post_message(
        BackgroundTaskDone(
            task_id=e.task_id,
            agent_name=e.agent_name,
            status=e.status,
            result=e.result,
            error=e.error,
            duration_s=duration_s,
        )
    )

agent.on(BackgroundTaskCompleted, on_background_task_completed)
```

**Add** `BackgroundTaskDone` to imports from `sage_tui.messages`:
```python
from sage_tui.messages import (
    BackgroundTaskDone,
    DelegationEventStarted,
    StreamChunkReceived,
    ToolCallCompleted,
    ToolCallStarted,
    TurnStarted,
)
```

### Step 4: Run tests

```bash
uv run pytest tests/test_instrumentation.py -v
```

Expected: 3 PASS.

### Step 5: Run full suite

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

### Step 6: Commit

```bash
git add sage_tui/instrumentation.py tests/test_instrumentation.py
git commit -m "feat: wire BackgroundTaskCompleted event; pass category through delegation instrumentation"
```

---

## Task 6: App handlers — background tasks, category routing, plan/notepad refresh

**Files:**
- Modify: `sage_tui/app.py`
- Test: `tests/test_app.py` (add tests)

### Step 1: Write failing tests

Add to `tests/test_app.py`:

```python
async def test_app_background_task_done_adds_chat_entry(
    config_path: Path, mock_agent: MagicMock
) -> None:
    from sage_tui.app import SageTUIApp
    from sage_tui.messages import BackgroundTaskDone
    from sage_tui.widgets import BackgroundTaskEntry

    mock_agent.close = AsyncMock()

    with patch("sage_tui.app.Agent.from_config", return_value=mock_agent):
        app = SageTUIApp(config_path=config_path)
        async with app.run_test() as pilot:
            app.post_message(
                BackgroundTaskDone(
                    task_id="t1",
                    agent_name="executor",
                    status="completed",
                    result="task done",
                    error=None,
                    duration_s=2.1,
                )
            )
            await pilot.pause()
            assert len(app.query(BackgroundTaskEntry)) == 1
            await pilot.press("ctrl+q")


async def test_app_delegation_with_category_updates_status_bar(
    config_path: Path, mock_agent: MagicMock
) -> None:
    from sage_tui.app import SageTUIApp
    from sage_tui.messages import DelegationEventStarted
    from sage_tui.widgets import StatusBar

    mock_agent.close = AsyncMock()

    with patch("sage_tui.app.Agent.from_config", return_value=mock_agent):
        app = SageTUIApp(config_path=config_path)
        async with app.run_test() as pilot:
            app.post_message(
                DelegationEventStarted(target="coder", task="write tests", category="quick")
            )
            await pilot.pause()
            bar = app.query_one(StatusBar)
            assert bar._active_category == "quick"
            await pilot.press("ctrl+q")


async def test_app_plan_state_changed_updates_status_panel(
    config_path: Path, mock_agent: MagicMock
) -> None:
    from sage_tui.app import SageTUIApp
    from sage_tui.messages import PlanStateChanged

    mock_agent.close = AsyncMock()

    with patch("sage_tui.app.Agent.from_config", return_value=mock_agent):
        app = SageTUIApp(config_path=config_path)
        async with app.run_test() as pilot:
            app.post_message(
                PlanStateChanged(
                    plan_name="my-plan",
                    tasks=[{"description": "Do X", "status": "pending"}],
                )
            )
            await pilot.pause()
            from textual.widgets import Static
            plan_widget = app.query_one("#plan-section", Static)
            assert plan_widget.display is True
            await pilot.press("ctrl+q")


async def test_app_notepad_changed_updates_status_panel(
    config_path: Path, mock_agent: MagicMock
) -> None:
    from sage_tui.app import SageTUIApp
    from sage_tui.messages import NotepadChanged

    mock_agent.close = AsyncMock()

    with patch("sage_tui.app.Agent.from_config", return_value=mock_agent):
        app = SageTUIApp(config_path=config_path)
        async with app.run_test() as pilot:
            app.post_message(NotepadChanged(plan_name="my-plan", content="### learnings\nX"))
            await pilot.pause()
            # No crash = success; collapsible exists
            from textual.widgets import Collapsible
            collapsible = app.query_one("#notepad-collapsible", Collapsible)
            assert collapsible is not None
            await pilot.press("ctrl+q")
```

### Step 2: Run to verify failure

```bash
uv run pytest tests/test_app.py::test_app_background_task_done_adds_chat_entry tests/test_app.py::test_app_delegation_with_category_updates_status_bar tests/test_app.py::test_app_plan_state_changed_updates_status_panel tests/test_app.py::test_app_notepad_changed_updates_status_panel -v
```

Expected: FAIL — handlers not yet in app.py.

### Step 3: Implement app.py changes

**3a. Add imports** to existing import blocks:

```python
from sage_tui.messages import (
    AgentError,
    AgentResponseReady,
    BackgroundTaskDone,        # NEW
    DelegationEventStarted,
    NotepadChanged,             # NEW
    PlanStateChanged,           # NEW
    SessionTitleGenerated,
    StreamChunkReceived,
    StreamFinished,
    ToolCallCompleted,
    ToolCallStarted,
    TurnStarted,
)
```

And add to widget imports:
```python
from sage_tui.widgets import (
    AssistantEntry,
    BackgroundTaskEntry,        # NEW
    ChatPanel,
    HistoryInput,
    LogPanel,
    StatusBar,
    StatusPanel,
    ThinkingEntry,
    ToolEntry,
    UserEntry,
)
```

**3b. Add `on_background_task_done` handler** after `on_agent_error`:

```python
def on_background_task_done(self, event: BackgroundTaskDone) -> None:
    self.query_one(ChatPanel).add_background_task(
        event.agent_name, event.status, event.result, event.error, event.duration_s
    )
```

**3c. Extend `on_delegation_event_started`**:

```python
def on_delegation_event_started(self, event: DelegationEventStarted) -> None:
    self.query_one(StatusPanel).set_active_delegation(
        event.target, event.task, category=event.category
    )
    if event.category:
        self.query_one(StatusBar).set_active_category(event.category)
```

**3d. Extend `on_tool_call_completed`** — add plan/notepad refresh after existing logic:

```python
def on_tool_call_completed(self, event: ToolCallCompleted) -> None:
    queue = self._pending_tools.get(event.tool_name)
    if queue:
        entry = queue.pop(0)
        entry.set_result(event.result)
    if event.tool_name.startswith(("plan_", "notepad_")):
        self._refresh_plan_notepad()
```

**3e. Extend `_finish_turn`** — call `_refresh_plan_notepad()` and clear category:

```python
def _finish_turn(self) -> None:
    self.query_one(StatusPanel).clear_active_delegation()
    self.query_one(StatusBar).set_active_category(None)    # NEW — clear category badge
    self._refresh_plan_notepad()                             # NEW — catch-all refresh
    if self._agent:
        # ... rest of existing _finish_turn unchanged
```

**3f. Add `_refresh_plan_notepad` helper** after `_schedule_title_generation`:

```python
def _refresh_plan_notepad(self) -> None:
    """Read active plan and notepad from disk and post refresh messages."""
    try:
        from sage.planning.notepad import Notepad
        from sage.planning.state import PlanStateManager

        mgr = PlanStateManager()
        plan_names = mgr.list_active()
        if not plan_names:
            self.query_one(StatusPanel).clear_plan()
            return
        # Use the first (most recently modified) active plan
        plan = mgr.load(plan_names[0])
        if plan is None:
            self.query_one(StatusPanel).clear_plan()
            return
        tasks = [{"description": t.description, "status": t.status} for t in plan.tasks]
        self.post_message(PlanStateChanged(plan_name=plan.plan_name, tasks=tasks))
        try:
            notepad = Notepad(plan.plan_name)
            content = notepad.read_all()
            if content.strip():
                self.post_message(NotepadChanged(plan_name=plan.plan_name, content=content))
        except Exception:
            pass  # Notepad is optional
    except Exception:
        logger.debug("Plan/notepad refresh failed", exc_info=True)
```

**3g. Add message handlers** for `PlanStateChanged` and `NotepadChanged`:

```python
def on_plan_state_changed(self, event: PlanStateChanged) -> None:
    self.query_one(StatusPanel).update_plan(event.plan_name, event.tasks)

def on_notepad_changed(self, event: NotepadChanged) -> None:
    self.query_one(StatusPanel).update_notepad(event.plan_name, event.content)
```

**3h. Update `__all__`** to include `BackgroundTaskEntry`:

```python
__all__ = [
    "SageTUIApp",
    "AssistantEntry",
    "BackgroundTaskEntry",   # NEW
    "ChatPanel",
    ...
]
```

### Step 4: Run new tests

```bash
uv run pytest tests/test_app.py::test_app_background_task_done_adds_chat_entry tests/test_app.py::test_app_delegation_with_category_updates_status_bar tests/test_app.py::test_app_plan_state_changed_updates_status_panel tests/test_app.py::test_app_notepad_changed_updates_status_panel -v
```

Expected: 4 PASS.

### Step 5: Run full test suite

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

### Step 6: Commit

```bash
git add sage_tui/app.py tests/test_app.py
git commit -m "feat: add background task, plan, notepad, and category routing handlers in app"
```

---

## Final Verification

```bash
uv run pytest tests/ -v --tb=short
```

All tests green. Run lint:

```bash
uv run ruff check sage_tui/ tests/
uv run ty check
```

Fix any issues, then final commit if needed.

---

## Summary of All Changed Files

| File | What changed |
|------|-------------|
| `sage_tui/messages.py` | +`BackgroundTaskDone`, `PlanStateChanged`, `NotepadChanged`; extend `DelegationEventStarted` |
| `sage_tui/widgets.py` | +`BackgroundTaskEntry`; extend `ChatPanel`, `StatusPanel`, `StatusBar` |
| `sage_tui/instrumentation.py` | Wire `BackgroundTaskCompleted`; pass `category` in delegation |
| `sage_tui/app.py` | +4 message handlers; `_refresh_plan_notepad`; category/plan/notepad wiring |
| `sage_tui/app.tcss` | +`BackgroundTaskEntry` styling |
| `tests/test_messages.py` | New — 7 message field tests |
| `tests/test_instrumentation.py` | New — 3 instrumentation wiring tests |
| `tests/test_app.py` | +12 new widget/integration tests |
