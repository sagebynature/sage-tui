"""Tests for sage-tui CLI entry point."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner


def test_main_shows_help() -> None:
    from sage_tui.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Launch the Sage interactive TUI" in result.output


def test_main_requires_config_or_config_toml() -> None:
    from sage_tui.cli import main

    runner = CliRunner()
    with patch("sage_tui.cli._load_main_config", return_value=None):
        result = runner.invoke(main, [])
    assert result.exit_code != 0
