---
name: datacontract
description: Use when writing, modifying, linting, or testing ODCS data contracts (*_odcs.yaml files). Covers ODCS v3.1.0 field reference, schema/quality/SLA/server sections, and datacontract CLI commands.
metadata:
  review_after: "2026-08-13"
  docs_url: "https://bitol-io.github.io/open-data-contract-standard/latest/"
  version_pinned: "ODCS v3.1.0 / datacontract-cli"
---

# Data Contract (ODCS)

The **Open Data Contract Standard (ODCS) v3.1.0** is a YAML specification for machine-readable data contracts. The **datacontract CLI** validates, tests, exports, and imports those contracts.

**Related skills**: [[biocloud-datacontract]] for Biocloud/Naturalis project conventions; [[new-table]] for scaffolding new tables with contracts.

## CLI Workflow

```sh
# Install (preferred)
uv tool install --python python3.11 --upgrade 'datacontract-cli[all]'

# Verify
datacontract --version

# Typical workflow
datacontract init odcs.yaml                                      # create from template
datacontract lint odcs.yaml                                      # validate ODCS structure
datacontract changelog v1.odcs.yaml v2.odcs.yaml                 # breaking-change diff
datacontract test odcs.yaml                                      # schema + quality tests against server
datacontract export html odcs.yaml --output odcs.html            # generate HTML docs
datacontract import sql --source ddl.sql --dialect postgres --output odcs.yaml
datacontract dbt sync orders.odcs.yaml --project-dir ./warehouse

# In-project (uv managed):
uv run datacontract lint <file>
```

## Minimal Contract Template

```yaml
apiVersion: v3.1.0
kind: DataContract
id: <stable-unique-id>         # e.g. UUID or raw_orders
name: <Human Readable Name>
version: 0.0.1
status: active                 # proposed | draft | active | deprecated | retired
domain: <domain>

description:
  purpose: <why this data exists>

servers:
  - server: production
    type: databricks            # see Servers section for all types
    environment: production
    catalog: <catalog_name>
    schema: <schema_name>

schema:
  - name: <table_name>
    logicalType: object
    physicalType: table
    description: <table description>
    properties:
      - name: <column_name>
        logicalType: string
        physicalType: string
        description: <column description>
        required: true
```

## Fundamentals

Required fields: `apiVersion`, `kind`, `id`, `version`, `status`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `apiVersion` | string | Yes | Always `v3.1.0` |
| `kind` | string | Yes | Always `DataContract` |
| `id` | string | Yes | Stable unique ID — does not change if name changes |
| `version` | string | Yes | Semantic version of the contract itself |
| `status` | string | Yes | `proposed`, `draft`, `active`, `deprecated`, `retired` |
| `name` | string | No | Human-readable display name |
| `domain` | string | No | Logical data domain |
| `tags` | array | No | Categorization tags, e.g. `['finance', 'sensitive']` |
| `description.purpose` | string | No | Intended use of the data |
| `description.limitations` | string | No | What this data must NOT be used for |
| `description.usage` | string | No | Recommended usage |

## Schema

Schema models data as **objects** (tables, documents) and **properties** (columns, fields). Both are called **elements**.

```yaml
schema:
  - id: orders_obj             # stable ID for cross-referencing
    name: orders
    logicalType: object
    physicalType: table
    physicalName: orders_v1    # physical name if different from logical name
    description: Order records
    dataGranularityDescription: One row per order
    properties:
      - id: order_id_prop
        name: order_id
        logicalType: string
        physicalType: VARCHAR(40)
        description: Unique order identifier
        primaryKey: true
        primaryKeyPosition: 1
        required: true
        unique: true

      - name: order_ts
        logicalType: timestamp
        physicalType: TIMESTAMP
        logicalTypeOptions:
          format: "yyyy-MM-ddTHH:mm:ssZ"
          timezone: true
          defaultTimezone: "Europe/Amsterdam"
        examples:
          - "2024-03-10T14:22:35Z"

      - name: amount
        logicalType: number
        physicalType: DOUBLE
        classification: public   # public | restricted | confidential

      - name: status
        logicalType: string
        physicalType: string
        required: true
        partitioned: true
        partitionKeyPosition: 1
        pattern: "^(pending|shipped|delivered|cancelled)$"

      - name: email
        logicalType: string
        physicalType: string
        classification: restricted
        encryptedName: email_encrypted   # name of the column holding the encrypted value
        criticalDataElement: true
```

### Logical Types

`string`, `date`, `timestamp`, `time`, `number`, `integer`, `object`, `array`, `boolean`

### Key Property Fields

| Field | Purpose |
|-------|---------|
| `primaryKey: true` + `primaryKeyPosition: N` | Mark primary key columns; position starts at 1 |
| `required: true` | Column must not contain NULLs |
| `unique: true` | All values must be distinct |
| `partitioned: true` + `partitionKeyPosition: N` | Partition key columns |
| `classification` | Data sensitivity: `public`, `restricted`, `confidential` |
| `encryptedName` | Name of the counterpart column with encrypted values |
| `pattern` | ECMA-262 regex that valid values must match |
| `examples` | Sample values for documentation |
| `criticalDataElement: true` | Marks this as a Critical Data Element (CDE) |
| `transformLogic` | SQL/logic used to derive this column |
| `transformSourceObjects` | List of source objects used in the transform |

### Arrays

```yaml
- name: street_lines
  logicalType: array
  items:
    logicalType: string

- name: line_items
  logicalType: array
  logicalTypeOptions:
    minItems: 1
    maxItems: 100
    uniqueItems: true
  items:
    logicalType: object
    properties:
      - name: sku
        logicalType: string
      - name: quantity
        logicalType: integer
```

## Data Quality

Quality rules attach at the **property level** (column checks) or **schema/object level** (row-level checks). Four types: `library`, `sql`, `text`, `custom`.

### Library Metrics

The default type — omit `type: library` when `metric` is present.

```yaml
properties:
  - name: customer_id
    quality:
      - id: no_nulls
        metric: nullValues
        mustBe: 0
        description: "No null customer IDs"

      - id: email_missing
        metric: missingValues
        arguments:
          missingValues: [null, '', 'N/A', 'n/a']
        mustBeLessThan: 100
        unit: rows         # rows (default) or percent

      - name: line_item_unit
        quality:
          - id: valid_units
            metric: invalidValues
            arguments:
              validValues: ['kg', 'pounds', 'g']
            mustBe: 0

          - id: iban_format
            metric: invalidValues
            mustBe: 0
            arguments:
              pattern: '^[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}$'

      - name: phone_number
        quality:
          - id: low_duplicates
            metric: duplicateValues
            mustBeLessThan: 1
            unit: percent

schema:
  - name: orders
    quality:
      - id: row_count_check
        metric: rowCount
        mustBeBetween: [100, 1000000]

      - id: unique_compound_key
        metric: duplicateValues
        mustBe: 0
        description: "tenant_id + order_id must be unique"
        arguments:
          properties: [tenant_id, order_id]
```

### Library Metrics Reference

| Metric | Level | Description | Key Arguments |
|--------|-------|-------------|---------------|
| `nullValues` | property | Count of NULL values | — |
| `missingValues` | property | Count of null/''/N/A/etc. | `missingValues: [...]` |
| `invalidValues` | property | Count outside valid set or pattern | `validValues: [...]` or `pattern: '...'` |
| `duplicateValues` | property | Count of duplicate values | — |
| `duplicateValues` | schema | Duplicate composite-key rows | `properties: [col1, col2]` |
| `rowCount` | schema | Total row count | — |

### Operators

| Operator | Symbol | Example |
|----------|--------|---------|
| `mustBe` | = | `mustBe: 0` |
| `mustNotBe` | ≠ | `mustNotBe: 3` |
| `mustBeGreaterThan` | > | `mustBeGreaterThan: 0` |
| `mustBeGreaterOrEqualTo` | ≥ | `mustBeGreaterOrEqualTo: 1` |
| `mustBeLessThan` | < | `mustBeLessThan: 1000` |
| `mustBeLessOrEqualTo` | ≤ | `mustBeLessOrEqualTo: 999` |
| `mustBeBetween` | ∈ | `mustBeBetween: [0, 100]` |
| `mustNotBeBetween` | ∉ | `mustNotBeBetween: [0, 100]` |

### SQL Quality

```yaml
quality:
  - id: no_future_dates
    type: sql
    query: |
      SELECT COUNT(*) FROM {object} WHERE {property} > CURRENT_DATE
    mustBe: 0
    scheduler: cron
    schedule: "0 20 * * *"
```

`{object}` and `{property}` are replaced at runtime with the current object/property name.

### Custom (vendor-specific)

```yaml
quality:
  - id: soda_duplicates
    type: custom
    engine: soda           # soda | greatExpectations | montecarlo | dbt
    implementation: |
      type: duplicate_percent
      columns: [carrier, shipment_number]
      must_be_less_than: 1.0
```

### Quality Dimensions

Use `dimension:` to classify a rule for reporting:
`accuracy`, `completeness`, `conformity`, `consistency`, `coverage`, `timeliness`, `uniqueness`

## Servers

```yaml
servers:
  # Databricks (Unity Catalog)
  - server: production
    type: databricks
    environment: production
    catalog: dna_production
    schema: enriched
    host: dbc-xxxxxxxx-xxxx.cloud.databricks.com
    roles:
      - role: Admins
        description: Full access

  # Amazon S3
  - server: raw_s3
    type: s3
    environment: production
    location: s3://my-bucket/path/to/data/
    format: parquet          # parquet | json | csv | avro | orc

  # PostgreSQL
  - server: pg_prod
    type: postgres
    environment: production
    host: db.example.com
    database: mydb
    schema: public
```

### Common Server Properties

| Field | Required | Notes |
|-------|----------|-------|
| `server` | Yes | Identifier for this server entry |
| `type` | Yes | Server technology (see list below) |
| `environment` | No | `prod`, `production`, `dev`, `development`, `uat` |
| `description` | No | Human-readable description |
| `roles` | No | Access roles for this server |

### Server Types

`api`, `athena`, `azure`, `bigquery`, `clickhouse`, `cloudsql`, `databricks`, `db2`, `denodo`, `dremio`, `duckdb`, `glue`, `hive`, `impala`, `informix`, `kafka`, `kinesis`, `local`, `mysql`, `oracle`, `postgres`, `postgresql`, `presto`, `pubsub`, `redshift`, `s3`, `sftp`, `snowflake`, `sqlserver`, `synapse`, `trino`, `vertica`, `zen`, `custom`

## SLA

```yaml
slaProperties:
  - id: data_freshness
    property: latency
    value: 4
    unit: d                   # d/day/days | h/hr/hours | y/yr/years
    element: orders.order_ts  # object.property notation
    driver: analytics         # regulatory | analytics | operational
    scheduler: cron
    schedule: "0 6 * * *"

  - id: data_retention
    property: retention
    value: 3
    unit: y

  - id: update_frequency
    property: frequency
    value: 1
    unit: d

  - id: ga_date
    property: generalAvailability
    value: 2024-01-01T00:00:00Z
```

### SLA Property Values

`availability`, `throughput`, `errorRate`, `generalAvailability`, `endOfSupport`, `endOfLife`, `retention`, `frequency`, `latency`, `timeToDetect`, `timeToNotify`, `timeToRepair`

## Support & Roles

```yaml
support:
  - channel: email
    url: mailto:team@example.com
  - channel: slack
    url: https://myworkspace.slack.com/archives/CXXXXXX

roles:
  - role: DataOwner
    description: Responsible for data quality and governance

customProperties:
  - property: owner
    value: My Team
```

## File Naming & Versioning

- File name: `<table_name>_odcs.yaml`, placed next to the source code for that table
- `id`: stable, never changes — even when the contract is renamed
- `version`: semantic version of the contract — bump on ANY breaking schema change
- `status`: progress through `draft` → `active` → `deprecated` → `retired`
- Breaking change = column removed, type changed, required constraint added, partition changed

## Best Practices

- **Lint in CI**: run `datacontract lint` on every commit — catches structural errors before they reach prod
- **Changelog on PR**: `datacontract changelog old.yaml new.yaml` surfaces breaking changes for reviewers
- **Stable IDs**: use `id:` on schema elements you may reference or rename — stable refs survive refactors
- **Physical vs. logical types**: use `logicalType` for portability (e.g., `string`), `physicalType` for the actual DB type (e.g., `VARCHAR(40)`)
- **Quality level matters**: property-level for column checks; schema-level for row counts and composite uniqueness
- **One server entry per environment**: keep `environment:` explicit on every server entry
- **Never omit `required:` on primary keys**: primary key columns should always have `required: true`
- **Version every breaking change**: consumers rely on `version` to detect when they need to update downstream

---

## Quick Reference: CLI Commands

| Command | Purpose |
|---------|---------|
| `datacontract init odcs.yaml` | Create empty contract from template |
| `datacontract lint odcs.yaml` | Validate ODCS structure against schema |
| `datacontract changelog a.yaml b.yaml` | Show breaking-change diff between two versions |
| `datacontract test odcs.yaml` | Run schema + quality tests against server |
| `datacontract export html odcs.yaml --output out.html` | Generate HTML documentation |
| `datacontract export sql odcs.yaml` | Generate SQL DDL |
| `datacontract import sql --source ddl.sql --dialect postgres` | Create contract from existing DDL |
| `datacontract dbt sync odcs.yaml --project-dir ./dbt` | Sync dbt tests from contract |
| `uv run datacontract lint <file>` | In-project invocation via uv |

---

## Troubleshooting

### `lint` fails: "apiVersion not found" or "kind is invalid"

`apiVersion` must be exactly `v3.1.0`; `kind` must be exactly `DataContract`. Both are case-sensitive.

### `lint` fails on schema properties

Every element in `properties[]` requires `name`. A missing `name` causes lint failure.

### `test` fails: "no server configured"

The `servers` section is missing, or credentials are not set. Credentials are passed via env vars: `DATACONTRACT_<TYPE>_<FIELD>` (e.g., `DATACONTRACT_POSTGRES_USERNAME`).

### `test` fails: schema mismatch

The physical schema in the database diverged from the contract. Run `datacontract changelog` to identify what changed.

### Version bump not detected in CI

The contract's `version` field was not incremented. Bump `version` on every breaking change to schema, quality rules, or SLA.

### `quality.rule` not recognized

`quality.rule` is deprecated since ODCS v3.1.0 — use `quality.metric` instead.

---

## Python API

Everything the CLI does is available as a Python library through the `DataContract` class from `datacontract.data_contract`. The parsed contract model (`OpenDataContractStandard`) comes from the separate `open_data_contract_standard` package — it is a Pydantic BaseModel, not a dict.

### Constructor

```python
from datacontract.data_contract import DataContract

DataContract(
    data_contract_file="datacontract.yaml",   # path or URL to YAML file
    # — OR —
    data_contract_str="...",                   # contract as a YAML string
    # — OR —
    data_contract=odcs_object,                 # pre-parsed OpenDataContractStandard

    server="production",                       # which server to test/export (default: all)
    schema_name="orders",                      # which schema to test/export (default: "all")
    spark=spark_session,                       # SparkSession for Spark/Databricks testing
    duckdb_connection=conn,                    # existing DuckDB connection
    check_categories={"schema", "quality"},    # subset: schema, quality, servicelevel, custom
    publish_url="https://...",                 # URL to publish test results to
    inline_references=True,                    # resolve $ref references (default True)
    ssl_verification=True,                     # verify SSL certificates (default True)
    include_failed_samples=False,              # collect failing row samples (default False)
)
```

### Methods

| Method | Returns | Purpose |
|--------|---------|---------|
| `lint()` | `Run` | Validate ODCS YAML structure against JSON schema |
| `test()` | `Run` | Run schema + quality checks against configured server(s) |
| `get_data_contract()` | `OpenDataContractStandard` | Return fully resolved Pydantic model — use for schema introspection |
| `export(format, schema_name="all", **kwargs)` | `str\|bytes` | Convert to another format (see ExportFormat below) |
| `changelog(other: DataContract)` | `ChangelogResult` | Diff two contract versions |
| `DataContract.import_from_source(format, source, **kwargs)` | `OpenDataContractStandard` | Class method: import from SQL, dbt, Avro, etc. |
| `DataContract.init(template, schema)` | `OpenDataContractStandard` | Class method: create new contract from template |

### Inspecting test / lint results

```python
run = data_contract.test()   # or .lint()

run.result          # "passed" | "failed" | "warning" | "error" | "info" | "unknown"
run.has_passed()    # bool
run.timestampStart  # datetime (UTC)
run.timestampEnd    # datetime (UTC)

for check in run.checks:
    print(check.result)    # "passed" | "failed" | ...
    print(check.name)      # human-readable check name
    print(check.type)      # "lint" | "schema" | "quality" | ...
    print(check.model)     # which schema/table this check covers
    print(check.field)     # which column (if column-level)
    print(check.reason)    # failure reason / details
```

### Export formats

Pass as first arg to `.export()`:

`sql`, `spark`, `jsonschema`, `pydantic-model`, `html`, `markdown`, `odcs`, `dbt-models`, `dbt-sources`, `dbt-staging-sql`, `avro`, `protobuf`, `bigquery`, `mermaid`, `great-expectations`, `excel`, `rdf`, `dbml`, `sqlalchemy`, `iceberg`, `custom`

```python
spark_schema_str = data_contract.export("spark", model="orders")  # returns StructType definition
html = data_contract.export("html")
```

### Spark / Databricks integration

Register a DataFrame as a temp view, then pass the `SparkSession` to test in-memory:

```python
df.createOrReplaceTempView("my_table")
run = DataContract(data_contract_file="contract.yaml", spark=spark).test()
assert run.has_passed()
```

### `OpenDataContractStandard` model — attribute access

`get_data_contract()` returns a Pydantic `BaseModel`. Use attribute access — **never call `model_dump()` to walk dicts**:

```
OpenDataContractStandard
├─ .id, .name, .version, .status, .domain, .apiVersion, .kind
├─ .description: Description          (.usage, .purpose, .limitations)
├─ .servers: list[Server]             (.server, .type, .environment, .catalog, .schema_, .host, ...)
├─ .slaProperties: list[SLAProperty]
├─ .customProperties: list[CustomProperty]   (.property, .value, .description)
│
└─ .schema_: list[SchemaObject]       ← aliased as "schema" in YAML
    ├─ .id, .name, .physicalType, .physicalName, .logicalType
    ├─ .description, .dataGranularityDescription
    ├─ .tags: list[str]
    ├─ .customProperties: list[CustomProperty]
    ├─ .quality: list[DataQuality]    ← table-level quality rules
    └─ .properties: list[SchemaProperty]
        ├─ .id, .name, .physicalType, .physicalName, .logicalType
        ├─ .description, .businessName
        ├─ .required: bool            ← NOT NULL constraint
        ├─ .unique: bool
        ├─ .primaryKey: bool
        ├─ .primaryKeyPosition: int
        ├─ .partitioned: bool
        ├─ .partitionKeyPosition: int
        ├─ .classification: str       ← "public" | "restricted" | "confidential"
        ├─ .criticalDataElement: bool
        ├─ .examples: list[Any]
        ├─ .logicalTypeOptions: dict  ← minLength, maxLength, format, enum, pattern, ...
        ├─ .transformLogic: str
        ├─ .transformSourceObjects: list[str]
        ├─ .customProperties: list[CustomProperty]
        ├─ .quality: list[DataQuality]   ← column-level quality rules
        ├─ .properties: list[SchemaProperty]   ← nested (for object types)
        └─ .items: SchemaProperty             ← array item schema
```

### `DataQuality` model fields

```
DataQuality
├─ .id, .name, .description, .dimension, .severity, .businessImpact
├─ .type: str          ← "library" (default) | "sql" | "text" | "custom"
├─ .metric: str        ← nullValues | missingValues | invalidValues | duplicateValues | rowCount | ...
├─ .arguments: dict    ← metric-specific; e.g. {validValues: [...]} or {pattern: "..."}
├─ .mustBe, .mustNotBe, .mustBeGreaterThan, .mustBeLessThan, .mustBeBetween, ...
├─ .query: str         ← SQL query for type: sql checks
├─ .engine: str        ← soda | dbt | greatExpectations | ...
├─ .implementation     ← str or dict, for type: custom
└─ .schedule, .scheduler
```

### `CustomProperty` model fields

```
CustomProperty
├─ .id: str
├─ .property: str     ← the key name
├─ .value: Any        ← any YAML value (string, list, dict, ...)
└─ .description: str
```

### `ChangelogResult`

```python
result = v1.changelog(v2)
result.has_changes()   # bool
result.entries         # list[ChangelogEntry]: .path, .type ("added"|"removed"|"updated"), .old_value, .new_value
```

---

## Related Skills

- [[biocloud-datacontract]]: Biocloud/Naturalis project conventions, Databricks server templates, quarantine checks, shared Python utilities
- [[new-table]]: Scaffolding new tables with run files, tests, and data contracts
- [[spark]]: PySpark/Delta Lake patterns that read and validate these contracts
