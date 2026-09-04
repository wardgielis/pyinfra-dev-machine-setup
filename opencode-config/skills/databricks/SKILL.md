---
name: databricks
description: Generic Databricks CLI, SDK, and operational reference. Use when installing/authenticating the CLI, managing clusters/warehouses/jobs, querying Unity Catalog, handling secrets, setting up Databricks Connect locally, or extracting table schemas for data contract generation. Does NOT contain project-specific workspace URLs or configs — see [[biocloud-databricks]] for that.
metadata:
  review_after: "2027-07-22"
  docs_url: "https://docs.databricks.com/en/index.html"
  version_pinned: "databricks-cli / DBR 17.3"
---

# Databricks

Generic Databricks CLI + SDK reference. Covers operational tasks — cluster management, SQL execution, Unity Catalog, secrets, local development. **Related skills**: [[spark]] for PySpark/Delta Lake code patterns; [[biocloud-databricks]] for Biocloud-specific workspace config and workflows.

---

## IMPORTANT: Release Notes — Check Before Answering Runtime Questions

> **Rule**: Before answering any question about Databricks Runtime behaviour, missing functions, deprecated APIs, or unexpected behaviour in a specific DBR version — **look at the release notes first**. Do not rely on training knowledge alone; release notes change frequently and training data may be stale.

### Databricks Runtime (DBR)

- **Index (all versions)**: https://docs.databricks.com/en/release-notes/runtime/index.html
- **DBR 17.3** (current pinned version): https://docs.databricks.com/en/release-notes/runtime/17.3.html
- MLflow, Feature Store, GPU runtimes: linked from the index page above

### Serverless Compute

- **Serverless release notes**: https://docs.databricks.com/en/release-notes/serverless/index.html

> **Serverless behaviour differs from classic clusters** — preinstalled libraries, Python version, Spark config defaults, and network egress are all different. When a user hits unexpected behaviour on serverless, always check the serverless release notes before suggesting a fix.

---

## CLI Setup

### Install

```sh
brew tap databricks/tap
brew install databricks
```

### Authenticate (OAuth — preferred)

```sh
databricks auth login --host https://<workspace>.cloud.databricks.com --profile <name>
```

Check auth state:
```sh
databricks auth env --profile development
databricks current-user me --profile development
```

### ~/.databrickscfg Profile Format

```ini
[development]
host         = https://dbc-xxxx-xxxx.cloud.databricks.com
account_id   = <uuid>
workspace_id = <id>
auth_type    = databricks-cli

[production]
host         = https://dbc-yyyy-yyyy.cloud.databricks.com
account_id   = <uuid>
workspace_id = <id>
auth_type    = databricks-cli
```

Token-based fallback:
```ini
[development-token]
host  = https://dbc-xxxx-xxxx.cloud.databricks.com
token = dapi...
```

> Do not run `databricks auth login` when using token auth — it overwrites the token. Store tokens in a password manager.

---

## Cluster Operations

```sh
databricks clusters list --profile development
databricks clusters get --cluster-id <id> --profile development
databricks clusters start --cluster-id <id> --profile development
databricks clusters delete --cluster-id <id> --profile development
databricks clusters restart --cluster-id <id> --profile development
databricks clusters list-node-types --profile development
databricks clusters spark-versions --profile development
```

---

## SQL Warehouse Operations

```sh
databricks warehouses list --profile development
databricks warehouses get --id <warehouse-id> --profile development

# Execute SQL against a warehouse
databricks sql execute-statement \
  --warehouse-id <warehouse-id> \
  --statement "SELECT * FROM catalog.schema.table LIMIT 10" \
  --profile development

# Fetch async result
databricks sql get-statement --statement-id <id> --profile development
```

---

## Jobs and Notebook Operations

```sh
databricks jobs list --profile development
databricks jobs run-now --job-id <job-id> --profile development

# One-off run (no saved job)
databricks jobs submit --json '{
  "run_name": "ad-hoc run",
  "new_cluster": {},
  "notebook_task": {"notebook_path": "/path/to/notebook"}
}' --profile development

databricks runs get --run-id <run-id> --profile development
databricks runs cancel --run-id <run-id> --profile development
databricks runs list --job-id <job-id> --profile development
databricks runs get-output --run-id <run-id> --profile development
```

---

## Unity Catalog (CLI)

```sh
databricks catalogs list --profile development
databricks schemas list --catalog-name <catalog> --profile development
databricks tables list --catalog-name <catalog> --schema-name <schema> --profile development
databricks tables get --full-name <catalog>.<schema>.<table> --profile development
databricks tables delete --full-name <catalog>.<schema>.<table> --profile development
```

---

## Table Schema Extraction (hand-off to datacontract CLI)

Use these to extract a table schema locally. See [[biocloud-databricks]] for the biocloud workflow, and [[datacontract]] / [[biocloud-datacontract]] for the contract authoring steps.

### Option 1 — DDL via SQL (best for `datacontract import sql`)

```python
from databricks.connect import DatabricksSession
spark = DatabricksSession.builder.profile("development").serverless().getOrCreate()
ddl = spark.sql("SHOW CREATE TABLE catalog.schema.table").collect()[0][0]
print(ddl)
```

Pipe to datacontract CLI:
```sh
datacontract import --format sql --source table_ddl.sql --output contract.yaml
```

### Option 2 — StructType JSON

```python
schema_json = spark.table("catalog.schema.table").schema.json()
print(schema_json)
```

### Option 3 — Detailed column info (SQL)

```sql
DESCRIBE TABLE EXTENDED catalog.schema.table;
```

### Option 4 — Full metadata via CLI

```sh
databricks tables get --full-name catalog.schema.table --profile development
```

### Spark to ODCS Type Mapping

| Spark Type | ODCS logicalType | ODCS physicalType |
|------------|-----------------|-------------------|
| StringType | string | string |
| IntegerType | integer | int |
| LongType | integer | bigint |
| ShortType | integer | smallint |
| ByteType | integer | tinyint |
| FloatType | number | float |
| DoubleType | number | double |
| DecimalType(p,s) | number | decimal(p,s) |
| BooleanType | boolean | boolean |
| DateType | date | date |
| TimestampType | timestamp | timestamp |
| TimestampNTZType | timestamp | timestamp_ntz |
| BinaryType | string | binary |
| ArrayType | array | array |
| StructType (nested) | object | struct |
| MapType | object | map |

---

## Grants and Permissions (Unity Catalog)

### SQL

```sql
GRANT USE CATALOG ON CATALOG my_catalog TO `my_group`;
GRANT USE SCHEMA ON SCHEMA my_catalog.my_schema TO `my_group`;
GRANT SELECT ON TABLE my_catalog.my_schema.my_table TO `my_group`;
GRANT MODIFY ON TABLE my_catalog.my_schema.my_table TO `my_group`;
GRANT ALL PRIVILEGES ON SCHEMA my_catalog.my_schema TO `my_group`;
REVOKE SELECT ON TABLE my_catalog.my_schema.my_table FROM `my_group`;
SHOW GRANTS ON TABLE my_catalog.my_schema.my_table;
SHOW GRANTS ON SCHEMA my_catalog.my_schema;
SHOW GRANTS ON CATALOG my_catalog;
```

### CLI

```sh
databricks grants get table my_catalog.my_schema.my_table --profile development
databricks grants get schema my_catalog.my_schema --profile development
databricks grants get catalog my_catalog --profile development

databricks grants update table my_catalog.my_schema.my_table \
  --json '{"changes": [{"principal": "my_group", "add": ["SELECT"]}]}' \
  --profile development
```

Securable types: `catalog`, `schema`, `table`, `view`, `function`, `external-location`, `storage-credential`

---

## Secrets

```sh
databricks secrets list-scopes --profile development
databricks secrets list --scope my_scope --profile development
databricks secrets put-secret --scope my_scope --key my_key --string-value "value" --profile development
databricks secrets delete-secret --scope my_scope --key my_key --profile development
databricks secrets create-scope --name my_scope --profile development
databricks secrets delete-scope --name my_scope --profile development
```

---

## Databricks Connect (Local Development)

Package version must match the Databricks Runtime version.

```sh
uv add databricks-connect==17.3.9   # match DBR version
```

### Serverless session (no cluster ID needed)

```python
from databricks.connect import DatabricksSession
spark = DatabricksSession.builder.profile("development").serverless().getOrCreate()
df = spark.table("my_catalog.my_schema.my_table")
df.show()
```

### Classic cluster session

```python
spark = DatabricksSession.builder.profile("development").clusterId("your-cluster-id").getOrCreate()
```

---

## Databricks SDK (Python)

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(profile="development")

# Clusters
for c in w.clusters.list():
    print(c.cluster_id, c.cluster_name, c.state)

# SQL warehouses
for wh in w.warehouses.list():
    print(wh.id, wh.name, wh.state)

# Jobs
for job in w.jobs.list():
    print(job.job_id, job.settings.name)

# Unity Catalog
for table in w.tables.list(catalog_name="my_catalog", schema_name="my_schema"):
    print(table.full_name, table.table_type)

# Secrets
for scope in w.secrets.list_scopes():
    print(scope.name)

# Groups
for group in w.groups.list():
    print(group.display_name, group.id)
```

---

## Asset Bundles (DABs)

```sh
databricks bundle validate --target dev --profile development
databricks bundle deploy --target dev --profile development
databricks bundle deploy --target prod --profile production
databricks bundle run <resource-key> --target dev --profile development
databricks bundle destroy --target dev --profile development
databricks bundle summary --target dev --profile development
```

Bundle config lives in `databricks.yml`.

---

## Troubleshooting

### Auth fails with databricks-cli auth type

Switch to PAT token temporarily:
```ini
[development]
host  = https://dbc-xxxx.cloud.databricks.com
token = dapi...
```
Generate in Databricks UI: **User Settings > Developer > Access Tokens**.

### Serverless connect fails

Check https://docs.databricks.com/en/release-notes/serverless/index.html — the serverless library list and Python version change with each channel update.

### DATABRICKS_RUNTIME_VERSION not set locally

Expected — this env var is only set inside Databricks. Code that checks for it falls through to Databricks Connect locally.

---

## Related Skills

- [[biocloud-databricks]]: Biocloud workspace URLs, profiles, catalog naming, cluster configs, group sync, bundle ops, data contract workflow
- [[spark]]: PySpark/Delta Lake code patterns
- [[datacontract]]: Full ODCS field reference and datacontract CLI commands
- [[biocloud-datacontract]]: Biocloud-specific ODCS template and conventions
