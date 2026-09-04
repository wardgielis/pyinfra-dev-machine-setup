---
name: glab-cli
description: Use when interacting with GitLab via the glab CLI. Covers MR creation/review, pipeline management, issue tracking, and repository operations via glab commands.
metadata:
  review_after: "2026-08-09"
  docs_url: "https://gitlab.com/gitlab-org/cli/-/tree/main/docs"
---

# glab CLI

Authentication is managed via `GITLAB_TOKEN` env var or `glab auth login`.

## Auto-detection

Before using `glab` commands, check which platform the repo is on:

```bash
git remote -v
```

- Remote is `gitlab.com` → use this skill (glab CLI)
- Remote is `github.com` → use the `gh-cli` skill instead

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

Branch names must match `[0-9]+/[a-zA-Z0-9\-_]+` or be `main`/`main-databricks`. The numeric prefix should be the Jira ticket number (e.g. `BIOCL-2126/add-s3-buckets`). Use `0000/` as placeholder when no ticket exists (e.g. `0000/use-data-contract-schema`).

### Pushing via HTTPS (when SSH is not configured)

```bash
git remote set-url origin https://gitlab.com/<namespace>/<project>.git
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
