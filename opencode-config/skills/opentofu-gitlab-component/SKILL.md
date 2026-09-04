---
name: opentofu-gitlab-component
description: Use when configuring or troubleshooting the GitLab OpenTofu CI/CD component (gitlab.com/components/opentofu). Covers include syntax, all component inputs, the three job templates it generates, Vault OIDC token wiring, and advanced features like drift detection and MR plan reuse.
metadata:
  review_after: "2026-08-09"
  docs_url: "https://gitlab.com/components/opentofu"
  version_pinned: "4.7.0"
---

# OpenTofu GitLab Component

The official GitLab CI/CD component for OpenTofu. It generates three hidden job templates that you extend in your own pipeline.

**Related skills**: [[opentofu]] for HCL language reference; [[naturalis-opentofu]] for Naturalis-specific CI setup; [[naturalis-terraform-pitfalls]] for common pitfalls.

## Include Syntax

```yaml
include:
  - component: $CI_SERVER_FQDN/components/opentofu/job-templates@4.7.0
    inputs:
      opentofu_version: "1.12.1"
      root_dir: infrastructure/terraform/my-project
      state_name: production
      enable_id_tokens: true
      id_tokens_setup_script: ""
      auto_define_backend: true
      base_os: alpine
```

Use `$CI_SERVER_FQDN` (not hardcoded `gitlab.com`) so it works on self-managed instances.

## Component Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `opentofu_version` | string | latest | OpenTofu version to install |
| `root_dir` | string | `.` | Path to the root module (where `.tf` files live) |
| `state_name` | string | `default` | GitLab-managed state name (used in HTTP backend URL) |
| `enable_id_tokens` | boolean | `false` | Enable OIDC ID token generation for Vault/cloud auth |
| `id_tokens_setup_script` | string | `""` | Shell script to run before init (inject credentials) |
| `auto_define_backend` | boolean | `false` | Auto-configure GitLab HTTP backend |
| `base_os` | string | `alpine` | Base OS for the runner image (`alpine` or `ubuntu`) |

## Generated Job Templates

The component creates three hidden jobs you extend:

| Template | Purpose |
|----------|---------|
| `.opentofu:validate` | `tofu init` + `tofu validate` + `tofu fmt -check` |
| `.opentofu:plan` | `tofu plan -out=plan.cache` + produces plan artifact + terraform MR report |
| `.opentofu:apply` | `tofu apply plan.cache` — consumes plan artifact |

## Standard Workflow

```yaml
stages:
  - lint
  - deploy
  - opentofu_apply

include:
  - component: $CI_SERVER_FQDN/components/opentofu/job-templates@4.7.0
    inputs:
      opentofu_version: "1.12.1"
      root_dir: infrastructure/terraform/my-project
      state_name: production
      enable_id_tokens: true
      auto_define_backend: true
      base_os: alpine

# Hidden job: provides OIDC id_tokens block that component jobs extend
.gitlab-tofu:id_tokens:
  id_tokens:
    VAULT_ID_TOKEN:
      aud: https://${CI_SERVER_HOST}

# Validate on all branches when infra changes
opentofu:validate:
  extends: [.opentofu:validate]
  <<: *vault_auth
  stage: lint
  needs: []
  allow_failure: false
  rules:
    - changes:
        - infrastructure/terraform/my-project/**/*

# Plan on all branches (manual on feature branches, auto on main)
opentofu:plan:
  extends: [.opentofu:plan]
  <<: *vault_auth
  stage: deploy
  needs: []
  artifacts:
    name: plan
    paths:
      - infrastructure/terraform/my-project/plan.cache
      - infrastructure/terraform/my-project/plan.json
    reports:
      terraform: infrastructure/terraform/my-project/plan.json
    expire_in: 7 days
  rules:
    - if: $CI_COMMIT_BRANCH != $CI_DEFAULT_BRANCH
      changes:
        - infrastructure/terraform/my-project/**/*
      when: manual
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      changes:
        - infrastructure/terraform/my-project/**/*

# Apply on main branch only, manual trigger, needs plan
opentofu:apply:
  extends: [.opentofu:apply]
  <<: *vault_auth
  stage: opentofu_apply
  needs:
    - opentofu:plan
  allow_failure: false
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      changes:
        - infrastructure/terraform/my-project/**/*
      when: manual
```

## Vault OIDC Auth Anchor Pattern

When `enable_id_tokens: true`, the component generates a `.gitlab-tofu:id_tokens` hidden job. You still need to exchange the token for credentials before `tofu init` runs. Use a YAML anchor:

```yaml
.vault_auth: &vault_auth
  before_script:
    - |
      set -e
      # Exchange GitLab OIDC token for Vault token
      export VAULT_TOKEN=$(curl -sf --request POST \
        --data "{\"jwt\":\"$VAULT_ID_TOKEN\",\"role\":\"$TOFU_VAULT_AUTH_ROLE\"}" \
        "$TOFU_VAULT_SERVER_URL/v1/auth/jwt/login" | jq -r '.auth.client_token')
      export VAULT_ADDR="$TOFU_VAULT_SERVER_URL"
      # Fetch AWS STS credentials from Vault
      AWS_CREDS=$(curl -sf --header "X-Vault-Token:$VAULT_TOKEN" \
        "$TOFU_VAULT_SERVER_URL/v1/aws/sts/$TOFU_VAULT_AWS_ROLE")
      export AWS_ACCESS_KEY_ID=$(echo "$AWS_CREDS" | jq -r '.data.access_key')
      export AWS_SECRET_ACCESS_KEY=$(echo "$AWS_CREDS" | jq -r '.data.secret_key')
  variables:
    TOFU_VAULT_SERVER_URL: "https://vault.example.io"
    TOFU_VAULT_AUTH_ROLE: "jwt-my-project"
    TOFU_VAULT_AWS_ROLE: "aws-my-project"
```

Merge this into each job with `<<: *vault_auth`.

## Plan Artifacts

The `.opentofu:plan` template produces two artifacts under `root_dir/`:
- `plan.cache` — binary plan passed to apply
- `plan.json` — human-readable JSON plan, used as the MR terraform report

The MR report renders a diff table directly in the merge request UI.

## Key Patterns

- **`allow_failure: false`** on validate and apply — these must not silently pass
- **`needs: [opentofu:plan]`** on apply — enforces ordering and artifact availability
- **`when: manual`** on apply on main — no auto-apply to production
- **`changes:`** rules — only trigger on infra file changes, not on every commit

---

## Advanced (rarely needed in standard setups)

### Drift Detection

Run a scheduled plan to detect drift between state and real infrastructure:

```yaml
opentofu:drift:
  extends: [.opentofu:plan]
  <<: *vault_auth
  stage: deploy
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  allow_failure: true  # drift is a warning, not a blocker
```

Set up a GitLab CI schedule to run this pipeline periodically (e.g. nightly).

### MR Plan Reuse

To show the plan in an MR without re-running it on main, pass the plan artifact from the MR pipeline to apply on merge. This requires artifact cross-pipeline references and is complex — use only when CI time is critical.

### OPA Policy Enforcement

Inject an OPA sidecar step between plan and apply:

```yaml
opentofu:policy:
  stage: deploy
  needs:
    - job: opentofu:plan
      artifacts: true
  script:
    - |
      conftest test infrastructure/terraform/my-project/plan.json \
        --policy policies/ \
        --namespace opentofu
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      changes:
        - infrastructure/terraform/my-project/**/*
```

### Multiple Root Modules

For monorepos with multiple Terraform roots, include the component multiple times with different `state_name` and `root_dir`:

```yaml
include:
  - component: $CI_SERVER_FQDN/components/opentofu/job-templates@4.7.0
    inputs:
      root_dir: infrastructure/terraform/storage
      state_name: storage
      opentofu_version: "1.12.1"
      auto_define_backend: true
      enable_id_tokens: true
      base_os: alpine

  - component: $CI_SERVER_FQDN/components/opentofu/job-templates@4.7.0
    inputs:
      root_dir: infrastructure/terraform/networking
      state_name: networking
      opentofu_version: "1.12.1"
      auto_define_backend: true
      enable_id_tokens: true
      base_os: alpine
```

Then define separate validate/plan/apply jobs extending each template set.

---

## Quick Reference: Component Inputs

```yaml
include:
  - component: $CI_SERVER_FQDN/components/opentofu/job-templates@4.7.0
    inputs:
      opentofu_version: "1.12.1"      # exact version or "latest"
      root_dir: "."                   # path to root module
      state_name: "production"        # GitLab HTTP backend state name
      enable_id_tokens: true          # enable OIDC for Vault/cloud auth
      id_tokens_setup_script: ""      # optional: shell script for pre-auth setup
      auto_define_backend: true       # auto-configure GitLab HTTP backend
      base_os: "alpine"               # runner OS: "alpine" or "ubuntu"
```

---

## Troubleshooting

### Component not found

**Symptom**: `invalid include: component not found`

**Fix**: Verify the component path and version:
```yaml
# Use $CI_SERVER_FQDN for self-managed instances, gitlab.com for SaaS
include:
  - component: $CI_SERVER_FQDN/components/opentofu/job-templates@4.7.0
```

Check that the version exists: `git clone https://.../components/opentofu` and check available tags.

### OIDC token not passed to jobs

**Symptom**: `VAULT_ID_TOKEN` is empty in `before_script`

**Fix**: Ensure the `.gitlab-tofu:id_tokens` hidden job is defined in your pipeline:
```yaml
.gitlab-tofu:id_tokens:
  id_tokens:
    VAULT_ID_TOKEN:
      aud: https://${CI_SERVER_HOST}
```

And extend it with `extends: [.opentofu:plan]` (the component job templates extend it automatically).

### Plan artifact not found during apply

**Symptom**: `apply` stage fails because `plan.cache` is missing

**Fix**: Ensure `opentofu:plan` runs before `apply` and produces artifacts:
```yaml
opentofu:apply:
  extends: [.opentofu:apply]
  needs:
    - opentofu:plan  # explicit dependency; downloads artifacts
```

Also check artifact retention: `expire_in: 7 days` should be long enough.

### Backend auto-configuration fails

**Symptom**: `tofu init` fails with backend HTTP errors even though `auto_define_backend: true`

**Fix**: The component injects `TF_HTTP_*` variables automatically. Verify:
- GitLab is at the specified `$CI_SERVER_FQDN`
- Your CI job has permission to read/write state (check project settings → CI/CD → Runners)
- For self-managed: check the HTTP backend is enabled in GitLab admin settings

### Plan shows unexpected changes

**Symptom**: `tofu plan` in CI shows drift you didn't make

**Cause**: Local drift or remote changes since last plan. 

**Fix**: Rerun plan to refresh state:
```yaml
opentofu:plan:
  extends: [.opentofu:plan]
  # ... no -refresh=false — always refresh to catch drift
```

---

## Related Skills

- [[opentofu]]: HCL patterns and CLI reference
- [[naturalis-opentofu]]: Naturalis-specific CI and Vault auth patterns
- [[naturalis-terraform-pitfalls]]: Common pitfalls and debugging patterns
