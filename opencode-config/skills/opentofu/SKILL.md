---
name: opentofu
description: Use when writing, modifying, or reviewing OpenTofu/Terraform HCL code, running tofu CLI commands, managing state, designing modules, or provisioning infrastructure. Covers language, CLI, best practices, and OpenTofu-specific features like state encryption.
metadata:
  review_after: "2026-08-09"
  docs_url: "https://opentofu.org/docs/"
  version_pinned: "1.12.x"
---

# OpenTofu

OpenTofu is an open-source fork of Terraform. HCL syntax and CLI commands are identical to Terraform with additional OpenTofu-specific features (state encryption, for_each on unknown values, etc.).

**Related skills**: [[opentofu-gitlab-component]] for CI/CD integration; [[naturalis-opentofu]] for Naturalis/arise-biodiversity conventions; [[naturalis-terraform-pitfalls]] for common pitfalls.

## CLI Workflow

```sh
# Init — downloads providers & modules, configures backend
tofu init
tofu init -upgrade              # upgrade providers to latest allowed version
tofu init -reconfigure          # reinitialize backend even if config unchanged
tofu init -backend-config=backend.hcl  # load extra backend config from file

# Validate & Format
tofu validate                   # check HCL syntax and internal consistency
tofu fmt                        # format .tf files in current directory
tofu fmt -recursive             # format all .tf files recursively
tofu fmt -check                 # exit non-zero if files need formatting (CI)

# Plan
tofu plan                       # preview changes
tofu plan -out=plan.cache       # save plan binary for reproducible apply
tofu plan -var-file=prod.tfvars
tofu plan -target=module.name.aws_s3_bucket.data  # scope to one resource
tofu plan -refresh=false        # skip provider read (faster; risk of drift)
tofu plan -destroy              # plan a full destroy

# Apply
tofu apply                      # apply (prompts for confirmation)
tofu apply -auto-approve        # skip confirmation prompt (CI)
tofu apply plan.cache           # apply a saved plan exactly as planned
tofu apply -target=...          # targeted apply — emergency use only

# Destroy
tofu destroy -auto-approve
tofu destroy -target=module.name.resource_type.name

# State operations
tofu state list                 # list all managed resources
tofu state show aws_s3_bucket.data  # inspect resource attributes
tofu state mv <src> <dst>       # rename resource without destroy/recreate
tofu state rm <resource>        # remove from state without destroying the real resource
tofu state pull                 # dump current state as JSON (stdout)
tofu state push state.json      # overwrite remote state — use with extreme caution

# Output
tofu output                     # show all outputs
tofu output -json               # machine-readable
tofu output bucket_arn          # single value

# Import existing resources
tofu import aws_s3_bucket.existing my-bucket-name  # CLI import
tofu plan -generate-config-out=generated.tf        # generate config from live resource

# Workspace
tofu workspace list
tofu workspace new staging
tofu workspace select staging
```

## File Organization

```
root/
├── main.tf          # terraform{} block, provider blocks
├── variables.tf     # all input variables
├── outputs.tf       # all outputs
├── locals.tf        # all locals
├── data.tf          # all data sources
├── <component>.tf   # resources grouped by logical component (s3.tf, iam.tf)
└── modules/
    └── <name>/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

Keep root modules ≤ 200 lines; extract into child modules when a logical group grows beyond that.

## HCL Style

### Resources

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "${local.prefix}-data"

  tags = merge(local.common_tags, {
    purpose = "data-storage"
  })
}
```

- Use `local.prefix` for consistent naming, not inline interpolation per resource
- Apply tags via `merge(local.common_tags, { ... })` — never override tags directly
- Group resources of the same type in a dedicated `<component>.tf` file

### Variables

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment."
  validation {
    condition     = contains(["development", "acceptance", "production"], var.environment)
    error_message = "Must be development, acceptance, or production."
  }
}

variable "noncurrent_version_expiration_days" {
  type    = number
  default = 90
  validation {
    condition     = var.noncurrent_version_expiration_days > 0
    error_message = "Must be a positive number."
  }
}
```

- Always include `type` and `description`
- Use `validation` blocks for constrained inputs rather than failing at apply time
- Mark secrets with `sensitive = true`; never put secrets in `default`

### Locals

```hcl
locals {
  prefix = var.service
  common_tags = {
    service       = var.service
    service_owner = var.service_owner
    managed_by    = "opentofu"
  }
  env_keys = toset(["development", "acceptance", "production"])
}
```

Compute derived values once in `locals.tf` and reference everywhere else.

### Outputs

```hcl
output "bucket_arn" {
  description = "ARN of the data S3 bucket."
  value       = aws_s3_bucket.data.arn
}

output "db_password" {
  description = "Database root password."
  value       = random_password.db.result
  sensitive   = true
}
```

### Data Sources

```hcl
data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "allow_read" {
  statement {
    principals {
      type        = "AWS"
      identifiers = [var.role_arn]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
}
```

## `for_each` vs `count`

Always prefer `for_each` over `count`. `count` produces indexed resources (`[0]`, `[1]`); removing one element reindexes and triggers destroy/recreate of unchanged resources. `for_each` produces named resources (`["dev"]`, `["prod"]`) that are stable regardless of set membership changes.

```hcl
# Bad — index-based, fragile on element removal
resource "aws_s3_bucket" "data" {
  count  = length(var.buckets)
  bucket = var.buckets[count.index]
}

# Good — key-based, stable
resource "aws_s3_bucket" "data" {
  for_each = toset(var.buckets)
  bucket   = each.key
}

# for_each on a map
resource "aws_s3_bucket" "env" {
  for_each = {
    dev  = "development"
    prod = "production"
  }
  bucket = "${var.service}-${each.key}"
  tags   = merge(local.common_tags, { environment = each.value })
}
```

Use `count` only for booleans: `count = var.enabled ? 1 : 0`.

## Modules

```hcl
module "s3_buckets" {
  for_each = local.env_keys
  source   = "./modules/s3-bucket"

  bucket_name = "${local.prefix}-${each.key}"
  tags        = local.common_tags
}
```

Module sources: `./modules/name` (local), `git::https://...` (remote), `registry.opentofu.org/namespace/module/provider` (registry).

## Backend Configuration

### HTTP Backend (GitLab managed state)

```hcl
terraform {
  backend "http" {}  # all config injected via CI env vars or -backend-config
}
```

GitLab CI injects `TF_HTTP_ADDRESS`, `TF_HTTP_USERNAME`, `TF_HTTP_PASSWORD` automatically when using the GitLab OpenTofu component with `auto_define_backend: true`.

### S3 Backend

```hcl
terraform {
  backend "s3" {
    bucket  = "my-terraform-state"
    key     = "path/to/state.tfstate"
    region  = "eu-west-1"
    encrypt = true
  }
}
```

## State Encryption (OpenTofu 1.7+)

OpenTofu-specific: encrypts state and plan files at rest. Not available in Terraform.

```hcl
terraform {
  encryption {
    # Key provider — pbkdf2 for passphrase, aws_kms for KMS
    key_provider "pbkdf2" "main" {
      passphrase = var.state_passphrase
    }

    method "aes_gcm" "main" {
      keys = key_provider.pbkdf2.main
    }

    state {
      method = method.aes_gcm.main
    }

    plan {
      method = method.aes_gcm.main
    }
  }
}
```

AWS KMS (preferred for production):

```hcl
key_provider "aws_kms" "main" {
  kms_key_id = "arn:aws:kms:eu-west-1:123456789012:key/..."
  key_spec   = "AES_256"
}
```

## Provider Configuration

```hcl
terraform {
  required_version = ">= 1.12"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.5"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.10"
    }
  }
}

provider "aws" {
  region = "eu-west-1"

  default_tags {
    tags = local.common_tags  # applied to every resource automatically
  }
}

provider "vault" {
  address          = "https://vault.example.io"
  skip_child_token = true
}
```

Pin with `~>` (patch-float): `~> 6.5` means `>= 6.5, < 7.0`. Never use `>= X` alone.

## Config-Driven Import (OpenTofu 1.5+)

Preferred over CLI `tofu import` — reviewable and version-controlled.

```hcl
import {
  id = "existing-bucket-name"
  to = aws_s3_bucket.existing
}

resource "aws_s3_bucket" "existing" {
  bucket = "existing-bucket-name"
}
```

Generate config skeleton for existing resources:

```sh
tofu plan -generate-config-out=generated.tf  # then review and clean up
```

## Moved Block (rename without destroy/recreate)

```hcl
moved {
  from = aws_s3_bucket.old_name
  to   = aws_s3_bucket.new_name
}
```

## Checks (OpenTofu 1.5+)

Post-apply assertions that warn without failing the apply:

```hcl
check "api_healthy" {
  data "http" "probe" {
    url = "https://${aws_lb.api.dns_name}/health"
  }
  assert {
    condition     = data.http.probe.status_code == 200
    error_message = "API health check failed after deploy."
  }
}
```

## Expressions & Functions

```hcl
# Interpolation
name = "${var.service}-${var.env}"

# Conditional
instance_type = var.env == "production" ? "t3.large" : "t3.micro"

# Collection functions
merge(map1, map2)            # merge maps; right-side wins on conflict
toset(list)                  # deduplicate and convert to set
tolist(set)                  # set → list
keys(map)                    # get map keys as list
values(map)                  # get map values as list
lookup(map, key, default)    # safe map lookup with fallback
contains(list, value)        # membership test
length(collection)           # count elements
flatten([[1,2],[3]])         # → [1, 2, 3]
distinct(list)               # deduplicate preserving order
compact(list)                # remove null and empty strings

# String functions
format("s3://%s/%s", var.bucket, var.key)
replace(str, "old", "new")
trimspace(str)
join(",", list)
split(",", str)
lower(str) / upper(str)

# Error handling
try(expr, fallback)          # return fallback if expr errors
can(expr)                    # true if expr evaluates without error

# Comprehensions
[for k, v in map : "${k}=${v}"]          # list from map
{for k, v in map : k => upper(v)}        # map transform
[for item in list : item if item != ""]  # filtered list
```

## Lifecycle Rules

```hcl
resource "aws_s3_bucket" "critical" {
  bucket = "critical-data"

  lifecycle {
    prevent_destroy       = true                    # block tofu destroy
    ignore_changes        = [tags, lifecycle_rule]  # ignore external changes to these
    create_before_destroy = true                    # blue-green replacement
  }
}
```

## Dynamic Blocks

```hcl
dynamic "ingress" {
  for_each = var.ingress_rules
  content {
    from_port   = ingress.value.from_port
    to_port     = ingress.value.to_port
    protocol    = ingress.value.protocol
    cidr_blocks = ingress.value.cidr_blocks
  }
}
```

## Best Practices

- **Secrets**: never in `.tf` files or state — read from Vault or AWS Secrets Manager via data sources
- **Pin versions**: `~>` for providers; `>= X.Y` for the OpenTofu binary itself
- **`for_each` over `count`**: use `count` only for boolean enable/disable patterns
- **Tags**: define once in `local.common_tags`, spread with `merge()`
- **Sensitive outputs**: mark with `sensitive = true` so they're redacted in logs
- **`-target`**: emergency use only — normal plans must cover the full state
- **Never edit state manually**: use `tofu state mv/rm` or `moved {}` blocks
- **Separate envs by state file**: do not share state across environments; use separate backends
- **Always save plan in CI**: `tofu plan -out=plan.cache` then `tofu apply plan.cache`
- **Drift detection**: run periodic plans even without code changes to catch configuration drift
- **Validate in CI**: `tofu validate` + `tofu fmt -check` before every plan

---

## Quick Reference: Common Commands

| Task | Command |
|------|---------|
| Syntax check | `tofu validate` |
| Format code | `tofu fmt -recursive` |
| Preview changes | `tofu plan -out=tfplan` |
| Apply with saved plan | `tofu apply tfplan` |
| List all resources | `tofu state list` |
| Inspect resource | `tofu state show aws_s3_bucket.data` |
| Rename (no recreate) | `tofu state mv old_name new_name` |
| Remove from state | `tofu state rm resource_type.name` |
| Destroy everything | `tofu destroy -auto-approve` |
| Get plan in JSON | `tofu plan -json > plan.json` |

---

## Troubleshooting

### State is locked

**Symptom**: `Error acquiring the state lock: ... Terraform operation currently in progress`

**Fix**: Another `tofu` process still holds the lock. Either wait for it to finish or force-unlock (careful — only if you're certain the other process crashed):
```sh
tofu force-unlock <LOCK_ID>  # get LOCK_ID from error message
```

### Provider plugin not found

**Symptom**: `Error: Could not find provider ... hashicorp/aws`

**Fix**: Run `tofu init` to download the provider:
```sh
tofu init -upgrade  # also upgrades existing providers
```

### "no changes" after removing a variable

**Symptom**: You removed a variable from `.tf` files but `tofu plan` shows changes.

**Fix**: Old state references the now-removed variable. Clean it up:
```sh
tofu state rm resource_type.name  # remove from state
# Re-import if needed: tofu import aws_s3_bucket.data my-bucket
```

### Drift detected

**Symptom**: `tofu plan` shows changes you didn't make (someone edited live infrastructure).

**Action**: Review the changes carefully:
```sh
tofu plan | grep -A5 "will be updated"  # see drift details
tofu apply  # accept or reject the changes
```

### Backend authentication fails

**Symptom**: `Error reading state from remote: access denied` or `HTTP 401`

**Fix**: Check credentials:
- S3 backend: `aws sts get-caller-identity` (verify AWS credentials)
- HTTP backend: verify `TF_HTTP_USERNAME` and `TF_HTTP_PASSWORD`
- Vault backend: `vault token lookup` (check token is valid)

### Terraform vs OpenTofu syntax error

**Symptom**: Code that worked in Terraform fails in OpenTofu.

**Cause**: Usually version mismatch. OpenTofu 1.7+ has features Terraform doesn't (state encryption, for_each on computed values).

**Fix**: Pin the exact version needed. For state encryption, require OpenTofu 1.7+:
```hcl
terraform {
  required_version = ">= 1.7"  # enforcement
}
```

---

## Related Skills

- [[opentofu-gitlab-component]]: CI/CD integration patterns
- [[naturalis-opentofu]]: Naturalis organization conventions
- [[naturalis-terraform-pitfalls]]: Common pitfalls and debugging patterns
- [[aws-cli]]: Validate and inspect actual AWS resource state after `tofu apply`
