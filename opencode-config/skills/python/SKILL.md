---
name: python
description: Use when writing, reviewing, refactoring, debugging, or testing Python code, or when setting up a Python project. Covers PEP 8 and PEP 257, Google-style docstrings, comments and regex explanations, naming (functions are verbs), type hints, pytest, uv, pyproject.toml, and ruff. Also use when the user asks about Python style, project layout, or code quality. Treat any change to a .py file, pyproject.toml, or test configuration as Python work, even a one-line fix or a review comment. For PySpark work read [[spark]]; for Polars read [[polars]].
metadata:
  review_after: "2026-11-19"
  docs_url: "https://peps.python.org/pep-0008/"
  version_pinned: "3.12+"
---

# python

Write Python that a teammate can read, test, and change without guessing.

This skill is the default for Python work. It follows PEP 8 and PEP 257, with the house choices used in biocloud-core: 120-character lines, double quotes, Google docstrings, ruff, uv, and pytest. Where a repository already has a clear style, that style wins. Read the project's pyproject.toml and the surrounding code before changing anything.

**Related skills**: [[spark]] for PySpark and Delta Lake, [[polars]] for Polars, [[jupyter-notebook]] for notebooks, [[datacontract]] for data contracts.

## Which dataframe tool

| Situation | Use |
|---|---|
| One machine, local files, including larger-than-memory data via streaming | Polars |
| Large or distributed data, Databricks, Delta Lake | PySpark |
| Existing pandas code | Keep pandas unless asked to migrate; read [[polars]] for the migration path |

Do not write pandas-style code in Polars or Spark. Load the matching skill before writing dataframe code.

## First steps in an existing repository

1. Read pyproject.toml: Python version, dependencies, ruff and pytest settings.
2. Read two or three nearby modules and tests. Match their names, imports, and error style.
3. Run the existing checks before changing code: `uv run ruff check` and `uv run pytest`.
4. Keep the diff focused. Do not reformat unrelated code.

## Project setup with uv and pyproject.toml

Use uv for every Python project. Do not add requirements.txt unless an external tool needs one.

```sh
uv init my-project          # new application
uv init --lib my-library    # new library
cd my-project

uv add httpx                # runtime dependency
uv add --group test pytest  # dependency group
uv remove httpx

uv sync                     # create or update .venv from the lockfile
uv run pytest               # run inside the project environment
uv lock                     # refresh uv.lock after editing pyproject.toml
uv python pin 3.12          # write .python-version
```

- Commit `uv.lock`. Never edit it by hand.
- `uv run` syncs the environment from the lockfile before it runs anything.
- In CI, use `uv sync --locked` so a stale lockfile fails instead of silently resolving.
- Keep project metadata, dependencies, and tool settings in pyproject.toml.

A small pyproject.toml looks like this:

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["httpx"]

[project.scripts]
my-project = "my_project.cli:main"

[dependency-groups]
dev = ["ruff", "ty"]
test = ["pytest", "pytest-cov"]

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
strict = true  # pytest 9+
addopts = ["-v", "--import-mode=importlib"]
```

Use a src layout for new libraries. It stops the working directory from shadowing the installed package.

```
my-library/
├── pyproject.toml
├── uv.lock
├── src/
│   └── my_library/
│       └── __init__.py
└── tests/
    └── test_my_library.py
```

For an application, a flat package next to tests is fine. Match the layout the repository already uses.

## Naming

Functions and methods are verbs. A name should say what the function does, not what it receives.

| Avoid | Prefer |
|---|---|
| `process_data` | `clean_orders` |
| `data_loader` | `load_orders` |
| `handle_error` | `raise_for_missing_key` |
| `user_list` for a function | `list_users` |
| `flag`, `value`, `tmp` | `is_active`, `parsed_contract`, `raw_rows` |
| `x`, `df1`, `data` | `orders`, `raw_orders`, `validated_orders` |

More rules:

- Predicates read as questions: `is_active`, `has_children`, `can_retry`.
- Variables are nouns. Collections are plural: `orders`, `column_names`.
- Constants are UPPER_SNAKE_CASE at module level.
- Classes are CapWords. Exception classes end in `Error`.
- Private helpers start with one underscore.
- Avoid vague verbs: `process`, `handle`, `manage`, `do`, `run` on their own.
- Keep established short names such as `df`, `id`, `url`, `config`, and `db`.
- Match the surrounding code if it is consistent. Do not rename public names without checking callers.

## Layout and formatting

- Four spaces per indent. No tabs.
- 120 characters per line in this house. PEP 8 uses 79 and allows teams to agree on up to 99, so 120 is a deliberate local choice. The repository's ruff setting is the final word.
- Double quotes. Ruff format handles this.
- Two blank lines between top-level definitions, one between methods.
- Group imports: standard library, third-party, local. One blank line between groups.
- Use absolute imports. Avoid wildcard imports.
- Put a trailing comma in multiline calls and collections. It keeps diffs small.
- Wrap long expressions in parentheses. Do not use backslashes.
- Use `pathlib.Path` instead of string paths and `os.path`.
- Use `enumerate` instead of `range(len(items))`.
- Use `zip(left, right, strict=True)` when the lengths must match.
- Use f-strings for messages that are built at runtime, except log calls, which use lazy `%s` formatting.
- Use `is None` and `is not None`, never `== None`.
- Use `if not items:` for empty sequences.
- Do not compare booleans to `True` or `False`.
- Do not use mutable default arguments. Use `None` and create the value inside.

## Comprehensions and conditional expressions

Prefer a comprehension when the body is a single expression and the result is the point:

```python
# Prefer
active_names = [user.name for user in users if user.active]
totals = {region: sum(order.amount for order in orders) for region, orders in grouped.items()}

# Over
active_names = []
for user in users:
    if user.active:
        active_names.append(user.name)
```

- Use a list, set, or dict comprehension for one expression with at most one `if` filter.
- Use a plain loop when the body has side effects, more than one statement, exception handling, or nested logic.
- Never call a function for its side effects inside a comprehension. `[save(item) for item in items]` hides the loop; write the loop.
- Do not nest comprehensions. Extract a helper function instead.
- Prefer a comprehension to `map`/`filter` with a lambda, and use a generator expression inside `any`, `all`, `sum`, `min`, `max`, and `join`.

A conditional expression chooses a value. It does not control which action runs:

```python
label = "paid" if order.is_paid else "unpaid"
```

- Keep the condition simple. If a branch needs an explanation, use an `if` block.
- Do not use a conditional expression for side effects (`send() if ready else None`).
- Do not put a compound statement on one line (`if ready: send()`). Put the body on its own line.

## Type hints

Annotate public function arguments and return values. Annotate private helpers when the types are not obvious.

```python
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Order:
    order_id: str
    created_at: datetime
    is_paid: bool


def total_amount(orders: Iterable[Order]) -> float:
    ...
```

- Use built-in generics: `list[str]`, `dict[str, int]`, `tuple[str, ...]`.
- Use `str | None`, not `Optional[str]`.
- Avoid `Any`. If a value really can be anything, use `object` and narrow it.
- Use `Protocol` when several classes share behaviour.
- Use `TYPE_CHECKING` for imports that would create a cycle.
- Keep type hints in the signature. Do not repeat them in the docstring.
- Run `uv run ty check` in CI. If the repository uses mypy or pyright, use that instead.
- For a library, add an empty `py.typed` marker and declare the public API with `__all__`. Skip `py.typed` for applications.

## Docstrings

Write a docstring for every public module, class, and function. Write one for a private helper when its purpose is not obvious.

Use Google style, but keep it compact. The docstring should help a reader use the code, not repeat the code.

Rules:

- The first line is a summary in the imperative mood, ending with a period: "Return the open orders." not "Returns the open orders."
- Leave one blank line after the summary.
- Add only the sections that carry information: `Args`, `Returns`, `Raises`, `Yields`, `Attributes`.
- Do not put types in `Args` when the signature already has annotations.
- Do not restate the signature or narrate obvious steps.
- Use short, plain English sentences.
- **Do not use backticks anywhere inside a docstring.** No Markdown, no Sphinx roles, no `:param:`. Write names plainly.
- Keep the description to a few lines. If a function needs a page of explanation, split it or write a design note.
- Describe why, constraints, side effects, and surprising behaviour. Those are the parts a reader cannot get from the code.
- Module docstrings: one to three sentences on what the module is for.
- Class docstrings: what the class represents, plus public attributes.

Good:

```python
def count_unpaid_orders(orders: list[Order]) -> int:
    """Count orders that are not paid.

    Args:
        orders: Orders to inspect.

    Returns:
        Number of orders with is_paid set to False.
    """
    return sum(1 for order in orders if not order.is_paid)
```

Too long and too vague:

```python
def process_data(data):
    """This function processes the data.

    This function is responsible for processing the data that comes in from
    the various sources. It first checks the data, then cleans the data, then
    transforms the data, and finally returns the data. The data can be in
    several formats and the function tries to handle all of them.
    """
```

The second docstring says nothing a reader can use. Split the function instead.

## Comments and regex

Comments explain why. The code already explains what.

- Write complete sentences. Capitalise the first word and end with a period.
- Explain constraints, data quirks, workarounds, and decisions a reader cannot see.
- Keep the comment next to the code it describes.
- **Never delete an existing comment just because it looks redundant.** If the code it describes is still there, keep it. If it is stale, update it in the same change. If you are unsure, keep it and mention it.
- **Do not add comments that describe the old implementation.** Do not write "this used to be X" or "the old version did Y". The one exception is an active POC or migration where both paths exist and the comparison helps a reviewer. Remove those notes when the migration ends.
- Do not keep commented-out code. Git remembers it.
- Use `# TODO(owner): reason` for deferred work. Name the owner when you know it.

Every regular expression gets one comment line directly above it that says what it matches. Add an example if that helps.

```python
# Match a Dutch postcode: four digits, an optional space, two capital letters.
POSTCODE_PATTERN = re.compile(r"^\d{4}\s?[A-Z]{2}$")

# Match an ISO date such as 2026-10-19.
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
```

Do not explain every token. One line is enough. If the pattern is genuinely complex, put the longer explanation in the function docstring or a design note, but keep the one-line comment.

## Functions and modules

- One job per function. If the name needs "and", split it.
- Aim for 70 lines per function and 300 lines per module. Treat these as smoke alarms, not laws.
- Prefer early returns over deep nesting.
- Keep functions pure where you can. Pass dependencies in instead of reaching for globals.
- Avoid mutable global state. Module-level constants are fine.
- Replace magic numbers and strings with named constants.
- Use a module logger: `logger = logging.getLogger(__name__)`.
- Use lazy logging: `logger.info("Loaded %s rows", row_count)`, not an f-string. The logging call may be filtered out before the message is built.
- Never use `print` in library code. Use logging. A CLI entry point may print its final output.
- Raise specific exceptions. Use `raise ... from error` when you replace an exception.
- Do not use a bare `except:`. Catch the exceptions you can handle.
- Do not use `assert` for runtime validation. Assertions can be removed with `python -O`. Use an explicit `if` and raise.
- Use `with` for files, connections, locks, and other resources.
- Give a script a `main()` function and an `if __name__ == "__main__":` guard.
- Use timezone-aware datetimes: `datetime.now(UTC)`, not `datetime.utcnow()`.
- Use `enum.StrEnum` for a fixed set of string values.
- Use `dataclass(frozen=True)` for small value objects.

## Tests with pytest

- Put tests in `tests/` and mirror the package layout, unless the repository puts them next to the source.
- Name files `test_*.py` and functions `test_*`.
- Name a test after the behaviour, not the function: `test_rejects_expired_token`, not `test_validate_1`.
- Use arrange, act, assert. Put a blank line between the three parts.
- Test one behaviour per test. Several asserts are fine when they check the same behaviour.
- Use `pytest.mark.parametrize` for table-driven cases.
- Use fixtures for shared setup, `tmp_path` for files, and `monkeypatch` for environment variables.
- Mock at the boundary: network, database, clock, filesystem. Do not mock the function you are testing.
- Use `pytest.raises(ValueError, match="...")` to check both the exception type and the message.
- Do not use `sleep`. Freeze time with time-machine or freezegun.
- Mark tests with `unit`, `integration`, `slow`, or `contract`. For new projects, turn on strict mode (`strict = true`, pytest 9+): unknown markers, unknown config keys, bad parametrization IDs, and unexpected xpasses then fail.
- Use `--import-mode=importlib` for new projects. It avoids sys.path surprises.
- Coverage is a guide, not a target. Keep branch coverage on (`--cov-branch`) and raise `fail_under` over time instead of leaving it at a low number forever.
- Do not test private helpers through the public API when a direct test is clearer.

```python
import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-19", True),
        ("19-10-2026", False),
        ("", False),
    ],
)
def test_is_iso_date(value: str, expected: bool) -> None:
    assert is_iso_date(value) is expected
```

Run tests with `uv run pytest`. Run one file with `uv run pytest tests/test_dates.py`.

## Linting and quality gates

Use ruff for both linting and formatting. Do not hand-format code that ruff can format.

```sh
uv run ruff check --fix
uv run ruff format
uv run ty check
uv run pytest
```

A sensible ruff configuration starts with `E`, `F`, `I`, `B`, `UP`, `SIM`, `PT`, and `D` (Google convention). Add these in stages when the codebase is ready: `RUF`, `C4`, `RET`, `PTH`, `ARG`. Turning on every rule at once creates a large, low-value diff.

- `D` checks docstrings. Set `lint.pydocstyle.convention = "google"`.
- `RUF` catches ruff-specific mistakes.
- `C4` simplifies comprehensions.
- `RET` simplifies returns.
- `PTH` prefers pathlib.
- `ARG` finds unused arguments.
- Add `S` selectively for security checks. Do not silence a rule without a comment that says why.

Use prek for pre-commit hooks: ruff check, ruff format, `uv lock`, and the test suite. In CI, run lint, format check, type check, and tests in that order.

Add `pip-audit` if dependency security scanning is wanted. Keep the lockfile in the scan so the report matches what you deploy.

## Editing existing code

- Read the file before changing it. Look for comments that explain a workaround.
- Keep existing comments unless the code they describe is gone. Update a stale comment in the same change.
- Do not delete a comment because it is not needed for the new code. If it is still true, it stays.
- Do not add a comment that compares the new code to the old code, except during an active POC or migration.
- Do not reformat unrelated code. It hides the real change in review.
- Check callers before renaming a public function, class, or module.
- If the file already has a consistent style that differs from this skill, follow the file. Propose a separate cleanup instead of mixing it into the current change.

## Review checklist

- [ ] The code runs on the project's Python version and uses uv.
- [ ] `uv run ruff check` and `uv run ruff format --check` pass.
- [ ] `uv run ty check` passes, or the project's type checker does.
- [ ] `uv run pytest` passes.
- [ ] Public functions have compact Google docstrings.
- [ ] No docstring contains backticks.
- [ ] Function names are verbs; predicates read as questions.
- [ ] Simple accumulator loops are comprehensions; complex ones are still loops.
- [ ] Conditional expressions choose a value, not an action.
- [ ] Every regex has a one-line comment that says what it matches.
- [ ] Existing comments are preserved, and stale ones are updated.
- [ ] No old-implementation comments and no commented-out code.
- [ ] New behaviour has a test named after the behaviour.
- [ ] Logging uses lazy formatting; library code does not use print.
- [ ] No secrets, tokens, or machine-specific paths are in the code.

## Sources

- PEP 8: https://peps.python.org/pep-0008/
- PEP 257: https://peps.python.org/pep-0257/
- Google Python Style Guide: https://google.github.io/styleguide/pyguide.html
- uv projects: https://docs.astral.sh/uv/guides/projects/
- pytest good practices: https://docs.pytest.org/en/stable/explanation/goodpractices.html
- ruff: https://docs.astral.sh/ruff/
- ty: https://docs.astral.sh/ty/
- prek: https://github.com/j178/prek
- pip-audit: https://pypi.org/project/pip-audit/
- Palantir PySpark style guide: https://github.com/palantir/pyspark-style-guide
