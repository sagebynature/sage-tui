"""Custom Textual messages for sage-tui event communication."""

from __future__ import annotations

from typing import Any, Literal

from textual.message import Message


class ToolCallStarted(Message):
    """Emitted just before a tool is dispatched."""

    def __init__(self, tool_name: str, arguments: dict[str, Any]) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.arguments = arguments


class ToolCallCompleted(Message):
    """Emitted after a tool dispatch returns."""

    def __init__(self, tool_name: str, result: str) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.result = result


class AgentResponseReady(Message):
    """Emitted when ``agent.run()`` completes successfully."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class AgentError(Message):
    """Emitted when ``agent.run()`` raises an exception."""

    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error


class StreamChunkReceived(Message):
    """Emitted for each text chunk during streaming."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class StreamFinished(Message):
    """Emitted when the streaming response is complete."""

    def __init__(self, full_text: str) -> None:
        super().__init__()
        self.full_text = full_text


class TurnStarted(Message):
    """Emitted when the agent begins a new LLM turn."""

    def __init__(self, turn: int, model: str) -> None:
        super().__init__()
        self.turn = turn
        self.model = model


class DelegationEventStarted(Message):
    """Emitted when the agent delegates to a subagent."""

    def __init__(self, target: str, task: str, category: str | None = None) -> None:
        super().__init__()
        self.target = target
        self.task = task
        self.category = category


class SessionTitleGenerated(Message):
    """Emitted when the background title generation completes."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title


class BackgroundTaskDone(Message):
    """Emitted when a background task completes, fails, or is cancelled."""

    def __init__(
        self,
        task_id: str,
        agent_name: str,
        status: Literal["completed", "failed", "cancelled"],
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

    def __init__(self, plan_name: str, tasks: list[dict[str, Any]]) -> None:
        super().__init__()
        self.plan_name = plan_name
        self.tasks = tasks


class NotepadChanged(Message):
    """Emitted when notepad content on disk has been refreshed."""

    def __init__(self, plan_name: str, content: str) -> None:
        super().__init__()
        self.plan_name = plan_name
        self.content = content
