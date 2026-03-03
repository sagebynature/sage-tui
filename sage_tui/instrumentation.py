"""Agent event instrumentation, permission wiring, and TUI log forwarding."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, cast

from textual.app import App
from textual.message import Message

from sage.agent import Agent

from sage_tui.messages import (
    BackgroundTaskDone,
    DelegationEventStarted,
    StreamChunkReceived,
    ToolCallCompleted,
    ToolCallStarted,
    TurnStarted,
)

if TYPE_CHECKING:
    from sage_tui.app import SageTUIApp


def instrument_agent(agent: Agent, app: "SageTUIApp") -> None:
    """Subscribe to typed agent events to emit live Textual messages.

    Replaces the former monkey-patching approach with hook subscriptions via
    :meth:`~sage.agent.Agent.on`.  Every tool dispatch fires a
    :class:`ToolCallStarted` / :class:`ToolCallCompleted` pair, each LLM turn
    fires a :class:`TurnStarted` message, and each delegation fires a
    :class:`DelegationEventStarted` message.  Streaming text is delivered via
    :class:`StreamChunkReceived` through the :data:`~sage.hooks.base.HookEvent.ON_LLM_STREAM_DELTA`
    hook so the :meth:`~SageTUIApp._agent_stream` loop can stay clean.
    """
    from sage.events import (
        BackgroundTaskCompleted,
        DelegationStarted,
        LLMStreamDelta,
        LLMTurnStarted,
        ToolCompleted,
        ToolStarted,
    )

    async def on_tool_started(e: ToolStarted) -> None:
        app.post_message(ToolCallStarted(e.name, e.arguments))

    async def on_tool_completed(e: ToolCompleted) -> None:
        app.post_message(ToolCallCompleted(e.name, e.result))

    async def on_stream_delta(e: LLMStreamDelta) -> None:
        app.post_message(StreamChunkReceived(e.delta))

    async def on_turn_started(e: LLMTurnStarted) -> None:
        app.post_message(TurnStarted(e.turn, e.model))

    async def on_delegation_started(e: DelegationStarted) -> None:
        category = getattr(e, "category", None)
        app.post_message(DelegationEventStarted(e.target, e.task, category=category))

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
                status=cast(Literal["completed", "failed", "cancelled"], e.status),
                result=e.result,
                error=e.error,
                duration_s=duration_s,
            )
        )

    agent.on(ToolStarted, on_tool_started)
    agent.on(ToolCompleted, on_tool_completed)
    agent.on(LLMStreamDelta, on_stream_delta)
    agent.on(LLMTurnStarted, on_turn_started)
    agent.on(DelegationStarted, on_delegation_started)
    agent.on(BackgroundTaskCompleted, on_background_task_completed)


def _wire_interactive_permissions(agent: Agent, app: App) -> None:
    """Replace ASK-policy permission handlers with interactive ones on *agent* and all subagents.

    This allows the TUI to prompt the user via a modal dialog when a tool
    requires approval, instead of raising a ``PermissionError``.
    """
    from sage.permissions.interactive import InteractivePermissionHandler
    from sage.permissions.policy import PolicyPermissionHandler

    from sage_tui.modals import PermissionScreen

    async def ask_callback(tool_name: str, arguments: dict[str, Any]) -> bool:
        screen = PermissionScreen(tool_name, arguments)
        return await app.push_screen_wait(screen)

    def _upgrade(target: Agent) -> None:
        handler = target.tool_registry._permission_handler
        if isinstance(handler, PolicyPermissionHandler):
            interactive = InteractivePermissionHandler(
                rules=handler.rules,
                default=handler.default,
                ask_callback=ask_callback,
            )
            target.tool_registry.set_permission_handler(interactive)
        for sub in target.subagents.values():
            _upgrade(sub)

    _upgrade(agent)


class _LogRecord(Message):
    """Carries a logging.LogRecord safely across thread boundaries into Textual."""

    def __init__(self, record: logging.LogRecord) -> None:
        super().__init__()
        self.record = record


class TUILogHandler(logging.Handler):
    """Logging handler that forwards records to the TUI via post_message."""

    def __init__(self, app: App[None]) -> None:
        super().__init__()
        self._app = app

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._app.post_message(_LogRecord(record))
        except Exception:
            pass  # Never let logging raise


_LOG_COLORS: dict[int, str] = {
    logging.DEBUG: "dim",
    logging.INFO: "white",
    logging.WARNING: "yellow",
    logging.ERROR: "red",
    logging.CRITICAL: "bold red",
}
_LOG_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
