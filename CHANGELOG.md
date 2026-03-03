# CHANGELOG

<!-- version list -->

## v1.1.0 (2026-03-03)

### Bug Fixes

- Add task_id assertion and tighten duration bounds in instrumentation test
  ([`20708de`](https://github.com/sagebynature/sage-tui/commit/20708de012eee4ea3d7947256e78d467c41ee591))

- Cast BackgroundTaskCompleted.status to Literal for type safety
  ([`76f5277`](https://github.com/sagebynature/sage-tui/commit/76f52770672f5edabf050cca2b926cf7c7fda949))

- Improve test name accuracy and docstring consistency in Task 2
  ([`31560d8`](https://github.com/sagebynature/sage-tui/commit/31560d843c5f3df694713b353fd3527940003cd2))

- Tighten type annotations and add docstring in messages
  ([`3781eeb`](https://github.com/sagebynature/sage-tui/commit/3781eeb8c1e97284fab2b59ca07c30819abd7d55))

- Use explicit is not None guard for category in delegation handler
  ([`1a273b5`](https://github.com/sagebynature/sage-tui/commit/1a273b5f95e6aba42621d6cbe52a8a70d62ac3b9))

### Chores

- Update dependencies to latest versions in pyproject.toml and uv.lock; minor formatting adjustments
  in app.py and widgets.py
  ([`75edd2b`](https://github.com/sagebynature/sage-tui/commit/75edd2b3cbfd24ac77b19b63f8af0f62d552d786))

- Update type-checking tool and dependencies
  ([`3e5abfe`](https://github.com/sagebynature/sage-tui/commit/3e5abfe5e6a43f1eff9e78474cf416ba4d37171c))

### Documentation

- Add design doc for background tasks, planning, notepad, category routing
  ([`1f08d82`](https://github.com/sagebynature/sage-tui/commit/1f08d827d0409772e0fa02b96b5ecbc48278fb02))

- Add implementation plan for background tasks, planning, notepad, category routing
  ([`2b8e04b`](https://github.com/sagebynature/sage-tui/commit/2b8e04b49d600e3c382cbb49f2afca54e9806cfd))

### Features

- Add background task, plan, notepad, and category routing handlers in app
  ([`7dd33c0`](https://github.com/sagebynature/sage-tui/commit/7dd33c0856cd564d0d4e8097498197180265ff80))

- Add BackgroundTaskDone, PlanStateChanged, NotepadChanged messages; extend DelegationEventStarted
  with category
  ([`0bcf0bf`](https://github.com/sagebynature/sage-tui/commit/0bcf0bf912db26da34981b77cec0825af5d955e5))

- Add BackgroundTaskEntry widget and ChatPanel.add_background_task
  ([`5bdb3a0`](https://github.com/sagebynature/sage-tui/commit/5bdb3a0cc0637c789fd2176706f68a80cf85abb2))

- Add category badge to StatusBar
  ([`c4a1deb`](https://github.com/sagebynature/sage-tui/commit/c4a1debd294bc3e2a776a0cd4ab6a0934788173f))

- Add PLAN and NOTEPAD sections to StatusPanel; extend set_active_delegation with category
  ([`0b8751c`](https://github.com/sagebynature/sage-tui/commit/0b8751cac4cbdce676bbe4652e51475f24b33978))

- Force scroll to bottom when assistant turn ends
  ([`7d885ee`](https://github.com/sagebynature/sage-tui/commit/7d885ee59e0a54ad7abf28255a065b5cb0a77c67))

- Wire BackgroundTaskCompleted event; pass category through delegation instrumentation
  ([`4f6ad26`](https://github.com/sagebynature/sage-tui/commit/4f6ad266d129c5dd69ebe2b99c4ec5faa15ff151))


## v1.0.0 (2026-03-03)

- Initial Release
