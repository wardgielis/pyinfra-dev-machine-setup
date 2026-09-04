---
name: gitlab-cicd
description: Use when writing, modifying, or troubleshooting .gitlab-ci.yml pipelines. Always check the GitLab Component Catalog first before building custom CI logic. Covers components, stages, rules, artifacts, caching, YAML anchors, and common patterns.
metadata:
  review_after: "2027-01-15"
  docs_url: "https://docs.gitlab.com/ci/"
---

# GitLab CI/CD

**Related skills**: [[opentofu-gitlab-component]] for OpenTofu-specific CI patterns; [[glab-cli]] for interacting with pipelines from the CLI; [[naturalis-opentofu]] for Vault OIDC auth in CI.

---

## Rule #1: Component Registry First

**Before writing any custom CI job logic**, check the GitLab Component Catalog:

```
https://gitlab.com/explore/catalog
```

A well-maintained component saves days of implementation and is battle-tested across many pipelines. Only build custom logic when no suitable component exists.

**How to evaluate a component**:
1. Check the last release date — avoid components with no release in >12 months and open bugs
2. Read the README for `inputs:` documentation
3. Check the issue tracker for unresolved critical bugs
4. Prefer GitLab-authored components (`gitlab.com/components/`) over third-party where equivalent

---

## Notable Official Components

All from `gitlab.com/components/` — include via `$CI_SERVER_FQDN` (not hardcoded `gitlab.com`).

### OpenTofu / Terraform

```yaml
include:
  - component: $CI_SERVER_FQDN/components/opentofu/job-templates@4.7.0
    inputs:
      opentofu_version: "1.12.1"
      root_dir: infrastructure/terraform/my-project
      state_name: production
      enable_id_tokens: true
      auto_define_backend: true
      base_os: alpine
```

Generates `.opentofu:validate`, `.opentofu:plan`, `.opentofu:apply` hidden jobs. See [[opentofu-gitlab-component]] for full details.

### SAST (Static Application Security Testing)

```yaml
include:
  - component: $CI_SERVER_FQDN/components/gitlab/sast@1
    inputs:
      stage: test
```

Language-aware; auto-detects Python, Go, JS, Java, etc. Produces a `gl-sast-report.json` artifact and annotates MRs.

### Secret Detection

```yaml
include:
  - component: $CI_SERVER_FQDN/components/gitlab/secret-detection@1
    inputs:
      stage: test
```

Scans for hardcoded credentials, API keys, and tokens in committed files and history.

### Dependency Scanning

```yaml
include:
  - component: $CI_SERVER_FQDN/components/gitlab/dependency-scanning@1
    inputs:
      stage: test
```

SCA (Software Composition Analysis) — checks dependencies against known CVE databases.

### Container Scanning

```yaml
include:
  - component: $CI_SERVER_FQDN/components/gitlab/container-scanning@1
    inputs:
      stage: test
      image: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```

Scans Docker images for OS-level and language-level vulnerabilities.

### DAST (Dynamic Application Security Testing)

```yaml
include:
  - component: $CI_SERVER_FQDN/components/gitlab/dast@1
    inputs:
      stage: dast
      dast_website: https://my-app.example.com
```

Live web app scanning. Requires a running deployment target — not suitable for every pipeline.

---

## Component Include Syntax

### Basic

```yaml
include:
  - component: $CI_SERVER_FQDN/<namespace>/<project>/<component-name>@<version>
    inputs:
      key: value
```

### Version Pinning

| Syntax | Behavior | Recommendation |
|--------|----------|----------------|
| `@1.2.3` | Exact version | **Preferred in production** |
| `@~1` | Latest patch in major 1 | OK for rapid iteration |
| `@1` | Latest in major 1 | Acceptable if you monitor releases |
| `@latest` | Always latest | **Avoid** — breaks pipelines silently on major bumps |

### Self-Managed Instances

Always use `$CI_SERVER_FQDN` — it resolves to `gitlab.com` on SaaS and your instance hostname on self-managed. Never hardcode `gitlab.com` in a shared pipeline config.

### Overriding Generated Jobs

Don't override `script:` directly inside a generated job — it replaces the component logic entirely. Instead:

```yaml
# Extend and add a before_script
my-sast:
  extends: .sast
  before_script:
    - echo "extra setup"
    - !reference [.sast, before_script]   # preserve original before_script

# Or override specific variables
sast:
  variables:
    SAST_EXCLUDED_PATHS: "tests, docs"
```

---

## Component Best Practices

- **Pin versions** — treat component upgrades like dependency bumps; review the changelog before updating
- **Use `$CI_SERVER_FQDN`** — always, never hardcode the GitLab hostname
- **Don't override `script:`** — extend with `before_script`/`after_script` or inject via `variables:`
- **Test upgrades on a feature branch** — never bump a component version directly on the default branch
- **Read `inputs:` docs before wrapping** — most components expose enough knobs to avoid custom jobs
- **Fewer components, well-tested** — prefer one component that covers 80% over three narrow ones
- **When a component does most of what you need** — extend it, don't replace it; customization via `variables:` and `extends:` covers the majority of cases

---

## Core `.gitlab-ci.yml` Reference

### Top-Level Structure

```yaml
stages:          # ordered list of stage names
  - lint
  - test
  - build
  - deploy

default:         # defaults applied to all jobs
  image: python:3.12
  tags:
    - docker

variables:       # pipeline-level CI variables
  ENV: production

workflow:        # pipeline-level rules (when to create a pipeline at all)
  rules:
    - if: $CI_COMMIT_BRANCH

include:         # import external configs or components
  - component: $CI_SERVER_FQDN/components/gitlab/sast@1
```

### Job Keywords

```yaml
my-job:
  stage: test
  image: python:3.12              # override default image
  tags: [docker]                  # runner tag selector
  needs: [lint-job]               # DAG: run as soon as lint-job finishes (ignore stages)
  dependencies: [build-job]       # download artifacts from these jobs
  allow_failure: false            # pipeline fails if this job fails
  interruptible: true             # cancel if a newer pipeline starts (save runner minutes)
  timeout: 10 minutes             # per-job timeout
  retry: 2                        # auto-retry on failure (max 2)

  before_script:
    - pip install uv

  script:
    - uv run pytest

  after_script:                   # always runs, even on failure
    - echo "cleanup"

  artifacts:
    paths:
      - dist/
    reports:
      junit: report.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
    expire_in: 7 days

  cache:
    key: $CI_COMMIT_REF_SLUG
    paths:
      - .venv/

  environment:
    name: production              # tracks deployments in GitLab UI
    url: https://myapp.example.com

  when: manual                    # manual | always | on_success | on_failure | never | delayed
```

### Predefined CI Variables (cheat sheet)

| Variable | Value |
|----------|-------|
| `$CI_COMMIT_BRANCH` | Current branch name |
| `$CI_DEFAULT_BRANCH` | Default branch (main/master) |
| `$CI_COMMIT_SHA` | Full commit SHA |
| `$CI_COMMIT_SHORT_SHA` | 8-char commit SHA |
| `$CI_COMMIT_REF_SLUG` | Branch/tag name, URL-safe |
| `$CI_PIPELINE_SOURCE` | `push`, `merge_request_event`, `schedule`, `web`, `api` |
| `$CI_MERGE_REQUEST_IID` | MR internal ID (only in MR pipelines) |
| `$CI_PROJECT_PATH` | `namespace/project` |
| `$CI_SERVER_FQDN` | Hostname of the GitLab instance |
| `$CI_REGISTRY_IMAGE` | Container registry path for this project |
| `$CI_JOB_TOKEN` | Short-lived token for auth to GitLab API |

---

## Rules & Conditions

### `rules:` Anatomy

```yaml
rules:
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    when: on_success
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    when: manual
    allow_failure: true
  - changes:
      - src/**/*.py
      - tests/**/*.py
    when: on_success
  - exists:
      - Dockerfile
  - when: never          # catch-all: don't run otherwise
```

`rules:` are evaluated top-to-bottom; first match wins. If no rule matches the job is excluded.

### Common Patterns

```yaml
# Only on default branch
rules:
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

# Only on MR pipelines
rules:
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"

# Only when specific files change
rules:
  - changes:
      - infrastructure/**/*

# Manual on feature branches, automatic on main
rules:
  - if: $CI_COMMIT_BRANCH != $CI_DEFAULT_BRANCH
    when: manual
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    when: on_success

# Skip on scheduled pipelines
rules:
  - if: $CI_PIPELINE_SOURCE == "schedule"
    when: never
  - when: on_success
```

### `workflow:` (Pipeline-Level)

```yaml
workflow:
  rules:
    # Run on MR pipelines and default branch; skip redundant branch pipelines when an MR is open
    - if: $CI_MERGE_REQUEST_IID
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_COMMIT_BRANCH
      when: never
```

---

## Artifacts & Caching

### Artifacts — share data between jobs, download after pipeline

```yaml
artifacts:
  name: "$CI_JOB_NAME-$CI_COMMIT_REF_SLUG"   # archive name
  paths:
    - dist/
    - build/
  exclude:
    - dist/**/*.map                             # exclude source maps
  expire_in: 30 days                           # auto-delete after this period
  when: always                                 # upload even on failure
  reports:
    junit: report.xml                          # parsed by GitLab for test results UI
    coverage_report:
      coverage_format: cobertura
      path: coverage.xml
    terraform: plan.json                       # renders diff in MR
    dotenv: deploy.env                         # passes variables to downstream jobs
```

### Cache — speed up jobs by reusing expensive downloads

```yaml
cache:
  key: $CI_COMMIT_REF_SLUG          # one cache per branch
  paths:
    - .venv/
    - node_modules/
  policy: pull-push                  # pull at start, push at end (default)
  # policy: pull                     # read-only (use in test jobs that don't update deps)

# File-hash-scoped cache (invalidates when lockfile changes)
cache:
  key:
    files:
      - uv.lock
  paths:
    - .venv/
```

**Key distinction**: artifacts survive pipeline completion and are downloadable; caches are ephemeral and only speed up execution within runners.

---

## Reuse Patterns

### YAML Anchors (same file only)

```yaml
.common_setup: &common_setup
  before_script:
    - pip install uv
    - uv sync

test:
  <<: *common_setup
  script:
    - uv run pytest
```

Use anchors for inline DRY within one file. Cannot span across `include:`d files.

### `extends:` (cross-file, composable)

```yaml
# base.yml
.base-python:
  image: python:3.12
  before_script:
    - uv sync

# pipeline.yml
include:
  - local: base.yml

test:
  extends: .base-python
  script:
    - uv run pytest
```

`extends:` deep-merges; arrays are replaced (not appended). Use `!reference` to merge arrays.

### `!reference []` (merge arrays from other jobs)

```yaml
.setup:
  before_script:
    - uv sync

.auth:
  before_script:
    - vault login

deploy:
  before_script:
    - !reference [.setup, before_script]
    - !reference [.auth, before_script]
  script:
    - ./deploy.sh
```

Use `!reference` when you need to merge `script`/`before_script`/`after_script` arrays from multiple sources.

---

## General CI/CD Best Practices

### Pipeline Design

- **Fast feedback first** — lint and validate before expensive build/test jobs; fail early
- **Use `needs:`** for DAG ordering instead of relying on stage ordering alone — unlocks parallelism
- **Use `changes:`** rules to skip jobs when unrelated files change — saves runner minutes
- **Keep jobs single-purpose** — avoid monolithic `script:` blocks; one job = one concern
- **Use `interruptible: true`** on non-deployment jobs — GitLab cancels them when a newer pipeline starts
- **`allow_failure: false`** on quality gates — linting, security scans, and type checks must not silently pass

### Secrets & Variables

- Store secrets as **masked + protected CI/CD variables**, never in `.gitlab-ci.yml`
- Use **Vault** (via OIDC) for dynamic, short-lived credentials — avoid long-lived static keys
- Use `$CI_JOB_TOKEN` for authenticating to GitLab's own APIs (registry, packages, API) — no additional variable needed
- Never `echo` secret variables in scripts; they'll appear in logs

### Deployments

- **`when: manual`** for any job that deploys to production — no accidental applies
- Use GitLab `environment:` keyword to track deployments in the UI and enable rollback
- Separate plan and apply into distinct jobs with an artifact handoff (`plan.cache`)
- Gate `apply` jobs with `needs: [plan-job]` to enforce ordering and reuse the saved plan

### Validation

- Validate `.gitlab-ci.yml` locally before pushing: `glab ci lint .gitlab-ci.yml`
- The `prek` hook in this repo runs `glab-ci-lint` automatically on commit
- Use `tofu validate` / `ruff check` etc. inside validate jobs rather than inside `before_script` of every job

### Performance

- Cache dependency downloads keyed to the lockfile hash (invalidates only when deps change)
- Use `policy: pull` in jobs that consume but don't install new packages
- Avoid `cache: when: always` — caches with failed installs can poison future runs

---

## When to Build Your Own Component

Only build custom CI jobs or components when **all applicable** conditions are met:

| Condition | Notes |
|-----------|-------|
| No catalog component exists for this use case | Searched `gitlab.com/explore/catalog` thoroughly |
| The closest component is abandoned | Last release >12 months ago AND open bugs unaddressed |
| The component cannot be customized via `extends:` + `variables:` | Tried extending before concluding this |
| The logic is truly project-specific | Cannot be parameterized and reused elsewhere |

**If you do build custom jobs**:
- Keep them in a reusable hidden job template (`.my-job:`) so other jobs can `extends:` it
- Document accepted variables at the top of the job as comments
- If the job is useful across >2 repos, consider publishing it as an internal GitLab component rather than duplicating across repos

---

## Troubleshooting

### Pipeline not triggered

**Symptom**: Push or MR created but no pipeline starts.

**Checks**:
1. `workflow:rules:` may be excluding it — check pipeline-level rules first
2. Job-level `rules:` may all evaluate to `when: never`
3. GitLab CI/CD may be disabled for the project (Settings → CI/CD → General)
4. Branch is protected and runner doesn't have permission

### `needs:` DAG error — "job not found"

**Symptom**: `needs: [some-job]` but pipeline fails with "job not found or not in earlier stage".

**Fix**: With `needs:`, stage ordering no longer applies — the needed job can be in any stage. The error usually means the job name is misspelled or conditionally excluded by `rules:`. Jobs excluded by rules don't exist in the pipeline graph.

### Artifact not found in downstream job

**Symptom**: File from a previous job's artifacts is missing in the next job.

**Fix**:
- Add `dependencies: [upstream-job]` explicitly (automatic only within the same stage)
- With `needs:`, artifacts are downloaded automatically from listed jobs — no `dependencies:` needed
- Check `expire_in` — if the pipeline ran after expiry, artifacts are gone
- Verify the artifact `paths:` pattern actually matched files (check the job log)

### Component not found

**Symptom**: `invalid include: component '<path>' not found`

**Checks**:
1. Verify the component path and version tag exist
2. Use `$CI_SERVER_FQDN` not hardcoded `gitlab.com` on self-managed
3. On self-managed: check if the component catalog feature is enabled in GitLab admin
4. The runner needs network access to the GitLab instance

### OIDC token empty in job

**Symptom**: `$VAULT_ID_TOKEN` or similar OIDC token variable is empty.

**Fix**: OIDC tokens require explicit opt-in via `id_tokens:` in the job or a parent hidden job:

```yaml
my-job:
  id_tokens:
    VAULT_ID_TOKEN:
      aud: https://${CI_SERVER_HOST}
  script:
    - echo "$VAULT_ID_TOKEN" | wc -c   # verify token is present
```

When using the OpenTofu component, the `.gitlab-tofu:id_tokens` hidden job must be defined in your pipeline — the component extends it. See [[opentofu-gitlab-component]].

### Job runs on wrong branch / too often

**Symptom**: A job runs on every commit even though it should be scoped.

**Fix**: Check rule precedence — rules evaluate top-to-bottom, first match wins. A missing `when: never` catch-all at the bottom means the job runs by default:

```yaml
rules:
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  # Missing: - when: never   ← without this, job runs everywhere else too
```

Add `- when: never` as the last rule to make exclusion explicit.

---

## Quick Reference: Key Job Keywords

| Keyword | Purpose |
|---------|---------|
| `stage:` | Which stage this job belongs to |
| `needs:` | DAG dependency (run as soon as needed jobs finish) |
| `dependencies:` | Which jobs' artifacts to download |
| `rules:` | Conditional inclusion/exclusion |
| `allow_failure:` | Whether pipeline fails if this job fails |
| `interruptible:` | Cancel on newer pipeline (save runner time) |
| `when:` | Trigger condition (on_success/manual/always/never) |
| `artifacts:` | Files to preserve after job completion |
| `cache:` | Files to restore/save for performance |
| `extends:` | Inherit config from a hidden job template |
| `environment:` | Track deployment in GitLab UI |
| `id_tokens:` | Generate OIDC JWT tokens for auth |
| `parallel:` | Run N instances of the same job |
| `resource_group:` | Prevent concurrent deploys to same environment |
