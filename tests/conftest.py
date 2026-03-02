"""Shared test fixtures for sage-tui."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult


@pytest.fixture
def mock_agent() -> MagicMock:
    """Create a mock Agent with default attributes."""
    agent = MagicMock()
    agent.name = "test"
    agent.model = "gpt-4o"
    agent.skills = []
    agent.subagents = {}
    return agent


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Create a minimal AGENTS.md config file and return its path."""
    cfg = tmp_path / "AGENTS.md"
    cfg.write_text("---\nname: test-agent\nmodel: gpt-4o\n---\nA helpful assistant.\n")
    return cfg


@pytest.fixture
def widget_app():
    """Factory for single-widget test apps."""

    def _make(*widgets):
        class _App(App[None]):
            def compose(self) -> ComposeResult:
                yield from widgets

        return _App()

    return _make
