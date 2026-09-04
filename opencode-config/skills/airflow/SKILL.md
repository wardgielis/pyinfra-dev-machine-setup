---
name: airflow
description: Generic Apache Airflow 3.x reference. Use when configuring Airflow (env vars, config sections), managing Variables and Connections, setting up OAuth/SSO (Azure AD, Keycloak), understanding 2.x→3.x migration changes, authoring DAGs, or checking best practices. Does NOT contain biocloud-specific DAG patterns — see [[airflow-dag]] for that.
metadata:
  review_after: "2026-08-13"
  docs_url: "https://airflow.apache.org/docs/apache-airflow/stable/"
  version_pinned: "apache-airflow==3.x (docs reflect 3.3.0)"
---

# Apache Airflow 3.x Reference

Generic reference for Airflow 3.x. For biocloud-specific DAG patterns, deployment, and cluster configs, see [[airflow-dag]].

> **When answering questions like "can Airflow do X?", "in which version was Y added?", or "should we upgrade from 3.2.1?"** — fetch the live release notes before answering. The version table below gives quick orientation; the live page has the definitive detail:
> `https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html`

---

## Release Notes — 3.x Version Highlights

Full release notes: https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html

Use this table for quick orientation. For specific "was X available in 3.2.1?" questions, fetch the live page above.

### Airflow 3.3.0 (2026-07-06)

| Category | Change |
|---|---|
| **Assets** | Asset Partitioning — DAGs and tasks can now produce/consume partitioned assets |
| **State Store** | New Task and Asset State Store for sharing state between tasks without XCom |
| **Retries** | Pluggable Retry Policies — customize retry behavior per task type |
| **Multi-language** | Java and Go Task SDK (Language Task SDKs — AIP) |
| **DAG Bundles** | DAG Bundle Version on Clear/Rerun/Backfill; provider example DAGs as dedicated bundles |
| **Logging** | Remote logging resolution decoupled from `airflow.logging_config` |
| **Metrics** | OpenTelemetry timer metrics now use Histogram; DAG-processing metric tagged |
| **UI** | New Deadlines page under Browse |

### Airflow 3.2.0 (2026-04-07)

| Category | Change |
|---|---|
| **Performance** | Rendered Task Instance Fields cleanup ~42x faster for DAGs with many mapped tasks |
| **Performance** | Replace per-run TI summary requests with single NDJSON stream |
| **Performance** | Reduce API server memory by eliminating SerializedDAG loads on task start |
| **API server** | Gunicorn support with zero-downtime worker recycling |
| **Logging** | Structured JSON logging for API server output |
| **Python** | Python 3.14 support added |
| **Operators** | `PythonOperator` now supports async callables |
| **Operators** | `@continuous` schedule: `start_date` is now optional |
| **Operators** | Operator-level `render_template_as_native_obj` override |
| **Retries** | Numeric multiplier values for `retry_exponential_backoff` parameter |
| **Breaking** | SQLAlchemy upgraded to 2.0 |
| **Breaking** | Methods removed from `PriorityWeightStrategy` and `TaskInstance` |
| **Breaking** | `--conn-id` option removed from `airflow connections list` |
| **Breaking** | MySQL client removed from container images |
| **Breaking** | Methods removed from `DagBag` |

### Airflow 3.1.0 (2025-09-25)

| Category | Change |
|---|---|
| **Human in the Loop** | New task approval workflow (HITL) — tasks can pause and wait for human approval |
| **Task SDK** | Task SDK decoupled for independent upgrades (can update SDK separately from core) |
| **Alerting** | Deadline Alerts — monitor DAG completion deadlines |
| **UI** | Internationalization (multi-language support) |
| **UI** | React Plugin System (AIP-68) — new plugin architecture |
| **Scheduling** | Inference Execution (synchronous DAGs) |
| **Trigger rules** | New rule: `ALL_DONE_MIN_ONE_SUCCESS` |
| **Logging** | Airflow now uses `structlog` everywhere |
| **Python** | Python 3.13 support added; Python 3.9 support removed |
| **Breaking** | Deprecated config options removed; API behavior changes; Task SDK interface changes |
| **Breaking** | Default API server workers reduced to 1 |

### Airflow 3.0.0 (2025-04-22)

| Category | Change |
|---|---|
| **Architecture** | Task Execution API + Task SDK (AIP-72) — workers no longer access DB directly |
| **Architecture** | Standalone DAG Processor required (`airflow dag-processor`) |
| **Architecture** | React UI rewrite (AIP-38, AIP-84) |
| **Executors** | Edge Executor (AIP-69) for distributed lightweight execution |
| **Backfills** | Scheduler-managed Backfills (AIP-78) |
| **DAGs** | DAG Versioning (AIP-66) |
| **DAGs** | New stable authoring interface: `airflow.sdk` (replaces `airflow.decorators`, `airflow.models.*`) |
| **Scheduling** | Asset-Based Scheduling (AIP-74/75) — Datasets renamed to Assets |
| **Scheduling** | `catchup_by_default` changed to `False` |
| **Scheduling** | `create_cron_data_intervals` changed to `False` (CronTriggerTimetable is now default) |
| **Auth** | Default auth manager changed from FAB to **SimpleAuthManager** |
| **Auth** | OAuth redirect URL changed: `/oauth-authorized/<p>` → `/auth/oauth-authorized/<p>` |
| **REST API** | `/api/v1` removed; use `/api/v2` (FastAPI) |
| **Breaking** | `execution_date` removed from context — use `logical_date` |
| **Breaking** | XCom `pull()` without `task_ids` now pulls from current task only |
| **Breaking** | SequentialExecutor removed; SubDAGs removed; SLAs removed |
| **Breaking** | `fail_stop` parameter renamed to `fail_fast` |
| **Breaking** | Plugins can no longer add Executors, Operators, or Hooks |
| **Breaking** | Minimum Python version: 3.10 |

---

## 2.x → 3.x Breaking Changes

### Architecture

| Area | Airflow 2.x | Airflow 3.x |
|---|---|---|
| DB access | Workers hit DB directly | Workers go through API server only |
| Webserver | `airflow webserver` | `airflow api-server` |
| DAG processor | Embedded in scheduler | Must be started separately: `airflow dag-processor` |
| REST API | `/api/v1` (Flask) | `/api/v2` (FastAPI) |
| Auth default | FAB (Flask-AppBuilder) | **SimpleAuthManager** (no OAuth by default) |
| OAuth redirect URL | `/oauth-authorized/<provider>` | `/auth/oauth-authorized/<provider>` |

### Removed features

- **SubDAGs** → use TaskGroups or Asset-based scheduling
- **Sequential Executor** → use LocalExecutor (works with SQLite for local dev)
- **SLAs** → replaced by Deadline Alerts
- **CeleryKubernetesExecutor / LocalKubernetesExecutor** → Multiple Executor Configuration
- **`/api/v1`** → use `/api/v2`
- **`execution_date`** template var → use `logical_date`
- Removed template vars: `tomorrow_ds`, `yesterday_ds`, `prev_ds`, `next_ds`, `prev_execution_date`, `next_execution_date`

### Import path changes (Airflow 3.x)

Operators like `BashOperator`, `PythonOperator`, `ExternalTaskSensor`, `FileSensor` moved to `apache-airflow-providers-standard`. Install it explicitly.

| Old path | New path |
|---|---|
| `airflow.decorators.dag` | `airflow.sdk.dag` |
| `airflow.decorators.task` | `airflow.sdk.task` |
| `airflow.models.dag.DAG` | `airflow.sdk.DAG` |
| `airflow.models.baseoperator.BaseOperator` | `airflow.sdk.BaseOperator` |
| `airflow.datasets.Dataset` | `airflow.sdk.Asset` |
| `airflow.datasets.DatasetAlias` | `airflow.sdk.AssetAlias` |
| `airflow.models.variable.Variable` | `airflow.sdk.Variable` |
| `airflow.models.connection.Connection` | `airflow.sdk.Connection` |
| `airflow.utils.context.Context` | `airflow.sdk.Context` |
| `airflow.utils.task_group.TaskGroup` | `airflow.sdk.TaskGroup` |

Use ruff to auto-fix: `ruff check dags/ --select AIR301 --fix`

### Key behavioral changes

- `catchup_by_default` is now `False`
- `create_cron_data_intervals` is now `False` (uses `CronTriggerTimetable` instead of `CronDataIntervalTimetable`) — only affects DAGs with bare cron strings in `schedule=`
- **XCom pull**: `xcom_pull()` without `task_ids` now only pulls from the **current task** (Airflow 2 pulled from any task); always pass `task_ids` explicitly
- **Manual DAG run `data_interval`**: do not assume `data_interval_start/end` equals `logical_date` for manual runs; use `logical_date` explicitly when you need the trigger date
- Direct DB access from task code is blocked; use the Airflow Python Client or Task SDK APIs instead
- SSO using `webserver_config.py`: replace `from airflow.www.security import AirflowSecurityManager` with `from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride`

---

## Configuration

### Format

All config can be set via env vars using `AIRFLOW__<SECTION>__<KEY>` (double underscores). Values set via env vars take precedence over `airflow.cfg`.

```bash
# Example
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://user:pass@host/db
export AIRFLOW__CORE__FERNET_KEY=your-fernet-key
```

### [core]

| Key | Default | Notes |
|---|---|---|
| `executor` | `SequentialExecutor` (removed in 3.x → `LocalExecutor`) | `LocalExecutor`, `CeleryExecutor`, `KubernetesExecutor` |
| `dags_folder` | `$AIRFLOW_HOME/dags` | Path to DAG files |
| `fernet_key` | — | **Required**. Encrypt Variable/Connection passwords. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `load_examples` | `True` | Set `False` in production |
| `default_timezone` | `utc` | Timezone for naive datetimes |
| `parallelism` | `32` | Max tasks running simultaneously across all DAGs |
| `max_active_tasks_per_dag` | `16` | Max active tasks per DAG run |
| `max_active_runs_per_dag` | `16` | Max concurrent DAG runs per DAG |
| `dags_are_paused_at_creation` | `True` | New DAGs start paused |
| `default_task_retries` | `0` | Default retry count for tasks |
| `default_task_retry_delay` | `300` | Seconds between retries |
| `default_task_execution_timeout` | `None` | Timeout per task |
| `xcom_backend` | `airflow.sdk.bases.xcom.BaseXCom` | Override for custom XCom storage |
| `auth_manager` | `airflow.auth.managers.simple.SimpleAuthManager` | Set to FAB class for OAuth |
| `hide_sensitive_var_conn_fields` | `True` | Masks sensitive fields in logs |
| `sensitive_var_conn_names` | — | Comma-separated extra keywords to mask |
| `simple_auth_manager_all_admins` | `True` | When SimpleAuthManager: all users are Admin |
| `simple_auth_manager_passwords_file` | — | Path to bcrypt password file for SimpleAuthManager |
| `test_connection` | `Disabled` | Enable connection testing in UI/API |

### [api] (replaces [webserver] in Airflow 3.x)

| Key | Default | Notes |
|---|---|---|
| `base_url` | `http://localhost:8080` | Public URL of Airflow (used in links) |
| `host` | `0.0.0.0` | API server bind host |
| `port` | `8080` | API server bind port |
| `workers` | `4` | Number of gunicorn workers |
| `worker_timeout` | `120` | Worker timeout (seconds) |
| `secret_key` | auto-generated | Flask/JWT secret key — **set explicitly and share across all components** |
| `expose_config` | `Non-sensitive-only` | `True`/`False`/`Non-sensitive-only` |
| `expose_stacktrace` | `True` | Show stack traces in error responses |
| `enable_swagger_ui` | `True` | Expose `/api/v2/ui` |
| `ssl_cert` | — | Path to SSL cert |
| `ssl_key` | — | Path to SSL key |
| `instance_name` | — | Display name in UI header |

### [api_auth] (JWT for API server)

| Key | Default | Notes |
|---|---|---|
| `jwt_secret` | — | Symmetric JWT secret (share across API server + scheduler) |
| `jwt_private_key_path` | — | Use instead of `jwt_secret` for RS256 asymmetric JWT |
| `jwt_algorithm` | `HS512` | JWT signing algorithm |
| `jwt_expiration_time` | `3600` | JWT lifetime in seconds (1 hour) |
| `jwt_cli_expiration_time` | `86400` | JWT lifetime for CLI tokens |
| `trusted_jwks_url` | — | URL of external JWKS endpoint (for federated auth) |

### [database]

| Key | Default | Notes |
|---|---|---|
| `sql_alchemy_conn` | `sqlite:///$AIRFLOW_HOME/airflow.db` | **Must change for production**. PostgreSQL recommended |
| `sql_alchemy_pool_size` | `5` | SQLAlchemy connection pool size |
| `sql_alchemy_max_overflow` | `10` | Pool overflow |
| `sql_alchemy_pool_recycle` | `1800` | Recycle connections after N seconds |
| `sql_alchemy_pool_pre_ping` | `True` | Test connections before use |

PostgreSQL example:
```
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
```

### [dag_processor] (new in Airflow 3.x)

| Key | Default | Notes |
|---|---|---|
| `min_file_process_interval` | `30` | Minimum seconds between re-parsing the same DAG file |
| `parsing_processes` | `2` | Number of parallel DAG parsing processes |
| `dag_file_processor_timeout` | `50` | Timeout for parsing a single DAG file |
| `dag_bundle_config_list` | — | JSON list of DAG bundle configs |
| `dag_bundle_storage_path` | — | Where bundles are stored |

### [scheduler]

| Key | Default | Notes |
|---|---|---|
| `catchup_by_default` | `False` | Global default for DAG `catchup` param |
| `create_cron_data_intervals` | `False` | Use `CronDataIntervalTimetable` instead of `CronTriggerTimetable` |
| `scheduler_heartbeat_sec` | `5` | Scheduler heartbeat interval |
| `max_dagruns_to_create_per_loop` | `10` | Max DAG runs created per scheduling loop |
| `max_tis_per_query` | `512` | Max task instances per DB query |
| `use_row_level_locking` | `True` | PostgreSQL row-level locking |

### [secrets] (secret backend)

| Key | Default | Notes |
|---|---|---|
| `backend` | — | e.g. `airflow.providers.hashicorp.secrets.vault.VaultBackend` |
| `backend_kwargs` | `{}` | JSON kwargs passed to backend class |
| `use_cache` | `True` | Cache secret lookups |
| `cache_ttl_seconds` | `300` | Cache TTL |

HashiCorp Vault example:
```
AIRFLOW__SECRETS__BACKEND=airflow.providers.hashicorp.secrets.vault.VaultBackend
AIRFLOW__SECRETS__BACKEND_KWARGS={"connections_path": "airflow/connections", "variables_path": "airflow/variables", "url": "https://vault.example.com"}
```

### [smtp]

| Key | Default | Notes |
|---|---|---|
| `smtp_host` | `localhost` | SMTP server host |
| `smtp_port` | `25` | SMTP port (587 for STARTTLS, 465 for SSL) |
| `smtp_starttls` | `True` | Use STARTTLS |
| `smtp_ssl` | `False` | Use SSL (use with port 465) |
| `smtp_mail_from` | `airflow@example.com` | Sender address |
| `smtp_retry_limit` | `5` | Retry count on failure |
| `smtp_timeout` | `30` | Connection timeout |

Note: SMTP user/password are stored as a Connection (`smtp_default`), not in config.

### [email]

| Key | Default | Notes |
|---|---|---|
| `email_backend` | `airflow.providers.smtp.notifications.smtp.SmtpNotifier` | Email sending class |
| `email_conn_id` | `smtp_default` | Connection ID for SMTP |
| `from_email` | — | Override sender address |
| `default_email_on_failure` | `True` | Send email on task failure |
| `default_email_on_retry` | `True` | Send email on retry |

### [logging]

| Key | Default | Notes |
|---|---|---|
| `logging_level` | `INFO` | Root logging level |
| `base_log_folder` | `$AIRFLOW_HOME/logs` | Local log storage path |
| `remote_logging` | `False` | Enable remote log storage |
| `remote_base_log_folder` | — | e.g. `s3://my-bucket/airflow-logs` |
| `remote_log_conn_id` | `aws_default` | Connection for remote log storage |
| `json_logs` | `False` | Output logs as JSON |
| `colored_console_log` | `True` | Color in console output |

### [celery] (only if using CeleryExecutor)

| Key | Default | Notes |
|---|---|---|
| `broker_url` | `redis://redis:6379/0` | Message broker URL |
| `result_backend` | `db+postgresql://...` | Celery result backend (use same DB as Airflow) |
| `worker_concurrency` | `16` | Tasks per worker process |

---

## Variables

Variables are key-value pairs stored globally. Use for runtime config, not for passing data between tasks (use XComs for that).

### Accessing in Python

```python
from airflow.sdk import Variable

# String value
value = Variable.get("my_key")

# With default
value = Variable.get("my_key", default_var="fallback")

# JSON deserialization
config = Variable.get("my_config", deserialize_json=True)

# Via task context
from airflow.sdk import get_current_context

def my_task():
    ctx = get_current_context()
    raw = ctx["var"]["value"].get("my_key")
    parsed = ctx["var"]["json"].get("my_json_key")
```

### Using in Jinja templates

```python
# In operator templates:
bash_command="{{ var.value.my_key }}"
bash_command="{{ var.json.my_config.some_field }}"
```

### Environment variable override

```bash
# Naming: AIRFLOW_VAR_<KEY_UPPERCASE>
export AIRFLOW_VAR_FOO=BAR
export AIRFLOW_VAR_FOO_BAZ='{"hello":"world"}'
```

**Important**: env-var variables are NOT shown in the UI/CLI (resolved at runtime on the worker only). Set in the DB if you need UI visibility.

### Securing Variables

- Variables are encrypted at rest with Fernet (`[core] fernet_key`)
- Mark a variable sensitive by including a keyword from `[core] sensitive_var_conn_names` in its name (e.g. `db_password`, `api_secret`) — values are masked in logs
- For production secrets: use a Secrets Backend (Vault, AWS SSM) instead of the DB

### CLI

```bash
airflow variables get my_key
airflow variables set my_key my_value
airflow variables set my_json_key '{"a":1}' --json
airflow variables delete my_key
airflow variables list
airflow variables export /path/to/vars.json  # DB vars only, not env vars
airflow variables import /path/to/vars.json
```

---

## Connections

Store credentials for external systems. Lookup priority: environment variables → secrets backend → database.

### Environment variable format

```bash
# Naming: AIRFLOW_CONN_<CONN_ID_UPPERCASE>
# Value: URI or JSON

# URI format
export AIRFLOW_CONN_MY_DB='postgresql://user:pass@host:5432/mydb'

# JSON format (preferred for complex connections)
export AIRFLOW_CONN_MY_S3='{
  "conn_type": "aws",
  "login": "ACCESS_KEY_ID",
  "password": "SECRET_ACCESS_KEY",
  "extra": {"region_name": "eu-west-1"}
}'
```

**Note**: env-var connections are NOT shown in the UI (resolved on the worker at runtime).

### URI format

```
conn-type://login:password@host:port/schema?param1=val1&param2=val2
```

Special characters in password must be URL-encoded (e.g. `/` → `%2F`). Use `Connection.get_uri()` to generate URIs safely.

### Generating a URI from Python

```python
from airflow.sdk import Connection

c = Connection(
    conn_id="my_db",
    conn_type="postgresql",
    host="myhost.com",
    login="user",
    password="p@ss/word",
    port=5432,
    schema="mydb",
)
print(f"AIRFLOW_CONN_MY_DB='{c.get_uri()}'")

# Or get JSON:
print(f"AIRFLOW_CONN_MY_DB='{c.as_json()}'")
```

### CLI

```bash
airflow connections add my_conn --conn-json '{"conn_type": "http", "host": "example.com"}'
airflow connections get my_conn
airflow connections list
airflow connections delete my_conn
airflow connections export /path/to/conns.json
airflow connections test my_conn  # requires AIRFLOW__CORE__TEST_CONNECTION=Enabled
```

### Common connection types

| Type | conn_type string | Notes |
|---|---|---|
| PostgreSQL | `postgres` | `login`, `password`, `host`, `port`, `schema` |
| MySQL/MSSQL | `mssql` | `login`, `password`, `host`, `port`, `schema` |
| S3 / AWS | `aws` | `login`=access key, `password`=secret, `extra`={region_name} |
| HTTP / REST | `http` | `host`, optional `login`/`password` |
| Databricks | `databricks` | `host`=workspace URL, `password`=token |
| SMTP | `smtp` | `host`, `port`, `login`, `password` |
| Hive | `hive_cli` | — |

---

## Authentication & OAuth

### Auth Managers (Airflow 3.x)

Airflow 3.x uses a pluggable auth manager set via `[core] auth_manager`.

| Manager | Class | Notes |
|---|---|---|
| **SimpleAuthManager** (default) | `airflow.auth.managers.simple.SimpleAuthManager` | Username/password via CLI or config file. All users Admin by default. No OAuth. |
| **FAB Auth Manager** | `airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager` | Full RBAC, OAuth2/OIDC, LDAP. Requires `apache-airflow-providers-fab`. |

### SimpleAuthManager

Default in Airflow 3.x. Suitable for single-team or dev deployments.

```ini
[core]
auth_manager = airflow.auth.managers.simple.SimpleAuthManager
simple_auth_manager_all_admins = True  # everyone is admin

# Or: use a password file
simple_auth_manager_all_admins = False
simple_auth_manager_passwords_file = /path/to/passwords.json
```

### FAB Auth Manager (required for OAuth/OIDC/LDAP)

Install the provider:
```bash
pip install apache-airflow-providers-fab
```

Enable it:
```ini
[core]
auth_manager = airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager
```

#### Roles (RBAC)

| Role | Capabilities |
|---|---|
| Admin | Full access, manage users |
| Op | DAG runs, connections, variables, pools |
| User | View/trigger DAGs, read connections/variables |
| Viewer | Read-only access |
| Public | Unauthenticated access (set `AUTH_ROLE_PUBLIC` in webserver_config.py) |

#### Creating users (FAB)

```bash
airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com
```

#### `webserver_config.py`

OAuth and LDAP are configured in `$AIRFLOW_HOME/webserver_config.py` (location configurable via `[fab] config_file`).

```python
from flask_appbuilder.security.manager import AUTH_DB, AUTH_OAUTH, AUTH_LDAP, AUTH_REMOTE_USER

# Default: database auth
AUTH_TYPE = AUTH_DB
```

---

### OAuth2 / SSO with FAB Auth Manager

**Step 1**: Set auth manager to FAB (see above).

**Step 2**: Set `AUTH_TYPE = AUTH_OAUTH` in `webserver_config.py`:

```python
from flask_appbuilder.security.manager import AUTH_OAUTH
AUTH_TYPE = AUTH_OAUTH
```

**Step 3**: Configure `OAUTH_PROVIDERS` list.

**Note on Airflow 3.x redirect URL**: OAuth callback URL is now `/auth/oauth-authorized/<provider>` (not `/oauth-authorized/<provider>` as in 2.x). Update your OAuth app registrations accordingly.

---

#### Azure AD (Entra ID)

```python
from flask_appbuilder.security.manager import AUTH_OAUTH
from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_ROLES_SYNC_AT_LOGIN = True

AUTH_ROLES_MAPPING = {
    "airflow-admins": ["Admin"],
    "airflow-ops": ["Op"],
    "airflow-users": ["User"],
    "airflow-viewers": ["Viewer"],
}

OAUTH_PROVIDERS = [
    {
        "name": "azure",
        "icon": "fa-windows",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "<your-client-id>",
            "client_secret": "<your-client-secret>",
            "api_base_url": "https://graph.microsoft.com/v1.0/",
            "client_kwargs": {"scope": "openid email profile"},
            "request_token_url": None,
            "access_token_url": "https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token",
            "authorize_url": "https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize",
        },
    }
]

class AzureAdSecurityManager(FabAirflowSecurityManagerOverride):
    def get_oauth_user_info(self, provider, response):
        if provider != "azure":
            return {}
        groups = response.get("groups", [])
        roles = response.get("roles", [])
        return {
            "username": response.get("preferred_username"),
            "email": response.get("email"),
            "first_name": response.get("given_name"),
            "last_name": response.get("family_name"),
            "role_keys": groups or roles,
        }

SECURITY_MANAGER_CLASS = AzureAdSecurityManager
```

**Azure app registration requirements:**
- Redirect URI: `https://<your-airflow-url>/auth/oauth-authorized/azure`
- Enable `groupMembershipClaims` in the app manifest (set to `"SecurityGroup"` or `"All"`) to get group claims in the token
- For large tenants (>200 groups), group claims may be omitted from the token — query Microsoft Graph instead via `api_base_url`
- Optional claims → add `groups` claim to ID token and/or access token

**Via env vars (simpler, no `webserver_config.py` for just provider setup):**
```bash
export AIRFLOW__FAB__OAUTH_PROVIDERS='[{
  "name": "azure",
  "icon": "fa-circle",
  "token_key": "access_token",
  "remote_app": {
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "api_base_url": "https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/",
    "request_token_url": null,
    "access_token_url": "https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token",
    "authorize_url": "https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize",
    "client_kwargs": {"scope": "openid email profile"}
  }
}]'
```

Note: `AUTH_TYPE = AUTH_OAUTH` still requires `webserver_config.py` — env vars cannot replace this.

---

#### Keycloak (OpenID Connect)

```python
import logging
from base64 import b64decode

import jwt
import requests
from cryptography.hazmat.primitives import serialization
from flask_appbuilder.security.manager import AUTH_OAUTH

from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride

log = logging.getLogger(__name__)

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_USER_REGISTRATION_ROLE = "Viewer"

OIDC_ISSUER = "https://sso.example.com/realms/airflow"

AUTH_ROLES_MAPPING = {
    "Viewer": ["Viewer"],
    "User": ["User"],
    "Op": ["Op"],
    "Admin": ["Admin"],
}

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "airflow",
            "client_secret": "<your-client-secret>",
            "server_metadata_url": f"{OIDC_ISSUER}/.well-known/openid-configuration",
            "api_base_url": f"{OIDC_ISSUER}/protocol/openid-connect",
            "client_kwargs": {"scope": "email profile"},
            "access_token_url": f"{OIDC_ISSUER}/protocol/openid-connect/token",
            "authorize_url": f"{OIDC_ISSUER}/protocol/openid-connect/auth",
            "request_token_url": None,
        },
    }
]

req = requests.get(OIDC_ISSUER)
key_der = b64decode(req.json()["public_key"].encode())
public_key = serialization.load_der_public_key(key_der)

class KeycloakSecurityManager(FabAirflowSecurityManagerOverride):
    def get_oauth_user_info(self, provider, response):
        if provider == "keycloak":
            token = response["access_token"]
            me = jwt.decode(token, public_key, algorithms=["RS256"], audience="account")
            groups = me.get("realm_access", {}).get("roles", ["Viewer"])
            return {
                "username": me.get("preferred_username"),
                "email": me.get("email"),
                "first_name": me.get("given_name"),
                "last_name": me.get("family_name"),
                "role_keys": groups,
            }
        return {}

SECURITY_MANAGER_CLASS = KeycloakSecurityManager
```

**Keycloak setup:**
- Create an `airflow` client in your realm (type: OpenID Connect)
- Redirect URI: `https://<your-airflow-url>/auth/oauth-authorized/keycloak`
- Enable "Standard flow" (authorization code flow)
- Add a mapper for realm roles (`realm_access.roles` in the token)
- Create roles matching your `AUTH_ROLES_MAPPING` keys

**Install required packages:** `pip install PyJWT cryptography requests`

---

#### LDAP

```python
from flask_appbuilder.security.manager import AUTH_LDAP

AUTH_TYPE = AUTH_LDAP
AUTH_LDAP_SERVER = "ldap://ldap.example.com"
AUTH_LDAP_SEARCH = "dc=example,dc=com"
AUTH_LDAP_SEARCH_FILTER = "(memberOf=cn=airflow-users,ou=groups,dc=example,dc=com)"
AUTH_LDAP_UID_FIELD = "sAMAccountName"
AUTH_LDAP_BIND_USER = "cn=airflow,ou=service-accounts,dc=example,dc=com"
AUTH_LDAP_BIND_PASSWORD = "bind-password"
AUTH_LDAP_USE_TLS = True

AUTH_ROLES_MAPPING = {
    "cn=airflow-admins,ou=groups,dc=example,dc=com": ["Admin"],
    "cn=airflow-users,ou=groups,dc=example,dc=com": ["User"],
}
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Viewer"
```

---

## DAG Authoring (TaskFlow API)

### Minimal DAG structure

```python
from datetime import datetime
from airflow.sdk import dag, task

@dag(
    dag_id="my_dag",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["example"],
)
def my_dag():
    @task
    def extract():
        return {"key": "value"}

    @task
    def transform(data: dict):
        return data["key"].upper()

    @task
    def load(value: str):
        print(value)

    load(transform(extract()))

my_dag()
```

### Scheduling options

```python
# Cron
schedule="0 6 * * *"
schedule="@daily"
schedule=None               # Manual trigger only

# Asset-based (formerly Dataset-based)
from airflow.sdk import Asset
my_asset = Asset("s3://my-bucket/output/data.csv")

@dag(schedule=my_asset)
def consumer_dag(): ...

# Combined time + asset
from airflow.timetables.assets import AssetOrTimeSchedule
from airflow.timetables.trigger import CronTriggerTimetable
schedule = AssetOrTimeSchedule(
    timetable=CronTriggerTimetable("0 6 * * *", timezone="UTC"),
    assets=[my_asset],
)
```

### Context variables

| Variable | Type | Notes |
|---|---|---|
| `logical_date` | `datetime` | The logical date of the DAG run (replaces `execution_date`) |
| `ds` | `str` | `logical_date` as `YYYY-MM-DD` |
| `ts` | `str` | `logical_date` as ISO timestamp |
| `run_id` | `str` | Unique DAG run ID |
| `dag_run` | `DagRun` | Full DAG run object |
| `params` | `dict` | DAG/task params |
| `var.value` | mapping | Variable values (raw string) |
| `var.json` | mapping | Variable values (JSON-deserialized) |
| `conn` | mapping | Connections |
| `data_interval_start` | `datetime` | Interval start (may differ from `logical_date` on manual runs) |
| `data_interval_end` | `datetime` | Interval end |

**Removed in Airflow 3**: `execution_date`, `prev_ds`, `next_ds`, `tomorrow_ds`, `yesterday_ds`

### Dynamic task mapping

```python
@task
def process(item: str):
    return item.upper()

results = process.expand(item=["a", "b", "c"])

# From upstream output
@task
def get_items():
    return ["x", "y", "z"]

process.expand(item=get_items())
```

### XComs

```python
@task
def producer():
    return "my_value"

@task
def consumer(value: str):
    print(value)

# TaskFlow wires automatically:
consumer(producer())

# Manual pull — always specify task_ids in Airflow 3:
value = context["ti"].xcom_pull(task_ids="producer", key="return_value")
```

### Retries and timeouts

```python
@task(
    retries=3,
    retry_delay=timedelta(minutes=5),
    retry_exponential_backoff=True,
    execution_timeout=timedelta(hours=1),
)
def my_task(): ...
```

### Trigger rules

```python
from airflow.utils.trigger_rule import TriggerRule

@task(trigger_rule=TriggerRule.ALL_DONE)         # Run even if upstreams failed
@task(trigger_rule=TriggerRule.ONE_SUCCESS)      # Run if at least one upstream succeeded
@task(trigger_rule=TriggerRule.ALL_FAILED)       # Run only if all upstreams failed
@task(trigger_rule=TriggerRule.ALL_DONE_MIN_ONE_SUCCESS)  # Added in 3.1
```

### Emitting Asset events

```python
from airflow.sdk import Asset, task

my_asset = Asset("s3://my-bucket/output/data.parquet")

@task(outlets=[my_asset])
def write_data():
    pass  # Airflow marks the asset updated on task success
```

---

## Best Practices

Full reference: https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html

### Task design

**Idempotency** — tasks must produce the same result on every run (including retries). Key rules:
- Replace `INSERT` with `UPSERT` to avoid duplicate rows on retry
- Always read/write to specific **partitions** — never "latest available data". Use `data_interval_start` as the partition key
- Never use `datetime.now()` for critical computations inside tasks (it changes on each run). Only use it for logging

**Treat tasks like DB transactions** — they should never produce incomplete results.

### Top-level Python code (critical for performance)

The scheduler re-parses every DAG file at minimum every `min_file_process_interval` seconds. Any code at the top level of a DAG file runs on every parse.

**Never put at the top level:**
- `Variable.get()` calls (network + DB call on every parse)
- Heavy imports (`pandas`, `torch`, `tensorflow`)
- Database access, networking, or expensive API calls

```python
# BAD — runs on every DAG parse, slows the scheduler
import pandas
foo_var = Variable.get("foo")

# GOOD — deferred to task execution time
@task
def my_task():
    import pandas           # local import: only at task run
    foo = Variable.get("foo")   # only at task run
    ...

# GOOD — Jinja defers variable access to task runtime
BashOperator(bash_command="echo {{ var.value.foo }}")
```

**Check for top-level code:** run `python my_dag.py` — any printed output is top-level code.

### Airflow Variables in DAGs

- **Prefer Jinja** (`{{ var.value.my_key }}`) over `Variable.get()` at the module level — Jinja is evaluated at task run, not at DAG parse
- If you must call `Variable.get()` in a timetable or initializer, delay the call until execution time (not `__init__`)
- Enable variable caching with a TTL if top-level Variable access is unavoidable

### Communication between tasks

| Data size | Approach |
|---|---|
| Small (strings, IDs, counts) | XCom |
| Large (DataFrames, files) | Remote storage (S3, HDFS) — push the path to XCom |
| Credentials | Connections — never store passwords in task code |

Never store files on the local filesystem with distributed executors (Celery, Kubernetes) — workers may run on different machines.

### DAG complexity and scheduler performance

1. **Optimize DAG load time** — biggest single impact. Apply top-level code rules above.
2. **Simplify structure** — linear chains (A→B→C) have less scheduling overhead than deeply nested trees.
3. **Split large DAG files** — one file is parsed by one FileProcessor; split generated DAGs if UI feels slow.
4. **Tune parse intervals** if seeing long delays after deploying changes:
   - `[dag_processor] min_file_process_interval`
   - `[dag_processor] parsing_processes`
   - `[dag_processor] refresh_interval`

### Watcher pattern (ensure DAG fails on task failure with teardown tasks)

```python
from airflow.utils.trigger_rule import TriggerRule

@task(trigger_rule=TriggerRule.ONE_FAILED)
def watcher():
    raise Exception("A task failed — failing the DAG run")

# Wire watcher as downstream of ALL tasks
[task_a, task_b, teardown_task] >> watcher()
```

Trigger rules only check **direct** upstream tasks, not all upstream tasks.

### Testing DAGs

**Quick load test:**
```bash
python your_dag_file.py          # should complete without errors
time python your_dag_file.py     # measure parse time
```

**Unit test for DAG structure:**
```python
import pytest
from airflow.dag_processing.dagbag import DagBag

def test_dag_loaded():
    dagbag = DagBag()
    dag = dagbag.get_dag("my_dag_id")
    assert dagbag.import_errors == {}
    assert dag is not None
```

**Mocking Variables/Connections in tests:**
```python
from unittest import mock

with mock.patch.dict("os.environ", AIRFLOW_VAR_MY_KEY="test-value"):
    assert "test-value" == Variable.get("my_key")

conn = Connection(conn_type="http", host="test-host")
with mock.patch.dict("os.environ", AIRFLOW_CONN_MY_CONN=conn.get_uri()):
    assert "test-host" == Connection.get("my_conn").host
```

### Handling conflicting Python dependencies

| Approach | When to use |
|---|---|
| `@task.virtualenv(requirements=[...])` | Simplest — creates a virtualenv per task at runtime |
| `ExternalPythonOperator` | Pre-existing Python env with the right deps |
| `DockerOperator` / `KubernetesPodOperator` | Full isolation — separate container per task |
| Celery queues + separate images | Complex multi-dep scenarios |

### Upgrades

1. Backup the metadata database before any upgrade
2. Run `airflow db clean` to prune old data if the DB is large
3. Pause individual DAGs rather than the whole scheduler — allows testing specific DAGs first after upgrade
4. Add integration test DAGs (that hit S3, the data warehouse, etc.) and run them first after upgrade before unpausing production DAGs
5. Run `airflow config update --fix` when upgrading major versions

---

## Providers Reference

### Databricks (`apache-airflow-providers-databricks`)

Connection: `conn_type="databricks"`, `host`=workspace URL, `password`=token.

```python
from airflow.providers.databricks.operators.databricks import (
    DatabricksRunNowOperator,
    DatabricksSubmitRunOperator,
)

DatabricksRunNowOperator(
    task_id="run_job",
    databricks_conn_id="databricks_default",
    job_id=12345,
    notebook_params={"param_key": "value"},
)
```

### MSSQL (`apache-airflow-providers-microsoft-mssql`)

Connection: `conn_type="mssql"`, `host`, `port=1433`, `login`, `password`, `schema`=database name.

```python
from airflow.providers.microsoft.mssql.hooks.mssql import MsSqlHook

hook = MsSqlHook(mssql_conn_id="mssql_default")
df = hook.get_pandas_df("SELECT * FROM my_table WHERE date = %(date)s", parameters={"date": "2025-01-01"})
```

### SMTP (`apache-airflow-providers-smtp`)

Connection: `conn_type="smtp"`, `host`, `port`, `login`, `password`.

```python
from airflow.providers.smtp.operators.smtp import EmailOperator

EmailOperator(
    task_id="send_email",
    to=["recipient@example.com"],
    subject="Airflow: {{ dag.dag_id }} completed",
    html_content="<p>Run {{ run_id }} done.</p>",
    conn_id="smtp_default",
)
```

---

## Startup Commands (Airflow 3.x)

```bash
airflow db migrate            # Initialize / migrate DB
airflow api-server            # API server (replaces webserver)
airflow scheduler             # Scheduler
airflow dag-processor         # DAG processor (required separately in 3.x)
airflow triggerer             # Triggerer (deferrable operators)
airflow celery worker         # Celery worker (CeleryExecutor only)
airflow config update --fix   # Fix config when upgrading versions
```

---

## Secrets Backends

### HashiCorp Vault

```bash
AIRFLOW__SECRETS__BACKEND=airflow.providers.hashicorp.secrets.vault.VaultBackend
AIRFLOW__SECRETS__BACKEND_KWARGS='{"connections_path": "airflow/connections", "variables_path": "airflow/variables", "url": "https://vault.example.com", "auth_type": "token", "token": "your-vault-token"}'
```

### AWS SSM Parameter Store

```bash
AIRFLOW__SECRETS__BACKEND=airflow.providers.amazon.aws.secrets.systems_manager.SystemsManagerParameterStoreBackend
AIRFLOW__SECRETS__BACKEND_KWARGS='{"connections_prefix": "/airflow/connections", "variables_prefix": "/airflow/variables"}'
```

---

## Related Skills

- [[airflow-dag]]: biocloud-specific DAG patterns, CI placeholders, DAGConfig usage, Databricks cluster configs, deployment to S3
