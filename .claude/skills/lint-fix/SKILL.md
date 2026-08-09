---
name: lint-fix
description: Run and fix Python lint/format/type-check issues in this repo (ruff + mypy). Use when asked to lint, format, type-check, clean up Python, make the linters pass, or before committing backend changes. Python/backend only — the frontend uses oxlint separately.
version: 0.1.0
---

# Lint & type-check this repo (ruff + mypy)

The playbook for making the Python code clean. The linters are deterministic
tools; **your job is to run them and fix what `--fix` can't** — that's the part
that needs judgment. Config lives in `pyproject.toml` (`[tool.ruff]`,
`[tool.mypy]`); the gate is `.pre-commit-config.yaml` + `Makefile`.

## Commands

Tools live in the project venv, which is usually **not** activated in a fresh
shell — call them by path (or activate the venv / use `make` if it is active):

```bash
venv/bin/ruff format src tests        # auto-format (writes changes)
venv/bin/ruff check --fix src tests   # lint + autofix
venv/bin/ruff check src tests         # remaining lint (nothing auto-fixed it)
venv/bin/mypy src                     # type-check
venv/bin/pytest -q                    # confirm behavior after any code fix
```

Equivalents once the venv is active: `make format`, `make lint`, `make lint-check`,
`make typecheck`, `make test`, or `make check` (everything CI runs).

## How to fix, in order

1. **Format first** (`ruff format`) — resolves whitespace/wrapping so lint noise
   drops. The very first repo-wide format pass should be its **own commit**,
   separate from any logic change.
2. **Autofix lint** (`ruff check --fix`) — clears imports ordering, `UP`
   modernizations, etc.
3. **Fix remaining lint by hand** — read each finding, open the file, fix the
   *real cause*. Do **not** blanket-silence with `# noqa`; if a suppression is
   truly warranted, use a specific code with a reason: `# noqa: E741  # ...`.
4. **Fix mypy errors by hand** — fix the actual type issue (e.g. narrow a type,
   construct a proper `tuple[str, str]` instead of `tuple[str, ...]`). Only use
   `# type: ignore[code]` when genuinely unavoidable, always with the specific
   code and a one-line reason. Prefer fixing the code over loosening config.
5. **Re-run until clean, then run the tests** (`pytest -q`) — any code change to
   satisfy a linter must keep the 142 tests green.

## Repo-specific conventions (do not fight these)

- **FastAPI `Depends()` / `Query()` in argument defaults are intentional.** B008
  is configured to allow them (`[tool.ruff.lint.flake8-bugbear]
  extend-immutable-calls`). Never rewrite routes/`deps.py` to avoid B008 — add
  the callable to that allow-list instead if a new FastAPI default helper appears.
- **Gradual mypy.** Config is deliberately lenient: `check_untyped_defs = true`,
  `disable_error_code = ["import-untyped"]` (pandas/PyYAML/yfinance/pyvis have no
  stubs here). Don't crank strictness to clear a single error. Ratcheting up
  (`disallow_untyped_defs`, then `disallow_any_generics`, or adding
  `pandas-stubs`) is a deliberate, separate step — see production-roadmap.md §4.6.
- **Comment-light house style** (CLAUDE.md). Never add docstrings or comments
  solely to satisfy a linter; there is no docstring linter for this reason.
- **`E501` (line length) is off** — the formatter owns wrapping. Don't hand-wrap
  lines to chase a length limit.
- **Domain rules are not lint's business.** When fixing a lint/type issue inside
  analysis/graph code, preserve behavior exactly (log-returns, inner-join-on-date
  alignment, the correlation math). Fixing types must not change results.

## Guardrails

- Fix the code, not the config — the only config changes that are OK are for
  genuine false positives (like B008), and they must be documented with a comment.
- mypy is not in the pre-commit hook yet (it's in `make typecheck` / CI). Run it
  explicitly here; keeping `make typecheck` green is what will let it join the
  commit gate later.
- Scope: `src` (and `tests` for ruff). This skill is Python only — the frontend
  is linted with `oxlint` from `frontend/`, out of scope here.
