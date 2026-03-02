"""Interactive Textual TUI for Sage.

Provides the ``SageTUIApp`` class launched by ``sage-tui --config=<path>``.
The app offers a split-screen layout:

- **Chat panel** (left, flexible): conversation history with inline collapsible tool calls and message input.
- **Status panel** (right, fixed 40 cols): agent info, skills, token usage, context window, and active agents.
- **Log panel** (bottom, hidden): togglable log viewer (ctrl+l).
- **Status bar** (bottom): agent name, model, current state, keyboard hints.

Tool-call and LLM-turn visibility is achieved by subscribing to the typed
agent event system via :meth:`~sage.agent.Agent.on`.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from sage.main_config import MainConfig

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal

from sage.agent import Agent

from sage_tui.helpers import format_tokens
from sage_tui.instrumentation import (
    TUILogHandler,
    _LogRecord,
    _wire_interactive_permissions,
    instrument_agent,
)
from sage_tui.messages import (
    AgentError,
    AgentResponseReady,
    DelegationEventStarted,
    SessionTitleGenerated,
    StreamChunkReceived,
    StreamFinished,
    ToolCallCompleted,
    ToolCallStarted,
    TurnStarted,
)
from sage_tui.modals import OrchestrationScreen, PermissionScreen
from sage_tui.widgets import (
    AssistantEntry,
    ChatPanel,
    HistoryInput,
    LogPanel,
    StatusBar,
    StatusPanel,
    ThinkingEntry,
    ToolEntry,
    UserEntry,
)

logger = logging.getLogger(__name__)


class SageTUIApp(App[None]):
    """Interactive split-screen TUI for a Sage agent config."""

    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+b", "toggle_status", "Status panel"),
        Binding("ctrl+l", "toggle_logs", "Logs"),
        Binding("ctrl+n", "clear_chat", "New session"),
        Binding("ctrl+o", "orchestrate", "Orchestrate"),
        Binding("ctrl+s", "toggle_stream", "Toggle stream"),
    ]

    TITLE = "Sage TUI"

    def __init__(self, config_path: Path, central: "MainConfig | None" = None) -> None:
        super().__init__()
        self.config_path = config_path
        self._central = central
        self._agent: Agent | None = None
        self._streaming_mode: bool = True
        self._current_response: AssistantEntry | None = None
        self._pending_tools: dict[str, list[ToolEntry]] = {}
        self._had_tool_calls_in_turn: bool = False
        self._log_handler: TUILogHandler | None = None
        self._sage_logger_level: int = logging.NOTSET
        self._sage_logger_propagate: bool = True
        self._session_id: str = uuid4().hex
        self._session_title: str = ""
        self._title_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            yield ChatPanel(id="chat-panel")
            yield StatusPanel(id="status-panel")
        yield LogPanel(id="log-panel")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self._log_handler = TUILogHandler(self)
        self._log_handler.setLevel(logging.DEBUG)
        # Attach to the sage logger (not root) so only sage.* records appear.
        # Disable propagation while the TUI is running: logging.conf installs a
        # StreamHandler on the root logger that writes to stderr, which Textual
        # renders as raw terminal text (the "log flash"). With propagate=False,
        # records are handled only by our TUILogHandler and never reach stderr.
        sage_logger = logging.getLogger("sage")
        self._sage_logger_level = sage_logger.level
        self._sage_logger_propagate = sage_logger.propagate
        sage_logger.setLevel(logging.DEBUG)
        sage_logger.propagate = False
        sage_logger.addHandler(self._log_handler)

        agent = Agent.from_config(self.config_path, central=self._central)
        _wire_interactive_permissions(agent, self)
        self._agent = agent
        instrument_agent(agent, self)

        self.query_one(StatusPanel).initialize(agent)
        self.query_one(StatusPanel).set_session(self._session_id, self._session_title)
        self._set_status("Ready")
        self.sub_title = f"{agent.name} ({agent.model})"
        self.query_one("#chat-input", HistoryInput).focus()

    async def on_unmount(self) -> None:
        if self._log_handler is not None:
            sage_logger = logging.getLogger("sage")
            sage_logger.removeHandler(self._log_handler)
            sage_logger.setLevel(self._sage_logger_level)
            sage_logger.propagate = self._sage_logger_propagate
        if self._agent is not None:
            await self._agent.close()

    # -- Status / title helpers ------------------------------------------------

    def _set_status(self, state: str = "Ready") -> None:
        """Update the status bar with current agent info."""
        if self._agent:
            self.query_one(StatusBar).set_state(
                state,
                self._agent.name,
                self._agent.model,
                bool(self._agent.subagents),
                streaming_mode=self._streaming_mode,
            )

    def _cancel_title_task(self) -> None:
        """Cancel any in-flight background title generation."""
        if self._title_task and not self._title_task.done():
            self._title_task.cancel()
            self._title_task = None

    # -- Log record handler ----------------------------------------------------

    def on__log_record(self, event: _LogRecord) -> None:
        self.query_one(LogPanel).write_record(event.record)

    # -- Input handling --------------------------------------------------------

    @on(HistoryInput.Submitted, "#chat-input")
    def handle_chat_input(self, event: HistoryInput.Submitted) -> None:
        query = event.value.strip()
        if not query or self._agent is None:
            return
        input_widget = self.query_one("#chat-input", HistoryInput)
        input_widget.append_history(query)
        input_widget.clear()
        input_widget.disabled = True

        # Cancel any in-flight title generation to avoid concurrent LLM calls
        self._cancel_title_task()

        chat = self.query_one(ChatPanel)
        chat.append_user_message(query)
        chat.start_turn()

        self._pending_tools.clear()
        self._current_response = None
        self._had_tool_calls_in_turn = False

        if self._streaming_mode:
            self._set_status("Streaming\u2026")
            self.run_worker(self._agent_stream(query), exclusive=True, exit_on_error=False)
        else:
            self._set_status("Thinking\u2026")
            self.run_worker(self._agent_run(query), exclusive=True, exit_on_error=False)

    async def _agent_run(self, query: str) -> None:
        if self._agent is None:
            return
        try:
            result = await self._agent.run(query)
            self.post_message(AgentResponseReady(result))
        except Exception as exc:
            logger.exception("Agent run failed")
            self.post_message(AgentError(str(exc)))

    async def _agent_stream(self, query: str) -> None:
        if self._agent is None:
            return
        try:
            full_text = ""
            async for chunk in self._agent.stream(query):
                full_text += chunk
            self.post_message(StreamFinished(full_text))
        except Exception as exc:
            logger.exception("Agent stream failed")
            self.post_message(AgentError(str(exc)))

    # -- Message handlers ------------------------------------------------------

    def on_tool_call_started(self, event: ToolCallStarted) -> None:
        # Close the current AssistantEntry so any post-tool text creates a new
        # one *after* the ToolEntry, preventing text from sandwiching the tool.
        self._current_response = None
        self._had_tool_calls_in_turn = True
        chat = self.query_one(ChatPanel)
        entry = chat.add_tool_call(event.tool_name, event.arguments)
        self._pending_tools.setdefault(event.tool_name, []).append(entry)

    def on_tool_call_completed(self, event: ToolCallCompleted) -> None:
        queue = self._pending_tools.get(event.tool_name)
        if queue:
            entry = queue.pop(0)
            entry.set_result(event.result)

    def on_turn_started(self, event: TurnStarted) -> None:
        self._set_status("Streaming\u2026" if self._streaming_mode else "Thinking\u2026")

    def on_delegation_event_started(self, event: DelegationEventStarted) -> None:
        self.query_one(StatusPanel).set_active_delegation(event.target, event.task)

    def on_stream_chunk_received(self, event: StreamChunkReceived) -> None:
        chat = self.query_one(ChatPanel)
        if self._current_response is None:
            self._current_response = chat.start_response()
        self._current_response.append_chunk(event.text)
        chat.scroll_to_end()

    def on_stream_finished(self, event: StreamFinished) -> None:
        if self._current_response is None and not self._had_tool_calls_in_turn:
            # Fallback: no StreamChunkReceived arrived (e.g. tool-only turn with
            # no text output).  full_text holds everything so use it directly.
            if event.full_text:
                entry = self.query_one(ChatPanel).start_response()
                entry.set_text(event.full_text)
        self._current_response = None
        self._finish_turn()

    def on_agent_response_ready(self, event: AgentResponseReady) -> None:
        entry = self.query_one(ChatPanel).start_response()
        entry.set_text(event.text)
        self._finish_turn()

    def on_agent_error(self, event: AgentError) -> None:
        entry = self.query_one(ChatPanel).start_response()
        entry.set_text(f"[Error] {event.error}")
        self._current_response = None
        self._set_status("Error")
        self._re_enable_input()

    def on_session_title_generated(self, event: SessionTitleGenerated) -> None:
        self.query_one(StatusPanel).update_session_title(event.title)

    # -- Actions ---------------------------------------------------------------

    def action_toggle_status(self) -> None:
        panel = self.query_one(StatusPanel)
        panel.display = not panel.display

    def action_toggle_logs(self) -> None:
        self.query_one(LogPanel).toggle_visibility()

    def action_clear_chat(self) -> None:
        self.query_one(ChatPanel).clear_entries()
        # Cancel in-flight title generation
        self._cancel_title_task()
        # Start a fresh session
        self._session_id = uuid4().hex
        self._session_title = ""
        if self._agent:
            self._agent.reset_session()
        status_panel = self.query_one(StatusPanel)
        status_panel.set_session(self._session_id, self._session_title)
        status_panel.update_stats({})
        self.query_one(StatusBar).update_token_usage(0, None)
        self.query_one(StatusBar).update_session_cost(0.0)

    def action_orchestrate(self) -> None:
        if self._agent and self._agent.subagents:
            self.push_screen(OrchestrationScreen(self._agent))

    def action_toggle_stream(self) -> None:
        self._streaming_mode = not self._streaming_mode
        mode_label = "streaming" if self._streaming_mode else "batch"
        self.query_one(ChatPanel).append_user_message(
            f"[dim]\u2699 Switched to {mode_label} mode[/dim]"
        )
        self._set_status("Ready")

    # -- Private helpers -------------------------------------------------------

    def _finish_turn(self) -> None:
        self.query_one(StatusPanel).clear_active_delegation()
        if self._agent:
            stats = self._agent.get_usage_stats()
            self.query_one(StatusPanel).update_stats(stats)
            self._set_status("Ready")
            token_usage = stats.get("token_usage") or 0
            limit = stats.get("context_window_limit")
            self.query_one(StatusBar).update_token_usage(
                int(token_usage), int(limit) if limit else None
            )
            cost = stats.get("cumulative_cost") or 0.0
            self.query_one(StatusBar).update_session_cost(float(cost))
            if stats.get("compacted_this_turn"):
                self.query_one(ChatPanel).append_user_message("[dim]\u26a1 Context compacted[/dim]")
                self._schedule_title_generation("")  # re-derive from history
            elif not self._session_title:
                self._schedule_title_generation("")  # generate from first user message
        self._re_enable_input()

    def _re_enable_input(self) -> None:
        inp = self.query_one("#chat-input", HistoryInput)
        inp.disabled = False
        inp.focus()

    async def _generate_session_title(self, context: str) -> None:
        """Generate a session title from context using the agent's provider."""
        if self._agent is None:
            return
        if not context:
            # Derive context from conversation history
            for msg in reversed(self._agent._conversation_history):
                if msg.role == "user" and msg.content:
                    context = msg.content
                    break
        if not context:
            return
        try:
            from sage.models import Message as SageMessage

            snippet = context[:500]
            result = await self._agent.provider.complete(
                [
                    SageMessage(
                        role="system",
                        content=(
                            "Your ONLY job is to generate a short title. "
                            "Given a user's message to an AI coding assistant, "
                            "produce a concise title (max 50 chars, single line) "
                            "that captures the user's intent or goal.\n\n"
                            f'The user said: """{snippet}"""\n\n'
                            "Respond with ONLY the title. No quotes, no explanation, "
                            "no punctuation at the end."
                        ),
                    ),
                    SageMessage(role="user", content="Generate the title."),
                ]
            )
            title = (result.message.content or "").strip()[:50]
            if title:
                self._session_title = title
                self.post_message(SessionTitleGenerated(title))
        except Exception:
            logger.debug("Session title generation failed", exc_info=True)

    def _schedule_title_generation(self, context: str) -> None:
        """Fire-and-forget background title generation."""
        self._title_task = asyncio.create_task(self._generate_session_title(context))


# Re-export widget/message classes so existing imports from sage_tui.app keep working.
__all__ = [
    "SageTUIApp",
    "AssistantEntry",
    "ChatPanel",
    "HistoryInput",
    "LogPanel",
    "PermissionScreen",
    "StatusBar",
    "StatusPanel",
    "ThinkingEntry",
    "ToolEntry",
    "TUILogHandler",
    "UserEntry",
    "format_tokens",
]
