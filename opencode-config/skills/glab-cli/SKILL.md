---
name: glab-cli
description: Use when interacting with GitLab via the glab CLI — on gitlab.com or a self-managed instance. Covers host resolution for self-managed GitLab, MR creation/review, pipeline management, issue tracking, repository operations, and the `glab cluster agent` commands for Kubernetes access.
metadata:
  review_after: "2026-11-09"
  docs_url: "https://gitlab.com/gitlab-org/cli/-/tree/main/docs"
---

# glab CLI

Authentication is managed via `GITLAB_TOKEN` env var or `glab auth login`.

## Auto-detection

Before using `glab` commands, check which platform the repo is on:

```bash
git remote -v
```

- Remote is **any GitLab host** — `gitlab.com` *or* a self-managed instance → use this skill (glab CLI)
- Remote is `github.com` → use the [[gh-cli]] skill instead

**Most of our work is on a self-managed instance, not `gitlab.com`.** Do not treat a non-`gitlab.com` remote as "not GitLab".

### Host resolution on self-managed GitLab

`glab` picks the host in this documented order:

1. The host of the base repository, when you are inside a Git repo with a GitLab remote
2. The `GITLAB_HOST` environment variable
3. The `host` key in the config file (`glab config get host`)

So **inside a repo, glab does the right thing automatically** — the remote wins. The trap is running `glab` from outside a repo, or against a different instance: `glab config get host` returns `gitlab.com` by default, so the command silently targets the wrong instance and fails with a confusing 404 or auth error.

```bash
glab config get host                      # what would be used outside a repo
GITLAB_HOST=gitlab.example.org glab api /version   # one-off against an instance
glab auth login --hostname gitlab.example.org      # persist credentials per host
glab auth status                                   # list authenticated hosts
```

Tokens are per host. `GITLAB_TOKEN` applies to whichever host is resolved, so pair it with `GITLAB_HOST` when scripting against a self-managed instance. For an instance on a non-standard port or protocol, `glab auth login` also takes `--api-host`, `--api-protocol` and `--ssh-hostname`.

## Merge Requests

```bash
# Create MR with template (recommended, uses .gitlab/merge_request_templates/Default.md)
glab mr create -t "type: description" --template Default -a "@me" --yes

# Create MR with inline description (no template)
glab mr create -t "feat: add new table" -d "Description of the change" -a "@me" --yes

# Create MR with --fill (uses commit message as title, may open interactive editor)
glab mr create -a "@me" --fill --yes

# Review MRs
glab mr view 42 -w            # open in browser
glab mr diff 42               # show diff
glab mr checkout 42           # checkout locally
glab mr approve 42            # approve
glab mr merge 42              # merge

# List MRs
glab mr list --assignee=@me            # open MRs by default
glab mr list --assignee=@me --all      # include closed/merged
glab mr list --group my-group -l "team:data-engineering"
```

### Branch naming

Branch names must match `[0-9]+/[a-zA-Z0-9\-_]+` or be `main`/`main-databricks`. The numeric prefix should be the ticket number (e.g. `1234/add-s3-buckets`). Use `0000/` as placeholder when no ticket exists (e.g. `0000/use-data-contract-schema`). See [[jira-cli]] for finding the ticket key.

### Pushing via HTTPS (when SSH is not configured)

```bash
git remote set-url origin https://<gitlab-host>/<namespace>/<project>.git
git push -u origin <branch>
```

## Pipelines / CI

```bash
# List/status
glab ci list                   # recent pipelines
glab ci status                 # current branch pipeline status

# View
glab ci view                       # interactive pipeline/job browser (TTY)
glab ci view 12345 -w              # open in browser
glab ci get -p 12345               # pipeline details as JSON (non-interactive)
glab ci get -p 12345 --with-job-details  # pipeline + job details as JSON

# Jobs
glab ci retry 67890                # retry a job by ID
glab ci trace 67890                # job log stream (non-interactive)
glab ci trace lint                 # trace job by name

# Validate / inspect config
glab ci lint                       # validate .gitlab-ci.yml
glab ci config                     # inspect CI/CD config

# Run
glab ci run -b feat/my-branch      # run pipeline on branch
glab ci run -b feat/my-branch -i my-input:value  # with pipeline inputs
```

## Issues

```bash
glab issue list --assignee=@me         # open issues by default
glab issue list --assignee=@me --closed  # closed issues
glab issue view 99
glab issue create -t "Bug: ..." -d "description" -a "@me" -l bug
glab issue close 99
glab issue note 99 -m "Looking into this"
```

## Labels

```bash
glab label list                      # list labels in project
glab label create bug -c "#FF0000"   # create label with colour
glab label edit bug -n "bug-fix"     # rename a label
glab label delete bug                # delete a label
```

## To-Do

```bash
glab todo list                       # list pending items
glab todo done 123                   # mark item done
glab todo done --all                 # clear all
```

## CI/CD Variables

```bash
glab variable list                   # list project variables
glab variable set KEY value          # create a variable
glab variable get KEY                # get a variable value
glab variable delete KEY             # delete a variable
glab variable list --group           # list group-level variables
```

## Kubernetes: `glab cluster agent`

This is **how a human reaches a cluster** that is connected through the GitLab agent — no distributed kubeconfig, no inbound firewall rule to the API server. See [[kubernetes]] §5 for the agent itself and [[argocd]] §10 for the GitOps side.

```bash
glab cluster agent list                  # agents in the project, with numeric IDs

# Point kubectl at a cluster through the agent
glab cluster agent update-kubeconfig --agent <id> --use-context
kubectl get nodes

glab cluster graph                       # browse the live object graph (EXPERIMENTAL)
```

`update-kubeconfig` writes an **exec credential plugin** entry, so tokens are minted on demand rather than stored:

| Flag | Effect |
|---|---|
| `-a`, `--agent <id>` | The **numeric** agent ID, not its name — get it from `glab cluster agent list` |
| `-u`, `--use-context` | Make it the default `kubectl` context |
| `--token-expiry-duration` | Validity of the generated token; minimum 1 day, default 24h, expires end of day |
| `-c`, `--cache-mode` | `force-keyring` (default), `keyring-filesystem-fallback`, `force-filesystem`, `no` |
| `--check-revoked` | Verify a cached token server-side; adds latency to every access |
| `--kubeconfig` | Write to a specific kubeconfig file |

Token management, when you need the token itself rather than a kubeconfig:

```bash
glab cluster agent get-token --agent <id>    # create a PAT for the agent
glab cluster agent token list --agent <id>   # manage agent tokens
glab cluster agent token-cache               # inspect/clear locally cached tokens
glab cluster agent check-manifest-usage      # find agents on deprecated GitOps manifest settings
```

### `bootstrap` requires Flux — do not run it on an Argo CD cluster

`glab cluster agent bootstrap` is not a neutral installer. Its own help states that `flux` must be on `$PATH` and that **"Flux is always required for the bootstrap process"**; its steps create Flux `HelmRepository` and `HelmRelease` resources, commit them to the manifest path, and trigger a Flux reconciliation. On an Argo CD cluster this installs a second GitOps controller by accident.

If you do use it, `--manifest-path` must match the `--path` you gave `flux bootstrap gitlab`, or reconciliation fails. Otherwise install the agent with Helm or as an Argo CD `Application` — see [[kubernetes]] §5.2.

## Repository

```bash
glab repo view                    # open in browser
glab repo fork                    # fork to namespace
```

## Configuration

- Token: `GITLAB_TOKEN` env var or `glab auth login`
- Default project is auto-detected from git remote
- Override with `-R <namespace/project>` or `--repo <path>`
- Output format: `--output json` or `--output yaml` (not `-f`, useful for scripting)
- Use `glab api "projects/<id>/pipelines/<id>"` as fallback for endpoints not exposed by glab commands
- Use `glab ci trace <job-id>` to stream raw job logs in real time
