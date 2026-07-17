<!--
ADOPTION NOTES (2026-07-16)
- Adoptado como estándar oficial de código Python del proyecto (website + scrapers + proxy).
- Decisión: se UNIFICA todo en Python 3.13 (incluye bumpear el proxy mlb-api, hoy en 3.12).
- Decisión: se ALINEA el proxy existente a estas convenciones (estructura, line 120, tipos),
  apretando `mypy strict` de forma GRADUAL (no de golpe).
- Reconciliaciones pendientes (van en library-guidelines.md):
  * El layout `src/<package>/` aplica a proxy y scrapers; el website Django usa la estructura
    convencional de Django (no src-layout).
  * `mypy strict` + Django/Wagtail requiere `django-stubs` (y drf-stubs si aplica) para no
    ahogarse en falsos positivos.
  * La sección Async aplica a proxy y scrapers; Django/Wagtail es sync-first.
- Requiere Django 5.1+ y Wagtail 6.3+ para Python 3.13 (verificar versiones al implementar).
-->

# Python 3.13 Project Conventions

## Principles

- **Test-first (TDD) is mandatory.** Write the test BEFORE the implementation. Red → Green →
  Refactor: (1) write a failing test that specifies the behavior, (2) write the minimum code to
  pass it, (3) refactor with the test as safety net. **No feature or bugfix code is written
  without a failing test first.**
- **Everything has a test.** No feature, endpoint, view, model method, management command, or bug
  fix ships without a test that covers it. If it's hard to test, the design is wrong — fix the
  design (inject dependencies, keep I/O at the edges), don't skip the test.
- Write code that is obvious to read, not clever to write.
- Every function does one thing. If you need the word "and" to describe it, split it.
- Fail fast, fail loud. No silent swallowing of errors.
- Design for testability: inject dependencies, keep I/O at the edges.
- Do not reinvent the wheel, if there is a well-know Python library, use it.  Update requirements.txt

---

## Style & Structure

- PEP 8 enforced via `ruff`. Max line length: 120. Target: `py313`.
- Naming: No single-letter variable names. Use descriptive names that convey intent (e.g., `result` not `r`, `directory` not `d`).
- Trailing commas in all multi-line structures.
- Absolute imports only. No wildcard imports. No unused imports.
- Remove dead code — no commented-out blocks, no `TODO` without a linked issue.
- Project layout: source in `src/<package>/`, tests in `tests/` mirroring `src`, shared fixtures in `conftest.py`.

---

## Type Hints (Mandatory on all public interfaces)

- Modern 3.13 syntax only: `list[str]`, `X | None`, type aliases, inline generics `def f[T](x: T) -> T:`.
- No legacy imports from `typing` for builtins (`List`, `Dict`, `Optional`, `Tuple`).
- No `from __future__ import annotations` — unnecessary on 3.11+ where modern syntax works natively.
- Use `TypeIs` over `TypeGuard`. Use `TypeVar` defaults where appropriate.
- `# type: ignore` must include error code: `# type: ignore[attr-defined]`.

---

## Functions & Design

- ≤20 lines per function. Return early to reduce nesting. Exceptions require a comment explaining why.
- 3+ parameters → use keyword-only args (`*`). For 2-param functions, use `*` when argument order is non-obvious or types are identical. Exceptions require a comment explaining why.
- Never use mutable defaults (`def f(items=[]):`). Use `None` and assign inside.
- Google-style docstrings on public functions. Don't restate type hints in docstrings.
- Pure functions where possible. Keep I/O and side effects at the boundaries.
- Prefer composition over inheritance. `@dataclass` or Pydantic models for data containers.
- Anything that is common and repetitive across functions should be extracted.

---

## Error Handling & Logging

- Catch specific exceptions only. No bare `except:`. No `except Exception: pass`.
- Chain with `from e` when wrapping. Handle errors at one layer, not multiple.
- `logging` module only, never `print()`. Lazy formatting: `logger.info("user %s", uid)` — no f-strings in log calls.
- Never log secrets, tokens, or credentials. Sanitize before logging.

---

## Async

- `asyncio.run()` as entry point. Never manage loops manually.
- Prefer `TaskGroup` over `gather()`. Be aware: if one task raises, `TaskGroup` cancels all remaining tasks before re-raising — unlike `gather(return_exceptions=True)`, which lets all tasks run to completion. Choose accordingly.
- `asyncio.timeout()` on all network calls.
- `asyncio.to_thread()` for blocking I/O. Never call blocking code inside `async def`.
- Re-raise `CancelledError` after cleanup. Use `except*` for `ExceptionGroup`.

---

## Security & Config

- All secrets via environment variables or `.env`. Never hardcode. Never commit `.env`.
- Validate config at startup with `os.environ["KEY"]` (fails loud) — not deep in call stacks.
- Don't use `assert` for runtime validation — stripped with `-O`. Use `if`/`raise ValueError`.
- `.gitignore`: `.env`, `__pycache__/`, `*.pyc`, `.mypy_cache/`, `.pytest_cache/`, `htmlcov/`, `dist/`.

---

## Testing

- **TDD workflow (non-negotiable):** for every feature/bugfix, first commit (or write) a
  **failing test** that specifies the intended behavior, then implement until it passes, then
  refactor. Reviews/PRs should show the test alongside (or before) the implementation.
- **Arrange → Act → Assert**, separated by blank lines.
- Name: `test_<does_what>_when_<condition>`. Group related tests in classes.
- Mock at boundaries (external services, I/O), never internal implementation.
- `AsyncMock` for async functions. Inject dependencies rather than patching globally.
- `pytest.raises(SpecificError, match="...")` for exception tests.
- `@pytest.mark.parametrize` with `ids=` for multiple cases.
- Test error paths, edge cases, and empty inputs — not just the happy path.
- Don't test stdlib behavior: no tests for plain dataclass constructors, frozen immutability, `StrEnum` values, or type assignments when the model has no custom logic. These models get tested through actual usage in higher-level tests.
- Never use `==` for float comparison — use `pytest.approx()`. Floating point arithmetic is imprecise.
- Shared fixtures in `conftest.py`. Factory fixtures for test data with variations.
- ≥80% meaningful coverage. Don't write tests just to hit a number.
- `asyncio_mode = "auto"` is set globally — do not add `@pytest.mark.asyncio` to individual tests.

---

## Tooling

```toml
[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "ANN", "B", "SIM", "RUF"]
# ANN enforces type annotations on public interfaces.
# UP catches legacy typing imports (List, Dict, Optional, etc.).

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --strict-markers --tb=short --cov=src/ --cov-report=term-missing"
asyncio_mode = "auto"

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
```

---

## Reference

Library-specific patterns and gotchas: see `library-guidelines.md`
