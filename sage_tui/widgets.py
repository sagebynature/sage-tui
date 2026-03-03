"""TUI widget classes for sage-tui."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from textual import events
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import (
    Collapsible,
    Label,
    Markdown,
    RichLog,
    Static,
    TextArea,
)

from sage_tui.helpers import fmt_args, format_tokens
from sage_tui.instrumentation import _LOG_COLORS, _LOG_FMT

if TYPE_CHECKING:
    from sage.agent import Agent


class HistoryInput(TextArea):
    """Multiline input: Enter submits, Shift+Enter / Ctrl+J inserts newline.

    Supports up/down arrow history navigation when the content is a single line.
    """

    class Submitted(Message):
        """Emitted when the user presses Enter to submit."""

        def __init__(self, input: "HistoryInput", value: str) -> None:
            super().__init__()
            self.input = input
            self.value = value

        @property
        def control(self) -> "HistoryInput":
            return self.input

    def __init__(self, placeholder: str = "", **kwargs: object) -> None:
        super().__init__(
            show_line_numbers=False,
            soft_wrap=True,
            language=None,
            tab_behavior="focus",
            compact=True,
            highlight_cursor_line=False,
            placeholder=placeholder,
            **kwargs,  # type: ignore[arg-type]
        )
        self._history: list[str] = []
        self._history_idx: int = 0
        self._draft: str = ""

    # -- compatibility property ------------------------------------------------

    @property
    def value(self) -> str:
        """Alias for ``self.text`` so call-sites that used ``Input.value`` still work."""
        return self.text

    # -- public helpers (same API surface the app already uses) ----------------

    def append_history(self, value: str) -> None:
        """Add a submitted message to history and reset cursor to end."""
        if value:
            self._history.append(value)
        self._history_idx = len(self._history)
        self._draft = ""

    # -- key handling ----------------------------------------------------------

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            # Submit on plain Enter.
            event.prevent_default()
            event.stop()
            value = self.text.strip()
            if value:
                self.post_message(self.Submitted(self, value))
            return

        if event.key in ("shift+enter", "ctrl+j"):
            # Insert a newline.
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return

        # History navigation — only when content is a single line.
        if "\n" not in self.text:
            if event.key == "up" and self._history_idx > 0:
                if self._history_idx == len(self._history):
                    self._draft = self.text
                self._history_idx -= 1
                self.load_text(self._history[self._history_idx])
                self.move_cursor(self.document.end)
                event.prevent_default()
                event.stop()
                return
            if event.key == "down" and self._history_idx < len(self._history):
                self._history_idx += 1
                text = (
                    self._draft
                    if self._history_idx == len(self._history)
                    else self._history[self._history_idx]
                )
                self.load_text(text)
                self.move_cursor(self.document.end)
                event.prevent_default()
                event.stop()
                return

        await super()._on_key(event)


class UserEntry(Widget):
    """A single user message in the chat scroll view."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        lines = self._text.split("\n")
        # "You  ╷  " prefix is 8 visible chars; indent continuation lines to align.
        formatted = lines[0]
        if len(lines) > 1:
            formatted += "\n" + "\n".join("         " + ln for ln in lines[1:])
        yield Static(f"[bold cyan]You[/bold cyan]  [dim]╷[/dim]  {formatted}")


class ThinkingEntry(Widget):
    """Animated thinking indicator — removed when the response starts."""

    _FRAMES = ["\u25cc", "\u25ce", "\u25cf", "\u25ce"]

    def compose(self) -> ComposeResult:
        yield Static("[dim]\u25cc Thinking\u2026[/dim]", id="thinking-label")

    def on_mount(self) -> None:
        self._frame = 0
        self.set_interval(0.25, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self._FRAMES)
        self.query_one("#thinking-label", Static).update(
            f"[dim]{self._FRAMES[self._frame]} Thinking\u2026[/dim]"
        )


class ToolEntry(Widget):
    """A tool call rendered as a collapsible block. Yellow while running, green/red when done."""

    def __init__(self, tool_name: str, arguments: dict[str, Any]) -> None:
        super().__init__()
        self._tool_name = tool_name
        self._arguments = arguments
        self._result: str | None = None
        self._error: bool = False

    def _summary(self, icon: str = "\u25b6", color: str = "yellow") -> str:
        args_str = fmt_args(self._arguments)
        return f"[{color}]{icon}[/{color}]  [bold]{self._tool_name}[/bold]  [dim]{args_str}[/dim]"

    def compose(self) -> ComposeResult:
        with Collapsible(title=self._summary(), collapsed=True):
            yield Static(f"[dim]input:[/dim]   {self._arguments}", id="tool-input")
            yield Static("[dim]result:[/dim]  [dim]running\u2026[/dim]", id="tool-result")

    def set_result(self, result: str, error: bool = False) -> None:
        """Update the entry once the tool has completed."""
        self._result = result
        self._error = error
        color = "red" if error else "green"
        icon = "\u2717" if error else "\u2713"
        preview = result[:300] + "\u2026" if len(result) > 300 else result
        self.query_one(Collapsible).title = self._summary(icon=icon, color=color)
        self.query_one("#tool-result", Static).update(
            f"[dim]result:[/dim]  [{color}]{preview}[/{color}]"
        )


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


class AssistantEntry(Widget):
    """Agent response rendered as Markdown with streaming support."""

    def __init__(self) -> None:
        super().__init__()
        self._content = ""

    def compose(self) -> ComposeResult:
        yield Static("[bold green]Agent[/bold green]  [dim]╷[/dim]", classes="assistant-label")
        yield Markdown("", id="response-area")

    def append_chunk(self, chunk: str) -> None:
        """Append a streaming text chunk and re-render markdown."""
        self._content += chunk
        self.query_one("#response-area", Markdown).update(self._content)

    def set_text(self, text: str) -> None:
        """Set full text and render as markdown (non-streaming mode)."""
        self._content = text
        self.query_one("#response-area", Markdown).update(text)


class ChatScroll(VerticalScroll):
    """Chat scroll container that reactively tracks auto-scroll pin state.

    Watches ``scroll_y`` so that the parent :class:`ChatPanel` knows whether the
    user is "pinned" to the bottom (and should auto-scroll on new content) or
    has scrolled up to read history (and should *not* be yanked back down).
    """

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        """Update the parent's auto-scroll flag whenever scroll position changes."""
        super().watch_scroll_y(old_value, new_value)
        if isinstance(self.parent, ChatPanel):
            self.parent._auto_scroll = new_value >= self.max_scroll_y - 2


class ChatPanel(Widget):
    """Left panel: conversation history (typed entry widgets) and message input."""

    def compose(self) -> ComposeResult:
        yield Label("CHAT", id="chat-label")
        yield ChatScroll(id="chat-scroll")
        yield HistoryInput(
            placeholder="> Type a message\u2026 Enter to send, Shift+Enter for newline",
            id="chat-input",
        )

    # -- Scroll-pin logic ------------------------------------------------------
    # Auto-scroll follows output only while the user is "pinned" to the bottom.
    # If the user scrolls up to read history, we stop pulling them down.
    # Pinning resumes automatically when they scroll back to the bottom
    # (detected by ChatScroll.watch_scroll_y) or when they send a message.
    #
    # IMPORTANT: We do NOT re-check the pin state on every streaming chunk.
    # During rapid streaming, scroll_y lags behind max_scroll_y because
    # the previous scroll_end (via call_after_refresh) hasn't executed yet.
    # Re-checking per-chunk would incorrectly flip _auto_scroll to False,
    # causing the scroll to "stick" mid-stream even when the user hasn't
    # scrolled up.  Instead, ChatScroll's watch_scroll_y reactively tracks
    # the actual scroll position and updates _auto_scroll accordingly.

    _auto_scroll: bool = True

    def _maybe_scroll_end(self) -> None:
        """Scroll to bottom only if pinned — called via call_after_refresh."""
        if self._auto_scroll:
            self.query_one("#chat-scroll", VerticalScroll).scroll_end(animate=False)

    # -- Public API used by SageTUIApp ----------------------------------------

    def append_user_message(self, text: str) -> None:
        # User explicitly interacted — always re-pin.
        self._auto_scroll = True
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(UserEntry(text))
        self.call_after_refresh(self._maybe_scroll_end)

    def start_turn(self) -> None:
        """Show the animated thinking indicator."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(ThinkingEntry(id="thinking"))
        self.call_after_refresh(self._maybe_scroll_end)

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> ToolEntry:
        """Append a ToolEntry (yellow/running) and return it for later update."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        thinking = self.query("#thinking")
        if thinking:
            thinking.first().remove()
        entry = ToolEntry(tool_name, arguments)
        scroll.mount(entry)
        self.call_after_refresh(self._maybe_scroll_end)
        return entry

    def start_response(self) -> AssistantEntry:
        """Remove thinking indicator, append AssistantEntry, return it."""
        thinking = self.query("#thinking")
        if thinking:
            thinking.first().remove()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        entry = AssistantEntry()
        scroll.mount(entry)
        self.call_after_refresh(self._maybe_scroll_end)
        return entry

    def add_background_task(
        self,
        agent_name: str,
        status: str,
        result: str | None,
        error: str | None,
        duration_s: float,
    ) -> BackgroundTaskEntry:
        """Append a BackgroundTaskEntry card inline in the chat scroll and return it."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        entry = BackgroundTaskEntry(agent_name, status, result, error, duration_s)
        scroll.mount(entry)
        self.call_after_refresh(self._maybe_scroll_end)
        return entry

    def scroll_to_end(self) -> None:
        """Schedule a scroll-to-bottom respecting the pin state."""
        self.call_after_refresh(self._maybe_scroll_end)

    def clear_entries(self) -> None:
        self.query_one("#chat-scroll", VerticalScroll).remove_children()
        self._auto_scroll = True


class StatusPanel(Widget):
    """Right panel: session info, context, tokens, agent info, skills, active agents."""

    DEFAULT_CSS = """
    StatusPanel {
        display: none;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._session_id: str = ""
        self._session_title: str = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="session-section", classes="section")
        yield Static("", id="context-section", classes="section")
        yield Static("", id="tokens-section", classes="section")
        yield Static("", id="agent-section", classes="section")
        with Collapsible(
            title="SKILLS", collapsed=True, id="skills-collapsible", classes="section"
        ):
            yield Static("", id="skills-content")
        yield Static("", id="active-section")

    def set_session(self, session_id: str, title: str) -> None:
        """Set session identity. Call before initialize()."""
        self._session_id = session_id
        self._session_title = title
        self._render_session()

    def update_session_title(self, title: str) -> None:
        """Update the session title (e.g. from background LLM generation)."""
        self._session_title = title
        self._render_session()

    def _render_session(self) -> None:
        short_id = self._session_id[:8] if self._session_id else ""
        title_display = (
            f"  [bold]{self._session_title}[/bold]"
            if self._session_title
            else "  [dim](untitled)[/dim]"
        )
        self.query_one("#session-section", Static).update(
            f"[bold]SESSION[/bold]\n{title_display}\n  [dim]{short_id}[/dim]"
        )

    def initialize(self, agent: "Agent") -> None:
        """Populate static sections from agent config. Call once after mount."""
        import os

        cwd = os.getcwd()
        self.query_one("#agent-section", Static).update(
            f"[bold]AGENT[/bold]\n"
            f"  [dim]name[/dim]       {agent.name}\n"
            f"  [dim]model[/dim]      {agent.model}\n"
            f"  [dim]cwd[/dim]        {cwd}"
        )
        skill_names = [s.name for s in agent.skills]
        collapsible = self.query_one("#skills-collapsible", Collapsible)
        collapsible.title = f"SKILLS  ({len(skill_names)})" if skill_names else "SKILLS"
        skills_content = (
            "\n".join(f"[dim]\u2022[/dim] {n}" for n in skill_names) or "[dim](none)[/dim]"
        )
        self.query_one("#skills-content", Static).update(skills_content)
        self._render_session()
        self.update_stats({})
        self.clear_active_delegation()

    def update_stats(self, stats: dict[str, Any]) -> None:
        """Refresh context, token breakdown, and cost sections."""
        # -- Context section (progress bar + percentage + cost) --
        token_usage = int(stats.get("token_usage") or 0)
        limit = int(stats.get("context_window_limit") or 0)
        cost = float(stats.get("cumulative_cost") or 0.0)

        if limit > 0:
            ratio = min(1.0, token_usage / limit)
            filled = int(ratio * 15)
            bar = "\u2588" * filled + "\u2591" * (15 - filled)
            pct = int(ratio * 100)
            color = "red" if ratio >= 0.8 else ("yellow" if ratio >= 0.6 else "green")
            context_text = (
                f"[bold]CONTEXT[/bold]\n"
                f"  [{color}]{bar}[/{color}]  {pct}%\n"
                f"  [dim]({format_tokens(token_usage)} / {format_tokens(limit)})[/dim]\n"
                f"  [green]${cost:.4f}[/green] spent"
            )
        else:
            context_text = (
                f"[bold]CONTEXT[/bold]\n  [dim](unknown)[/dim]\n  [green]${cost:.4f}[/green] spent"
            )
        self.query_one("#context-section", Static).update(context_text)

        # -- Token breakdown --
        prompt = int(stats.get("cumulative_prompt_tokens") or 0)
        completion = int(stats.get("cumulative_completion_tokens") or 0)
        cache_read = int(stats.get("cumulative_cache_read_tokens") or 0)
        cache_write = int(stats.get("cumulative_cache_creation_tokens") or 0)
        reasoning = int(stats.get("cumulative_reasoning_tokens") or 0)

        tokens_lines = [
            "[bold]TOKENS[/bold]",
            f"  [dim]prompt[/dim]      {format_tokens(prompt)}",
            f"  [dim]completion[/dim]  {format_tokens(completion)}",
            f"  [dim]cache read[/dim]  {format_tokens(cache_read)}",
            f"  [dim]cache write[/dim] {format_tokens(cache_write)}",
        ]
        if reasoning:
            tokens_lines.append(f"  [dim]reasoning[/dim]  {format_tokens(reasoning)}")
        self.query_one("#tokens-section", Static).update("\n".join(tokens_lines))

    def set_active_delegation(self, target: str, task: str) -> None:
        preview = task[:45] + "\u2026" if len(task) > 45 else task
        self.query_one("#active-section", Static).update(
            f"[bold]ACTIVE AGENTS[/bold]\n  [yellow]\u21b3[/yellow] {target}  [dim]{preview!r}[/dim]"
        )

    def clear_active_delegation(self) -> None:
        self.query_one("#active-section", Static).update(
            "[bold]ACTIVE AGENTS[/bold]\n  [dim](idle)[/dim]"
        )


class LogPanel(Widget):
    """Docked-bottom log viewer, hidden by default. Toggle with ctrl+l."""

    DEFAULT_CSS = """
    LogPanel {
        display: none;
    }
    """

    _MAX_BUFFER = 500

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._buffer: list[logging.LogRecord] = []

    def compose(self) -> ComposeResult:
        yield Label("LOGS", id="log-label")
        yield RichLog(id="log-output", wrap=True, markup=True, highlight=False)

    def toggle_visibility(self) -> None:
        self.display = not self.display
        if self.display:
            # Flush buffered records that arrived while the panel was hidden.
            rich_log = self.query_one("#log-output", RichLog)
            for record in self._buffer:
                self._render_record(rich_log, record)
            self._buffer.clear()

    def write_record(self, record: logging.LogRecord) -> None:
        if not self.display:
            # Don't touch the RichLog while hidden — writing to it triggers
            # refresh() which causes a visible flash on every log event.
            if len(self._buffer) < self._MAX_BUFFER:
                self._buffer.append(record)
            return
        self._render_record(self.query_one("#log-output", RichLog), record)

    def _render_record(self, rich_log: RichLog, record: logging.LogRecord) -> None:
        color = _LOG_COLORS.get(record.levelno, "white")
        msg = _LOG_FMT.format(record)
        safe_msg = msg.replace("[", "\\[")
        rich_log.write(f"[{color}]{safe_msg}[/{color}]")


class StatusBar(Static):
    """Bottom bar: agent state, model info, and keyboard hints."""

    _token_usage: int = 0
    _context_window_limit: int | None = None
    _session_cost: float = 0.0
    _state: str = "Ready"
    _agent_name: str = ""
    _model: str = ""
    _has_subagents: bool = False
    _streaming_mode: bool = False

    def update_token_usage(self, token_usage: int, context_window_limit: int | None) -> None:
        self._token_usage = token_usage
        self._context_window_limit = context_window_limit
        self._refresh()

    def update_session_cost(self, cost: float) -> None:
        self._session_cost = cost
        self._refresh()

    def set_state(
        self,
        state: str,
        agent_name: str,
        model: str,
        has_subagents: bool,
        streaming_mode: bool = False,
    ) -> None:
        self._state = state
        self._agent_name = agent_name
        self._model = model
        self._has_subagents = has_subagents
        self._streaming_mode = streaming_mode
        self._refresh()

    def _refresh(self) -> None:
        colour = {
            "Ready": "green",
            "Thinking\u2026": "yellow",
            "Streaming\u2026": "cyan",
            "Error": "red",
        }.get(self._state, "white")
        hint = "  [dim]ctrl+o: orchestrate[/dim]" if self._has_subagents else ""
        stream_badge = (
            " [cyan]\u25c9 stream[/cyan]" if self._streaming_mode else " [dim]\u25cb batch[/dim]"
        )

        # Token usage display
        token_str = f"{format_tokens(self._token_usage)} tokens"
        token_colour = "dim"

        if self._context_window_limit:
            usage_str = format_tokens(self._token_usage)
            limit_str = format_tokens(self._context_window_limit)
            token_str = f"{usage_str} / {limit_str} tokens"

            ratio = self._token_usage / self._context_window_limit
            if ratio >= 0.8:
                token_colour = "red"
            elif ratio >= 0.6:
                token_colour = "yellow"
            else:
                token_colour = "green"

        cost_str = f"  [green]${self._session_cost:.4f}[/green]" if self._session_cost > 0 else ""

        self.update(
            f"[{colour}]\u25cf {self._state}[/{colour}]  [bold]{self._agent_name}[/bold]"
            f" ([dim]{self._model}[/dim]){stream_badge}    "
            f"[{token_colour}]{token_str}[/{token_colour}]{cost_str}    "
            f"[dim]ctrl+b: status  ctrl+n: new session  ctrl+s: stream  ctrl+l: logs  ctrl+q: quit[/dim]{hint}"
        )
