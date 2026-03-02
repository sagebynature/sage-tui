"""Modal screens for sage-tui (permissions, orchestration)."""

from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from sage.agent import Agent
from sage.orchestrator.parallel import Orchestrator


class PermissionScreen(ModalScreen[bool]):
    """Modal asking the user to approve or deny a tool execution."""

    BINDINGS = [
        Binding("y", "approve", "Allow", show=True),
        Binding("n", "deny_action", "Deny", show=True),
        Binding("escape", "deny_action", "Deny"),
    ]

    def __init__(self, tool_name: str, arguments: dict[str, Any]) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.arguments = arguments

    def compose(self) -> ComposeResult:
        detail = self._format_detail()
        with Vertical(id="perm-body"):
            yield Static("[bold yellow]Permission Required[/bold yellow]", id="perm-title")
            yield Static(f"Tool: [bold]{self.tool_name}[/bold]")
            yield Static(f"[dim]{detail}[/dim]", id="perm-detail")
            with Horizontal(id="perm-buttons"):
                yield Button("Allow (y)", id="allow-btn", variant="success")
                yield Button("Deny (n)", id="deny-btn", variant="error")

    def _format_detail(self) -> str:
        for key in ("command", "url", "path", "file_path"):
            if key in self.arguments:
                return f"{key}: {self.arguments[key]}"
        if self.arguments:
            return str(self.arguments)
        return ""

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_deny_action(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#allow-btn")
    def on_allow_pressed(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#deny-btn")
    def on_deny_pressed(self) -> None:
        self.dismiss(False)


class OrchestrationScreen(ModalScreen[None]):
    """Modal for launching parallel subagent orchestration."""

    BINDINGS = [Binding("escape", "close_modal", "Close")]

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self._agent = agent
        self._running = False

    def compose(self) -> ComposeResult:
        agents = list(self._agent.subagents.values())
        with Vertical(id="modal-body"):
            yield Static("[bold]Orchestrate Subagents[/bold]", id="modal-title")
            with Vertical(id="agent-list"):
                for a in agents:
                    yield Static(
                        f"  [green]\u2022[/green] [bold]{a.name}[/bold] ([dim]{a.model}[/dim])"
                    )
            yield Input(
                placeholder="Enter query for all subagents\u2026",
                id="orch-input",
            )
            with Horizontal(id="orch-buttons"):
                yield Button("Run Parallel", id="run-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")
            yield Vertical(id="orch-results")

    def action_close_modal(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#run-btn")
    def on_run_pressed(self) -> None:
        if self._running:
            return
        input_widget = self.query_one("#orch-input", Input)
        query = input_widget.value.strip()
        if not query:
            return
        self._running = True
        input_widget.disabled = True
        self.query_one("#run-btn", Button).disabled = True

        agents = list(self._agent.subagents.values())
        results_container = self.query_one("#orch-results", Vertical)
        for a in agents:
            results_container.mount(
                Static(
                    f"[yellow]\u27f3[/yellow] {a.name}: [dim]running\u2026[/dim]",
                    id=f"orch-result-{a.name}",
                )
            )
        self.run_worker(
            self._run_parallel(agents, query),
            exclusive=True,
            exit_on_error=False,
        )

    async def _run_parallel(self, agents: list[Agent], query: str) -> None:
        results = await Orchestrator.run_parallel(agents, query)
        for result in results:
            safe_id = f"orch-result-{result.agent_name}"
            widget = self.query_one(f"#{safe_id}", Static)
            if result.success:
                preview = (
                    result.output[:80] + "\u2026" if len(result.output) > 80 else result.output
                )
                widget.update(f"[green]\u2713[/green] [bold]{result.agent_name}:[/bold] {preview}")
            else:
                widget.update(
                    f"[red]\u2717[/red] [bold]{result.agent_name}:[/bold] [red]{result.error}[/red]"
                )
