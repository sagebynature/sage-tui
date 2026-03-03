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
