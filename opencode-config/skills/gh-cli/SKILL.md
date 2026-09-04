---
name: gh-cli
description: Use when the repository remote points to github.com. First check `git remote -v` to confirm the remote is on github.com before using. Covers PR creation/review, issue tracking, CI checks, and repository operations via gh commands.
metadata:
  review_after: "2026-08-09"
  docs_url: "https://cli.github.com/manual/"
---

# gh CLI

Authentication is managed via `gh auth login`, `GITHUB_TOKEN`, or `GH_TOKEN` env var.

## Auto-detection

Before using `gh` commands, check which platform the repo is on:

```bash
git remote -v
```

- Remote is `github.com` → use this skill (gh CLI)
- Remote is `gitlab.com` → use the `glab-cli` skill instead

## Authentication

```bash
gh auth status                              # check if authenticated
gh auth login -h github.com -p ssh          # authenticate via SSH
gh auth login -h github.com -w              # authenticate via web (device flow)
gh auth refresh -h github.com -s "repo"     # refresh with repo scope
gh auth token                               # print current auth token

# Fallback: authenticate via token
echo "$GITHUB_TOKEN" | gh auth login --with-token
```

## Pull Requests

```bash
# Create PR from your fork to upstream
gh pr create \
  --repo upstream-owner/repo \
  --head yourfork:branch \
  --base main \
  --title "Title" \
  --body "Description"

# Create PR from current branch (simple)
gh pr create --fill                    # uses commit message as title/body

# Create PR from current branch with template
gh pr create --fill --web              # open in browser to finalize

# View PRs
gh pr view 42                          # view in terminal
gh pr view 42 -w                       # open in browser
gh pr view 42 --json field1,field2     # JSON output for scripting

# Useful JSON fields for PR view:
# headRefName, baseRefName, headRepository, url, title, state,
# isCrossRepository, mergeable, reviewDecision, statusCheckRollup

# Close PR
gh pr close 1 --comment "Reason"       # close with comment

# List PRs
gh pr list                            # open PRs by default
gh pr list --author "@me"             # your PRs
gh pr list --state merged             # merged PRs
gh pr list --state all                # all PRs

# Checkout PR locally
gh pr checkout 42

# Diff
gh pr diff 42

# Review
gh pr review 42 --approve             # approve
gh pr review 42 --request-changes     # request changes
gh pr review 42 -c "LGTM!"            # comment

# Merge
gh pr merge 42
gh pr merge 42 --squash               # squash merge
gh pr merge 42 --rebase               # rebase merge
```

## Issues

```bash
gh issue list                         # list open issues
gh issue list --assignee "@me"        # your assigned issues
gh issue list --label bug             # filter by label
gh issue list --state closed          # closed issues
gh issue view 99                      # view issue in terminal
gh issue view 99 -w                   # open in browser
gh issue create -t "Title" -b "Body"
gh issue close 99
gh issue comment 99 -b "Looking into this"
```

## Repository

```bash
gh repo view                          # view current repo
gh repo view owner/repo               # view specific repo
gh repo fork                          # fork to your account
gh repo create                        # create new repo
gh repo clone owner/repo              # clone a repo
```

## CI / Actions

```bash
gh run list                           # list recent workflow runs
gh run list --branch main             # runs on a specific branch
gh run view <run-id>                  # view run details
gh run view <run-id> --log            # view run logs
gh run watch <run-id>                 # watch run in real-time
gh run rerun <run-id>                 # rerun a failed run
```

## Configuration

```bash
gh config list                        # show full config
gh config set git_protocol https      # use HTTPS (useful when SSH unavailable)
gh config set git_protocol ssh        # revert to SSH
```

## API (generic endpoint access)

```bash
# Raw API access
gh api repos/owner/repo/pulls/1

# With jq for filtering
gh api user --jq .login
gh api repos/owner/repo --jq '.default_branch'

# Check token scopes
gh api /user --head -i | grep -i x-oauth-scopes
```

## Troubleshooting

### SSH key issues during push

If `git push` fails with `Permission denied (publickey)`:

```bash
# Option 1: Use the gh auth token directly
GH_TOKEN="$(gh auth token)" git push \
  "https://oauth2:$(gh auth token)@github.com/owner/repo.git" branch

# Option 2: Switch git protocol to HTTPS globally
gh config set git_protocol https
git remote set-url origin https://github.com/owner/repo.git
git push origin branch
```

### Token scopes

If an operation fails due to insufficient scopes:

```bash
# Refresh with required scopes
gh auth refresh -h github.com -s "repo,workflow,read:org"
```

### Token still doesn't work for git push

GitHub no longer supports password authentication for Git operations (must use token or SSH).
