"""Standalone CLI entry point for sage-tui."""

from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

import click
from dotenv import load_dotenv


def _setup_logging(verbose: bool = False) -> None:
    """Initialize basic logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s|%(name)s:%(funcName)s:L%(lineno)s|%(levelname)s %(message)s",
    )
    if verbose:
        logging.getLogger("sage").setLevel(logging.DEBUG)


def _load_main_config(config_path: str | None) -> "MainConfig | None":
    """Load main config from a TOML file path."""
    from sage.main_config import load_main_config, resolve_main_config_path

    resolved = resolve_main_config_path(config_path)
    return load_main_config(resolved)


def _resolve_primary_agent(
    main_config: "MainConfig | None",
    config_file_path: Path | None = None,
) -> str:
    """Resolve the primary agent config path from MainConfig."""
    from sage.exceptions import ConfigError

    if main_config is None:
        raise ConfigError(
            "No config.toml found. Provide --agent-config or create a config.toml with a 'primary' field."
        )

    raw_agents_dir = Path(main_config.agents_dir)
    if not raw_agents_dir.is_absolute() and config_file_path is not None:
        agents_dir = (config_file_path.parent / raw_agents_dir).resolve()
    else:
        agents_dir = raw_agents_dir

    if main_config.primary:
        candidate = agents_dir / f"{main_config.primary}.md"
        if candidate.exists():
            return str(candidate)
        candidate = agents_dir / main_config.primary / "AGENTS.md"
        if candidate.exists():
            return str(candidate)
        raise ConfigError(
            f"Primary agent '{main_config.primary}' not found at "
            f"'{agents_dir / (main_config.primary + '.md')}' or "
            f"'{agents_dir / main_config.primary / 'AGENTS.md'}'"
        )

    candidate = agents_dir / "AGENTS.md"
    if candidate.exists():
        return str(candidate)
    raise ConfigError(
        f"No 'primary' set in config.toml and no AGENTS.md found in '{agents_dir}'. "
        "Provide --agent-config or set 'primary' in config.toml."
    )


@click.command()
@click.option(
    "--agent-config",
    "-c",
    "config_path",
    required=False,
    default=None,
    type=click.Path(exists=True),
    help="Path to AGENTS.md or directory containing AGENTS.md (inferred from config.toml if omitted)",
)
@click.option(
    "--config",
    "main_config_path",
    default=None,
    help="Path to main config.toml (also reads SAGE_CONFIG_PATH env var)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging",
)
def main(config_path: str | None, main_config_path: str | None, verbose: bool) -> None:
    """Launch the Sage interactive TUI."""
    load_dotenv()
    _setup_logging(verbose)

    from sage.exceptions import ConfigError
    from sage.main_config import resolve_and_apply_env

    main_config = _load_main_config(main_config_path)
    resolve_and_apply_env(main_config)

    if config_path is None:
        try:
            from sage.main_config import resolve_main_config_path

            resolved_path = resolve_main_config_path(main_config_path)
            config_path = _resolve_primary_agent(main_config, resolved_path)
        except ConfigError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    path = Path(config_path)
    if path.is_dir():
        path = path / "AGENTS.md"

    from sage_tui.app import SageTUIApp

    app = SageTUIApp(config_path=path, central=main_config)
    app.run()
