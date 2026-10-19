---
name: polars
description: Use when writing, reviewing, debugging, or optimising Polars code, or when a task involves loading, querying, transforming, aggregating, joining, or analysing tabular data (CSV, Parquet, NDJSON, or DataFrames). Covers the lazy API, expressions, window functions, group-bys, joins, the streaming engine (the 2.0 default, including larger-than-memory data), pandas-to-Polars migration, and DataFrame display styling. Applies even when the user does not say Polars, including data questions phrased as "which/top/how many" and requests to clean or combine CSV, Parquet, or NDJSON files. It is the default for single-machine Python data work when no dataframe library is specified. Not for Polars Cloud, On-Prem, distributed, or GPU workloads. For Spark or Databricks work read [[spark]]; for general Python style read [[python]].
license: MIT
metadata:
  author: Polars
  homepage: https://pola.rs
  review_after: "2026-11-19"
  docs_url: "https://docs.pola.rs/"
  upstream_version: "0.3.1"
  upstream_commit: "70bec73cd09722411492dfd3613c73bb6df979b8"
  version_pinned: "polars >= 2.0"
  tags:
    - polars
    - dataframes
    - lazyframe
    - data-processing
    - data-analysis
    - python
compatibility: Requires Python 3.10+ and Polars >= 2.0. Run `python -c
  "import polars as pl; print(pl.__version__)"` if unsure which version is
  installed.
---

# Polars

<!-- Local addition: routing and version notes. -->

**Related skills**: [[python]] for general Python style, [[spark]] for PySpark and Delta Lake.

**When not to use Polars**: if the data is already a Spark DataFrame, the job runs on Databricks, or the task needs a distributed cluster, use [[spark]] instead. Do not migrate an existing pandas job unless the user asks.

**Version target**: this skill targets Polars 2.x. The vendored upstream text is v0.3.1 and still says Polars >= 1.0; the 2.0 notes below override that. For 1.x, use an older copy.

## Polars 2.0

These are the 2.0 changes that affect this skill. Full list:
https://docs.pola.rs/releases/upgrade/2/

- **Streaming is the default.** `LazyFrame.collect()` with `engine="auto"` now uses the streaming engine. Row order is not guaranteed for `join`, `group_by`, `unpivot`, and similar operations. Sort explicitly when order matters, or pass `maintain_order="left"` to a join and `maintain_order=True` to a group-by.
- **`read_csv` and `read_ipc` are eager wrappers.** They now call `scan_csv(...).collect()` and `scan_ipc(...).collect()`. Prefer `scan_*` in code that ships.
- **`explode` drops empty lists.** An empty list now produces zero rows. Pass `empty_as_null=True` for the old one-null-row behavior.
- **Horizontal concat is strict.** `pl.concat(..., how="horizontal")` requires equal heights and no longer pads with nulls. Use `how="horizontal_extend"` when you want the old padding.
- **Renamed and removed APIs.** `melt` → `unpivot`; `join_nulls` → `nulls_equal`; string-to-date casts → `.str.to_date()` / `.str.to_datetime()`; integer-to-categorical casts are disabled, so cast to string first.
- **Binning.** `cut` and `qcut` are deprecated. Use `bin_intervals`, `bin_quantiles`, or `bin_ranks`, and pass `right_closed=True` to keep the old right-closed bins.
- **Interchange removed.** `DataFrame.__dataframe__` and the interchange protocol are gone. Use Arrow (`to_arrow` / `from_arrow`) or pandas.

## Default stance

When no data processing library has been specified, use Polars. Always use
the lazy API: build the whole query, then execute it with one `.collect()`,
so Polars can optimize the plan before any data is read. Eager execution
skips that optimization, so the same logic does more work.

**Data already in memory is no exception.** When a query starts from a
`DataFrame` — a function argument, `pl.from_pandas(pdf)`,
`pl.DataFrame(...)`, or an earlier `collect()` — call `.lazy()` before the
first operation and `.collect()` at the end. `.lazy()` is free (it wraps the
data, it does not copy it) and it is what turns a step-by-step eager pipeline
into one optimized plan. Do this unless the user asks for eager execution.

```python
# start from a file
pl.scan_csv("data.csv").filter(...).collect()

# start from an existing DataFrame — wrap it first
df.lazy().filter(...).group_by(...).agg(...).collect()

# avoid: eager, step by step, nothing to optimize
df = pl.read_csv("data.csv")
df.filter(...).group_by(...).agg(...)
```

## From question to insight

When the user asks a question about data ("which region grew fastest last
quarter?"), the goal is a correct answer in one shot: spend one cheap step
on schema discovery, then write the full query once.

1. **Discover the schema first. Never guess column names or dtypes.**

```python
lf = pl.scan_csv("sales.csv")        # or scan_parquet / scan_ndjson
print(lf.collect_schema())           # names and dtypes, no data read
print(lf.head(5).collect())          # eyeball values, formats, dirt
```

2. **Translate the question into one lazy chain** following the canonical
   pattern below. Map vague terms to explicit definitions and state them
   in the answer ("growth = revenue vs. previous quarter, percent").
3. **Handle dirt at the scan**, not downstream:
   `pl.scan_csv(path, null_values=["N/A", ""], try_parse_dates=True)`.
4. **Collect once**, then sanity-check the result before answering — the
   checks are at the end of `references/insight-recipes.md`.
5. **Answer with numbers, not just code.** Lead with the insight, show the
   supporting table, and keep the LazyFrame around so follow-ups extend the
   chain instead of rebuilding it.

Read `references/insight-recipes.md` first for ready-made query shapes (top-k,
period-over-period, distributions, time series, cohort-style questions).

## Core rules

- **Expressions over Python functions.** Never use `map_elements`,
  `map_batches`, `map_groups` (or the removed `apply`) when an expression
  exists — almost always one does. Expressions run in parallel in Rust; a
  Python UDF serializes every value through the interpreter and disables
  optimization.
- **Filter early.** Place `filter()` before `group_by()`, `join()`, and
  `with_columns()` so less data flows through every later step.
- **One context, one expression per operation.** Pass all expressions to a
  single `with_columns()`; expressions in one context run in parallel, and
  repeated calls in a loop serialize them. When the *same* operation applies
  to several columns, do not build one expression per column either — write
  one expression and let it expand over the schema: `pl.col("a", "b")`,
  `pl.col(pl.Float64)`, `pl.col("^sales_.*$")`, `cs.numeric()`,
  `pl.all().exclude("id")`. Rename the expanded set with `.name.suffix("_x")`
  / `.name.prefix()` / `.name.map(fn)`; `.alias()` names one output only.
  Selector catalogue and caveats: `references/expressions.md`.
- **Chain everything, collect once.** An intermediate `.collect()`
  materializes data and discards the plan, so everything after it optimizes
  from scratch.
- **Polars is strictly typed.** No implicit coercion, no mixed-type
  columns. Cast explicitly with `.cast()`; use
  `.cast(pl.Float64, strict=False)` to turn unparseable values into nulls
  instead of errors.
- **Respect warnings — never silence them.** A Polars warning names the
  exact fix in its message: `PerformanceWarning` and subclasses like
  `PolarsInefficientMapWarning` tell you to use `collect_schema()`, or to
  rewrite a `map_elements` call as a native expression. Apply the change;
  never `warnings.filterwarnings("ignore")` or `warnings.catch_warnings()`
  to hide it.

```python
import polars.selectors as cs

# avoid: same operation, one expression per column
lf.with_columns([(pl.col(c) * 1.1).alias(f"{c}_adj") for c in ["a", "b", "c"]])

# prefer: one expression, expanded by the schema
lf.with_columns((pl.col("a", "b", "c") * 1.1).name.suffix("_adj"))
lf.with_columns(cs.numeric().fill_null(0))          # in place, same names
```

## Canonical query pattern

Build queries in this order. Each step reduces data before the next.

```python
customers = pl.scan_csv("customers.csv")

result = (
    pl.scan_csv("orders.csv")                    # 1. scan, never read
    .filter(pl.col("year") == 2024)              # 2. filter early
    .join(customers, on="customer_id", how="left")   # 3. join filtered data
    .with_columns(                               # 4. add computed columns
        (pl.col("revenue") - pl.col("cost")).alias("profit")
    )
    .group_by("region")                          # 5. group
    .agg(                                        # 6. aggregate
        pl.col("profit").sum().alias("total_profit"),
        pl.col("profit").mean().alias("avg_profit"),
        pl.len().alias("count"),
    )
    .filter(pl.col("count") > 10)                # 7. filter groups
    .sort("total_profit", descending=True)       # 8. sort
    .select("region", "total_profit", "avg_profit")  # 9. final columns
    .collect()                                   # 10. execute once
)
```

## Context selection

| Context | Use when | Output |
|---|---|---|
| `select()` | Choosing or transforming columns | Only specified columns |
| `with_columns()` | Adding or replacing columns | All columns plus new |
| `filter()` | Removing rows | Same columns, fewer rows |
| `group_by() + agg()` | Aggregating per group | One row per group |
| `over()` | Group aggregate broadcast to all rows | Same shape as input |
| `sort()` | Ordering rows | Same shape, reordered |
| `join()` | Combining two frames | Columns from both |

The critical distinction: `group_by().agg()` returns one row per group;
`over()` keeps all rows and broadcasts the group result back — use it inside
`with_columns()` when every row needs its group's aggregate.

## Gotchas

Each of these fails silently or with a confusing error.

- **Strings in `then()`/`otherwise()` are column names, not values.**
  `pl.when(c).then("adult")` reads a column called `adult` (or raises
  `ColumnNotFoundError`). Wrap literals: `.then(pl.lit("adult"))`.
- **Null comparisons drop rows silently.** `filter(pl.col("v") > 2)`
  excludes nulls because `null > 2` is null, which is falsy. If nulls
  should be kept: `(pl.col("v") > 2) | pl.col("v").is_null()`.
- **Use `&`, `|`, `~` with parentheses around each condition.** Python's
  `and`/`or`/`not` raise on expressions, and without parentheses operator
  precedence binds the comparison wrong:
  `(pl.col("a") > 1) & (pl.col("b") < 5)`.
- **A bare aggregation in `with_columns()` broadcasts the global value to
  every row.** `with_columns(pl.col("v").mean())` fills the column with the
  overall mean — it does not error. Add `.over("group")` for the per-group
  value aligned to each row.
- **Duplicate output names raise `DuplicateError`.** A computed column
  keeps its source name; `select(pl.col("p"), pl.col("p") * 1.1)` fails.
  Always `.alias()` derived columns — or `.name.suffix(...)` for an expanded
  expression, which keeps every source name.
- **Regex column selection needs `^...$` anchors.** `pl.col("sales_.*")` is
  read as a literal column name and raises `ColumnNotFoundError`;
  `pl.col("^sales_.*$")` expands. One `col()` call cannot mix names with
  dtypes — use a selector instead.
- **Nulls don't match in joins by default.** Rows with null keys silently
  drop out of inner joins; pass `nulls_equal=True` if they should match.
- **pandas names don't transfer.** No index, no `iloc`, no `groupby`; verify
  any method you're not certain about (see below) rather than assuming the
  pandas spelling exists.

## Version and API verification

The API moved at 1.0 (for example `str.lengths()` became `str.len_chars()`,
and `pl.NUMERIC_DTYPES` gave way to `polars.selectors`). Before writing a
method call you are not certain about, verify it against the installed
version rather than memory:

- **MCP (preferred):** install `polars-mcp` in the project environment for
  live lookups — `polars_search_api("filter")` finds methods by keyword,
  `polars_browse("Expr.str")` explores a namespace, and
  `polars_get_docstring("Expr.str.contains")` gets the exact signature.
- **Otherwise fetch the docs:** the top of `references/expressions.md` maps
  all 18 expression categories to their live URLs on https://docs.pola.rs.

## When to load references

These reference files hold detail that is NOT in this file. When a task
matches one below, you MUST read that reference before writing code — do not
translate or answer from memory when a reference covers the task. Each file
opens with a `## Contents` line for jumping to a section.

- **Translating pandas → Polars** — MUST read
  `references/pandas-to-polars.md` first (it's short). It carries
  API-difference traps absent from this file.
- **Answering a natural-language data question** — read
  `references/insight-recipes.md` for ready-made query shapes.
- `references/contexts.md` — detailed behavior of `select`, `with_columns`,
  `filter`, `group_by`/`agg`, `over` (window mapping strategies), `sort`,
  and `join`.
- `references/expressions.md` — string, temporal, list, struct, expansion
  and selector syntax; casting; null handling; conditionals; plus the
  fetch-map described above.
- `references/lazy-api.md` — scan options for dirty data, query plan
  inspection with `explain()`, the streaming engine (the 2.0 default) and
  larger-than-memory data, `sink_parquet`.

<!-- Local addition: the upstream skill does not cover DataFrame display styling. -->

## Presentation styling

The Polars styling guide is about display, not code style: https://docs.pola.rs/user-guide/misc/styling/

`df.style` returns a Great Tables `GT` object. It changes how a table looks in a notebook or report. It does not change the data or the query. Install the optional dependency with `uv add "polars[style]"` or `uv add great-tables`.

```python
import polars as pl
import polars.selectors as cs
from great_tables import loc, style

(
    df.style.tab_header(title="Iris data", subtitle="Mean measurements per species")
    .tab_stub(rowname_col="species")
    .tab_spanner("Petal", cs.starts_with("petal"))
    .cols_label(petal_length="Length", petal_width="Width")
    .fmt_number("petal_width", decimals=2)
    .tab_style(
        style.fill("yellow"),
        loc.body(rows=pl.col("petal_length") == pl.col("petal_length").max()),
    )
    .tab_style(style.text(weight="bold"), loc.stub())
)
```

Use `fmt_number` for decimals, `tab_header` for a title, `tab_stub` for a row label, and `tab_style` for emphasis. Keep presentation code separate from data preparation so the query stays reusable.
