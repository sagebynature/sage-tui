# Contributing to sage-tui

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- git

## Setup

```bash
git clone <repo-url>
cd sage-tui
make install
```

`make install` syncs dependencies (including dev group) and installs pre-commit hooks
for both pre-commit and commit-msg stages.

> **Note:** The project depends on `sage-agent` as a local editable source
> (`../sage-agent`). Make sure that repo is cloned as a sibling directory.

## Development Workflow

For fast iteration while editing code:

```bash
make test-only     # runs pytest alone
```

Before pushing or opening a PR, run the full suite:

```bash
make test          # sync + lint + format + type-check + pytest
```

Other useful targets:

```
make install     -- sync deps + install pre-commit hooks
make sync        -- uv sync --frozen --group dev
make update      -- uv sync --group dev (unfrozen, updates lockfile)
make lint        -- ruff check with --fix
make format      -- ruff format
make type-check  -- mypy
make clean       -- remove build artifacts
```

## Project Structure

```
sage_tui/
  __init__.py          -- package marker
  cli.py               -- Click CLI entry point
  app.py               -- SageTUIApp main application class
  messages.py          -- Custom Textual Message subclasses
  widgets.py           -- All TUI widget classes
  modals.py            -- Modal screens: permissions, orchestration
  instrumentation.py   -- Agent event hooks, log handler
  helpers.py           -- Utility functions: format_tokens, fmt_args
  app.tcss             -- Textual CSS stylesheet
tests/
  conftest.py          -- Shared fixtures: mock_agent, config_path, widget_app
  test_app.py          -- Widget and integration tests
  test_cli.py          -- CLI entry point tests
```

## Code Style

- **Formatter/linter:** ruff
- **Line length:** 100 characters
- **Target version:** Python 3.10
- **Type checking:** mypy in strict mode

All of these run automatically via pre-commit hooks on each commit. You can also
run them manually:

```bash
make lint          # ruff check --fix
make format        # ruff format
make type-check    # mypy
```

## Testing

Tests use **pytest** with **pytest-asyncio** (`asyncio_mode = "auto"`).

### Running tests

```bash
make test-only                             # all tests
uv run pytest tests/test_app.py -v         # specific file
uv run pytest tests/test_app.py -k "test_name" -v   # specific test
```

### Writing tests

- Async widget tests use Textual's `app.run_test()` pilot pattern.
- Use fixtures from `conftest.py`:
  - `mock_agent` -- a `MagicMock` with `.name`, `.model`, `.skills`, `.subagents` set.
  - `config_path` -- a `tmp_path`-based `AGENTS.md` file.
  - `widget_app` -- factory that wraps one or more widgets in a minimal `App` for testing.
- For modal/screen tests, define an inline `_App` class with a custom `on_mount` that
  pushes the screen under test.
- Coverage: pass `--cov=sage_tui --cov-report=term-missing` to pytest for a coverage report.

### Example: widget test

```python
async def test_my_widget(widget_app):
    app = widget_app(MyWidget())
    async with app.run_test() as pilot:
        assert app.query_one(MyWidget) is not None
```

## Commit Messages

This project enforces [Conventional Commits](https://www.conventionalcommits.org/)
via a pre-commit hook. Every commit message must start with a valid type prefix.

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Allowed types

| Type | Purpose |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code restructuring, no behavior change |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `build` | Build system changes |
| `ci` | CI configuration |
| `chore` | Maintenance tasks |
| `revert` | Revert a previous commit |

### Examples

```
feat(widgets): add token usage display to status bar
fix: handle missing config file gracefully
test: add integration tests for permission modal
docs: update CONTRIBUTING.md with test examples
refactor(app): extract message handler into separate method
```

## Architecture

See `docs/architecture.md` for a deeper look at the application design and
component relationships.
