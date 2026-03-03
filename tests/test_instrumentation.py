"""Tests for sage-tui agent instrumentation."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from sage_tui.messages import BackgroundTaskDone, DelegationEventStarted


@pytest.mark.asyncio
async def test_instrument_agent_wires_background_task_completed() -> None:
    from sage_tui.instrumentation import instrument_agent

    mock_app = MagicMock()
    mock_app.post_message = MagicMock()

    mock_agent = MagicMock()
    handlers: dict = {}

    def capture_on(event_class, callback):
        handlers[event_class] = callback

    mock_agent.on.side_effect = capture_on

    # Mock _bg_manager
    from sage.coordination.background import BackgroundTaskInfo

    now = time.time()
    task_info = BackgroundTaskInfo(
        task_id="t1",
        agent_name="executor",
        status="completed",
        created_at=now - 2.0,
        completed_at=now,
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

    # Verify BackgroundTaskDone was posted
    call_args = mock_app.post_message.call_args_list
    bg_messages = [c for c in call_args if isinstance(c.args[0], BackgroundTaskDone)]
    assert len(bg_messages) == 1
    msg = bg_messages[0].args[0]
    assert msg.agent_name == "executor"
    assert msg.status == "completed"
    assert msg.result == "done"
    assert 1.5 <= msg.duration_s <= 2.5
    assert msg.task_id == "t1"


@pytest.mark.asyncio
async def test_instrument_agent_delegation_includes_category() -> None:
    from sage_tui.instrumentation import instrument_agent

    mock_app = MagicMock()
    mock_app.post_message = MagicMock()

    mock_agent = MagicMock()
    mock_agent._bg_manager = MagicMock()
    mock_agent._bg_manager.get = MagicMock(return_value=None)

    handlers: dict = {}

    def capture_on(event_class, callback):
        handlers[event_class] = callback

    mock_agent.on.side_effect = capture_on

    instrument_agent(mock_agent, mock_app)

    from sage.events import DelegationStarted

    # Simulate event with category field
    event = MagicMock(spec=["target", "task", "category"])
    event.target = "coder"
    event.task = "write tests"
    event.category = "quick"

    await handlers[DelegationStarted](event)

    call_args = mock_app.post_message.call_args_list
    deleg_messages = [c for c in call_args if isinstance(c.args[0], DelegationEventStarted)]
    assert len(deleg_messages) == 1
    assert deleg_messages[0].args[0].category == "quick"


@pytest.mark.asyncio
async def test_instrument_agent_delegation_category_defaults_none_when_absent() -> None:
    from sage_tui.instrumentation import instrument_agent

    mock_app = MagicMock()
    mock_app.post_message = MagicMock()

    mock_agent = MagicMock()
    mock_agent._bg_manager = MagicMock()
    mock_agent._bg_manager.get = MagicMock(return_value=None)

    handlers: dict = {}

    def capture_on(event_class, callback):
        handlers[event_class] = callback

    mock_agent.on.side_effect = capture_on

    instrument_agent(mock_agent, mock_app)

    from sage.events import DelegationStarted

    # Simulate event WITHOUT category attribute
    event = MagicMock(spec=["target", "task"])
    event.target = "coder"
    event.task = "write tests"

    await handlers[DelegationStarted](event)

    call_args = mock_app.post_message.call_args_list
    deleg_messages = [c for c in call_args if isinstance(c.args[0], DelegationEventStarted)]
    assert len(deleg_messages) == 1
    assert deleg_messages[0].args[0].category is None
