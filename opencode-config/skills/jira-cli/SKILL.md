---
name: jira-cli
description: Use when interacting with Jira via the CLI (ankitpokhrel/jira-cli). Covers issue search, creation, transitions, comments, sprints, epics, and boards.
metadata:
  review_after: "2026-08-09"
  docs_url: "https://github.com/ankitpokhrel/jira-cli"
---

# Jira CLI

Binary: `jira` from [ankitpokhrel/jira-cli](https://github.com/ankitpokhrel/jira-cli).

Install: `brew install jira-cli`

## Authentication

```bash
# 1. Get a Jira API token from https://id.atlassian.com/manage-profile/security/api-tokens
# 2. Export it and add to ~/.zshrc:
export JIRA_API_TOKEN="your_token"

# 3. Run init (non-interactive):
jira init \
  --installation cloud \
  --server https://your-domain.atlassian.net \
  --login you@example.com \
  --project PROJ \
  --board None \
  --force

# Or interactive:
jira init
```

## Project Template

This project uses an **auto-generated template** in the description field when a new issue is created. The template uses **Jira info panels** (Atlassian Document Format) with sections:

- Work to be done
- Acceptance criteria
- Impact (sub-fields: Database, DSI API, DNA dashboard, Databricks dashboard, BOLD export)
- Stakeholders

### ⚠️ CRITICAL: Never use `jira issue edit -b"..."` for description

`jira issue edit -b"..."` replaces the entire description as plain text, destroying the info panel structure. Always use the **REST API** with `curl` + `jq` to update the description while preserving the ADF panels.

**Correct workflow:**
1. Create the issue with just title + assignee (no description) — template auto-generates
2. View to confirm → `jira issue view KEY-X`
3. Grab the template ADF from an unfilled issue → `curl` + `jq` (see workflow below)

## Issues

```bash
# List
jira issue list                                 # interactive table view
jira issue list --plain                         # plain output for scripting
jira issue list --raw                           # raw JSON
jira issue list -a$(jira me)                    # assigned to me
jira issue list -yHigh -s"To Do"                # high priority, status
jira issue list --created month                 # created this month
jira issue list -lbackend                       # with label
jira issue list -q "summary ~ cli"              # raw JQL
jira issue list --created -7d                   # last 7 days
jira issue list -w                              # watching
jira issue list -ax                             # unassigned
jira issue list --order-by rank --reverse       # same order as UI
jira issue list --plain --paginate 10           # limit to N results (NOT --limit)
jira issue list --plain --columns KEY,SUMMARY,STATUS  # show specific columns
jira issue list --plain --no-truncate           # show all available columns

# Use -pPROJ to scope to a project (default project from config is used otherwise)

# View
jira issue view KEY-1                           # detailed view with pager
jira issue view KEY-1 --comments 5              # show 5 recent comments

# Create
jira issue create                               # interactive prompt
jira issue create -tBug -s"Summary" -yHigh -lbug -b"Description" --no-input
jira issue create -tStory -s"Title" -PEPIC-42   # attach to epic
jira issue create -tTask -s"Summary" -a$(jira me) --no-input  # create with just title + assignee (template auto-generates in description)

# Edit
jira issue edit KEY-1 -s"New summary" -yHigh -lbug -lurgent --no-input

# Assign
jira issue assign KEY-1 "User Name"
jira issue assign KEY-1 $(jira me)              # assign to self
jira issue assign KEY-1 x                       # unassign

# Transition (move)
jira issue move KEY-1 "In Progress"
jira issue move KEY-1 Done -RFixed -a$(jira me) # with resolution + assignee
jira issue move KEY-1 "In Progress" --comment "Started working"

# Comment
jira issue comment add KEY-1 "Comment body"
jira issue comment add KEY-1 --template /path/to/template.tmpl
jira issue comment add KEY-1 "internal note" --internal

# Link
jira issue link KEY-1 KEY-2 "Blocks"
jira issue link remote KEY-1 https://example.com "Example"

# Clone
jira issue clone KEY-1 -s"Modified summary" -yHigh -a$(jira me)

# Delete
jira issue delete KEY-1
jira issue delete KEY-1 --cascade               # with subtasks
```

## Epics

```bash
jira epic list                                  # explorer view
jira epic list --table                          # table view
jira epic list -r$(jira me) -sOpen              # filtered
jira epic list KEY-1                            # issues in epic
jira epic create -n"Epic Name" -s"Summary" -yHigh -b"Description"
jira epic add EPIC-KEY KEY-1 KEY-2              # add issues
jira epic remove KEY-1 KEY-2                    # remove issues
```

## Sprints

```bash
jira sprint list                                # all sprints
jira sprint list --table                        # table view
jira sprint list --current                      # active sprint
jira sprint list --prev                         # previous sprint
jira sprint list --next                         # next planned
jira sprint list --state future,active          # filter by state
jira sprint list SPRINT_ID                      # issues in sprint
jira sprint list SPRINT_ID -yHigh -a$(jira me)  # filtered
jira sprint add SPRINT_ID KEY-1 KEY-2           # add issues
```

## Boards & Projects

```bash
jira board list                                 # all boards
jira project list                               # all projects
jira open                                       # open project
jira open KEY-1                                 # open issue
```

## Utility

```bash
jira me                                         # current user
jira completion                                 # shell completion
```

## Common Workflows

**Create issue with template (auto-generated):**
```bash
# 1. Create the issue with just title + assignee (template auto-generates in description)
jira issue create -tTask -s"Implement feature X" -a$(jira me) -yMedium --no-input
# → returns KEY-123

# 2. View the issue to see the auto-generated template
jira issue view KEY-123

# 3. Get the template ADF from an unfilled issue
curl -s -u "user@example.com:$JIRA_API_TOKEN" \
  "https://your-domain.atlassian.net/rest/api/3/issue/BIOCL-2160?fields=description" \
  | jq '.fields.description' > /tmp/adf.json

# 4. Edit /tmp/adf.json to add content paragraphs inside each info panel
#    Panel structure: content[0..3] are the 4 sections; each has a bold header + empty paragraph
#    Append paragraph nodes: {"type":"paragraph","content":[{"type":"text","text":"your content"}]}
#    Or use jq:
jq '.content[0].content += [{"type":"paragraph","content":[{"type":"text","text":"- Task item"}]}]' /tmp/adf.json > /tmp/adf_filled.json

# 5. Push via REST API (preserves info panels)
curl -s -X PUT "https://your-domain.atlassian.net/rest/api/3/issue/KEY-123" \
  -u "user@example.com:$JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(jq '{fields: {description: .}}' /tmp/adf_filled.json)"
```

> ⚠️ **Never use `jira issue edit -b"..."` for description** — it replaces the entire ADF with plain text and destroys info panels. Use the REST API + curl + jq instead.

**Add to active sprint:**
```bash
# Find the active sprint ID (may need REST API if jira CLI can't find it)
curl -s -u "user@example.com:$JIRA_API_TOKEN" \
  "https://your-domain.atlassian.net/rest/agile/1.0/board/65/sprint?state=active" \
  | jq '.values[0].id'

# Add issue to sprint
curl -s -u "user@example.com:$JIRA_API_TOKEN" -X POST \
  "https://your-domain.atlassian.net/rest/agile/1.0/sprint/SPRINT_ID/issue" \
  -H "Content-Type: application/json" \
  -d '{"issues": ["KEY-123"]}'
```

**Start work:**
```bash
jira issue move KEY-1 "In Progress"
jira issue assign KEY-1 $(jira me)
```

**Submit for review:**
```bash
jira issue move KEY-1 "In Review"
jira issue comment add KEY-1 "MR: !42"
```

**Mark complete:**
```bash
jira issue move KEY-1 Done -RFixed
```
