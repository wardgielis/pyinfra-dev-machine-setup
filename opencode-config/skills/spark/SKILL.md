---
name: spark
description: Generic PySpark/Delta Lake/Databricks patterns. Use when writing Spark transformations, Delta Lake operations, or Databricks workflows. Does NOT contain project-specific paths or configs.
metadata:
  review_after: "2026-08-09"
  docs_url: "https://spark.apache.org/docs/latest/"
---

# Apache Spark & Delta Lake

## Style Guide (Palantir)

Best practices from [palantir/pyspark-style-guide](https://github.com/palantir/pyspark-style-guide).

### Column Selection

Prefer string column references (Spark 3.0+), then `F.col()`, avoid direct dataframe access:

```python
# bad
df.select(F.lower(df1.colA), F.upper(df2.colB))

# good
df.select(F.lower('colA'), F.upper('colB'))

# fallback when string syntax doesn't work
df.select(F.lower(F.col('colA')))
```

### Complex Logic

Refactor complex logical operations into named variables — limits to 3 expressions per block:

```python
# bad
F.when((F.col('status') == 'Delivered') | ((F.datediff('delivery_date', 'current_date') < 0) & ((F.col('registration') != '') | (F.col('operator') != ''))), 'In Service')

# good
has_operator = (F.col('operator') != '')
delivery_date_passed = (F.datediff('delivery_date', 'current_date') < 0)
is_delivered = (F.col('status') == 'Delivered')
F.when(is_delivered | (delivery_date_passed & has_operator), 'In Service')
```

### Select Statements

Use `select` to define a schema contract — cluster operations of the same type:

```python
# good
df = df.select(
    'aircraft_id',
    'aircraft_type',
    F.col('registration').alias('tail_number'),
    F.col('economy_seats').cast('long'),
)

# prefer withColumn for single new columns
df = df.withColumn('days_open', (F.col('closed_at') - F.col('created_at')) / 86400)
```

### Empty Columns

Always use `F.lit(None)` — never empty strings or `'NA'`:

```python
df = df.withColumn('foo', F.lit(None))
```

### Comments

Explain the *why*, not the *what*:

```python
# good - gives context about data quirks
# The source stores timestamps as millis despite docs saying date
cols = ['start_date', 'delivery_date']
for c in cols:
    df = df.withColumn(c, F.from_unixtime(F.col(c) / 1000).cast(TimestampType()))
```

### UDFs

Avoid UDFs entirely — native PySpark functions are dramatically more performant.

### Chaining

Maximum 5 chained expressions. Break into separate blocks with intermediate assignments:

```python
# better: separate logical groups
df = df.select('a', 'b', 'c').filter(F.col('a') == 'truthiness')
df = df.withColumn('ratio', F.col('b') / F.col('c'))
df = df.join(df2, 'key', how='inner')

# best: extract into a well-named function
```

### Multi-line Expressions

Wrap in parentheses, avoid backslash continuation:

```python
df = (
    df
    .filter(F.col('event') == 'executing')
    .filter(F.col('has_tests') == True)
    .drop('has_tests')
)
```

### Miscellaneous

- Extract magic strings/ints into named constants — never use literals in filters
- Don't keep commented-out code — rely on git
- Files ≤ 250 lines, functions ≤ 70 lines
- Keep related logic in the same block

## DataFrame Operations

```python
from pyspark.sql import functions as F, types as T

# Read
df = spark.read.parquet("path")
df = spark.read.format("delta").load("path")
df = spark.read.table("catalog.schema.table")

# Write
df.write.mode("overwrite").parquet("path")
df.write.mode("append").format("delta").save("path")
df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("table")

# Column operations
df.withColumn("new_col", F.col("a") + F.col("b"))
df.withColumn("casted", F.col("value").cast("decimal(18,2)"))
df.withColumn("date_trunc", F.date_trunc("month", F.col("dt")))

# Aggregations (loses original row count — see Window Functions below)
df.groupBy("key").agg(
    F.sum("value").alias("total"),
    F.count("*").alias("cnt"),
    F.avg("score").alias("avg_score"),
)

# Filtering
df.filter(F.col("status") == "active")
df.filter(F.col("dt").between(F.lit("2024-01-01"), F.lit("2024-12-31")))

# Joins
df1.join(df2, on="key", how="left")
df1.alias("a").join(df2.alias("b"), F.col("a.id") == F.col("b.ref_id"), "inner")
```

## Window Functions

Prefer window functions over `groupBy` in many cases. `groupBy` collapses rows — you lose the original row context. Window functions preserve all rows while computing aggregations, which is often what you actually want. Use `groupBy` only when you explicitly need a reduced/aggregated result set.

### Always Specify an Explicit Frame

Without an explicit frame, Spark's default behavior changes depending on ordering — leading to subtle bugs:

```python
from pyspark.sql import Window as W

# bad — implicit frame, behavior varies
w_bad = W.partitionBy('key')

# good — explicit row frame
w = W.partitionBy('key').orderBy('num').rowsBetween(W.unboundedPreceding, 0)

# running sum (current row + all previous)
w_cumulative = W.partitionBy('key').orderBy('dt').rowsBetween(W.unboundedPreceding, 0)

# full partition frame (like groupBy but preserves rows)
w_full = W.partitionBy('key').rowsBetween(W.unboundedPreceding, W.unboundedFollowing)

# use with aggregation functions
df.withColumn('total_per_key', F.sum('value').over(w_full))
df.withColumn('running_total', F.sum('value').over(w_cumulative))
```

### Window vs groupBy

```python
# groupBy — collapses rows
summary = df.groupBy("department").agg(F.avg("salary").alias("avg_salary"))

# window — preserves all rows, adds computed column
df = df.withColumn(
    "avg_salary",
    F.avg("salary").over(W.partitionBy("department").rowsBetween(W.unboundedPreceding, W.unboundedFollowing)),
)

# common use cases for window functions:
# - dedup with row_number
df_deduped = (
    df
    .withColumn("rn", F.row_number().over(W.partitionBy("key").orderBy(F.col("updated").desc())))
    .filter(F.col("rn") == 1)
    .drop("rn")
)

# - lag/lead for comparing with previous/next row
df.withColumn("prev_value", F.lag("value").over(W.partitionBy("key").orderBy("dt")))

# - rank/dense_rank for ordering within groups
df.withColumn("rank", F.rank().over(W.partitionBy("key").orderBy(F.col("score").desc())))
```

### Null Handling in Windows

Use `ignorenulls=True` and explicit null ordering:

```python
w = W.partitionBy('key').orderBy(F.asc_nulls_last('num')).rowsBetween(W.unboundedPreceding, W.unboundedFollowing)
df.withColumn('first_val', F.first('num', ignorenulls=True).over(w))
df.withColumn('last_val', F.last('num', ignorenulls=True).over(w))
df.withColumn('next_val', F.lead('num').over(w))
```

### Avoid Empty partitionBy

An empty `partitionBy()` forces all data into a single partition — use `agg()` instead:

```python
# bad
w = W.partitionBy()
df = df.select(F.sum('num').over(w).alias('sum'))

# good
df = df.agg(F.sum('num').alias('sum'))
```

## Joins

- Always specify `how=` explicitly (even for inner)
- Avoid `right` joins — swap the dataframe order and use `left`
- Use dataframe aliases instead of renaming columns to avoid collisions
- Never use `.dropDuplicates()` or `.distinct()` as a crutch for bad joins — find the root cause

```python
# good — explicit, aliased
flights = flights.alias('flights')
parking = parking.alias('parking')
flights = flights.join(parking, on='flight_code', how='left')
flights = flights.select(
    F.col('flights.start_time').alias('flight_start'),
    F.col('parking.total_time').alias('parking_total'),
)
```

## Delta Lake

```python
from delta.tables import DeltaTable

# Merge (upsert)
target = DeltaTable.forPath(spark, "path")
source = spark.table("updates")

target.alias("t").merge(source.alias("s"), "t.key = s.key") \
    .whenMatchedUpdateAll() \
    .whenNotMatchedInsertAll() \
    .execute()

# Time travel
spark.read.format("delta").option("versionAsOf", 42).load("path")
spark.read.format("delta").option("timestampAsOf", "2024-01-01").load("path")

# Vacuum / optimize
DeltaTable.forPath(spark, "path").vacuum(168)       # 7 days retention
spark.sql("OPTIMIZE delta.`path`")
spark.sql("OPTIMIZE delta.`path` ZORDER BY (key)")

# History
display(DeltaTable.forPath(spark, "path").history())
```

## Databricks Utilities (dbutils)

```python
# Filesystem
dbutils.fs.ls("path")
dbutils.fs.cp("src", "dst", recurse=True)
dbutils.fs.rm("path", recurse=True)
dbutils.fs.mkdirs("path")

# Widgets
dbutils.widgets.text("param", "default", "Param Label")
param_val = dbutils.widgets.get("param")

# Notebooks
dbutils.notebook.run("notebook_path", timeout_seconds=3600, args={"key": "val"})
```

## Performance Tips

- **Partitioning**: write with `partitionBy("dt", "key")` — avoid too many small files
- **Bucketing**: use `bucketBy(16, "key")` for large tables joined on that key
- **Caching**: `df.cache()` or use `CHECKPOINT` for iterative jobs
- **Shuffle**: reduce shuffle partitions with `spark.conf.set("spark.sql.shuffle.partitions", 200)`
- **Auto Optimize**: enable for Delta tables with frequent writes
- **UDFs**: avoid at all costs — use native PySpark functions instead
- **Joins**: validate key uniqueness to prevent join explosions

## Testing Patterns

```python
# Inline assertion (Databricks)
df = spark.range(10).withColumn("doubled", F.col("id") * 2)
assert df.count() == 10
assert df.filter(F.col("doubled") > 10).count() == 5

# Row-level checks
from pyspark.sql import Row
expected = [Row(id=0, doubled=0), Row(id=1, doubled=2)]
actual = df.orderBy("id").limit(2).collect()
assert actual == expected
```

## Known Patterns

- Use `F.col()` over string column references for type safety (`df.select(F.col("a"))` not `df.select("a")`)
- Prefer `write.mode("overwrite").option("overwriteSchema", "true")` when schema evolves
- Use window functions for dedup: `F.row_number().over(W.partitionBy("key").orderBy(F.col("updated").desc()))`
- Prefer window functions over `groupBy` when preserving row context matters — `groupBy` collapses rows, windows don't
- Use `F.lit(None)` for empty columns, never `F.lit('')` or `F.lit('NA')`
- Always specify explicit frame `.rowsBetween(...)` in window functions to avoid implicit behavior
