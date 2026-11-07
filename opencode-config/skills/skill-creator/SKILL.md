---
name: skill-creator
description: Use when creating a new opencode skill, improving or auditing an existing one, running test prompts against a skill with a with-skill versus baseline comparison, benchmarking skill quality, reviewing results in the eval viewer, or tuning a skill description so it triggers correctly. Make sure to use this whenever the user says things like "turn this workflow into a skill", "test my skill", or "make this skill better", even if they never name skill-creator. Pair it with the opencode skill, which owns the repo conventions for naming, frontmatter, vendoring and deploy.
license: Apache-2.0 (see LICENSE.txt)
metadata:
  review_after: "2026-12-07"
  docs_url: "https://opencode.ai/docs/skills/"
  upstream_repo: "https://github.com/anthropics/skills (skills/skill-creator)"
  upstream_commit: "2c5958ecac7cee2b583967a2c4981d0f4a75c579"
---

# skill-creator

Goal: take a skill from idea to a tested, well-triggering `SKILL.md` by looping draft, test, review, improve. Adapted from Anthropic's skill-creator for opencode; every local change is listed in `VENDORED.md`.

**Related skills**: [[opencode]] defines what a valid skill looks like in this repo (naming, frontmatter, size, lifecycle, vendoring, validation checklist) and where it deploys. This skill covers the other half, how to test and improve one. Read [[opencode]] before writing the first draft, and do not duplicate its rules here. Use [[python]] when a skill bundles scripts.

## The loop

- Decide what the skill should do and roughly how
- Write a draft
- Create a few test prompts and run an agent with access to the skill on them
- Help the user evaluate the results, qualitatively and quantitatively
  - While runs are in progress, draft quantitative assertions if none exist, and explain them
  - Use `eval-viewer/generate_review.py` so the user can look at the outputs and the metrics
- Rewrite the skill based on the user's feedback and any glaring flaws in the benchmark
- Repeat until satisfied, then expand the test set and try again at larger scale

Work out where the user is in this loop and jump in there. If they already have a draft, go straight to testing. If they say they do not want formal evaluation and just want to talk it through, do that instead. The order is flexible.

## Communicating with the user

Users range from people who write Python daily to people who have just opened a terminal. Read the context cues. "Evaluation" and "benchmark" are borderline but fine; explain "JSON" and "assertion" briefly unless the user has shown they know them.

---

## Where things live (opencode specifics)

- **The skill** lives in `opencode-config/skills/<name>/` in the pyinfra repo. Edit it there, never in `~/.config/opencode` (repo-first rule in [[opencode]]).
- **The workspace** (test outputs, benchmarks, feedback) goes in `~/skill-workspaces/<skill-name>-workspace/`, not next to the skill. The skills directory is a discovery source, and test runs can write files named `SKILL.md`; keeping the workspace out of it stops stray skills from being registered.
- **A new skill is not visible yet.** The `skill` tool only sees skills present at session start, so a skill you just wrote cannot be loaded by ID. When you start test runs, give each subagent the full path and tell it to read that `SKILL.md` first. Restart opencode (or open a new session) after finishing.
- **Other discovery sources.** opencode also reads `~/.claude/skills` and `~/.agents/skills` at lower precedence. If a skill with the same ID exists there, the repo one wins, but check for it before inventing a new name.
- **`<skill-creator-path>`** below means the directory that holds this `SKILL.md`. The `skill` tool reports it as the base directory.

---

## Creating a skill

### Capture intent

Start from what the user wants. The conversation may already contain a workflow to capture ("turn this into a skill"). If so, extract answers from the history first, namely the tools used, the sequence of steps, corrections the user made, and input and output formats, and let the user fill gaps and confirm before you continue.

1. What should this skill enable the agent to do?
2. When should it trigger (what user phrases and contexts)?
3. What is the expected output format?
4. Should we set up test cases? Skills with objectively checkable outputs (file transforms, data extraction, code generation, fixed workflows) benefit from them. Skills with subjective output (writing style, design) often do not. Suggest a default, let the user decide.

### Interview and research

Ask about edge cases, input and output formats, example files, success criteria and dependencies. Wait to write test prompts until this is settled. Check which MCP servers are available and whether they help with research (docs, similar skills, best practices). Research in parallel with subagents when useful, and arrive with context so the user has less to explain.

### Write the SKILL.md

Frontmatter fields, name rules, size limits and the body skeleton are defined in [[opencode]] ("Creating or updating a skill"). The points that decide whether a skill works:

- **description** is the primary trigger. It states what the skill does and the situations that call for it, and it starts with "Use when" in this repo. All "when to use" information goes here, not in the body, because the body is only read after the skill has triggered. Agents tend to undertrigger skills, so make the description a little pushy: name the class of work and the phrasings that should fire it, including cases where the user does not mention the tool. For example, "Use when building dashboards or showing any kind of company data, even if the user never says dashboard" beats "How to build a dashboard".
- **Progressive disclosure.** Three levels load in turn: name and description (always in context), the `SKILL.md` body (when triggered, ideally under 500 lines), and bundled resources (on demand; scripts can run without being read). If the body nears the limit, add a layer of hierarchy with clear pointers on when to read each file. Give reference files over about 300 lines a table of contents.
- **Organise by variant** when a skill covers several frameworks or targets: keep the workflow and selection logic in `SKILL.md` and put each variant in `references/<variant>.md`, so the agent reads only the one it needs.
- **Bundled resources**: `scripts/` for deterministic or repeated work, `references/` for docs loaded as needed, `assets/` for files used in output.

#### Principle of lack of surprise

A skill's contents must not surprise the user given its description. No malware, exploit code or anything that could compromise security, and do not go along with requests for misleading skills or skills built to enable unauthorised access or data exfiltration. Role-play skills ("act as an XYZ") are fine.

#### Writing patterns

Prefer the imperative. Define output formats explicitly:

```markdown
## Report structure
Use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

Examples help. Format them like this, and deviate if "Input" and "Output" are part of the example itself:

```markdown
## Commit message format
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

#### Writing style

Explain why something matters instead of reaching for heavy MUSTs. Models have good theory of mind, and a reason generalises where a rule does not. Keep the skill general rather than tuned to your test examples. Write a draft, read it again with fresh eyes, and improve it.

### Test cases

After the draft, write 2-3 realistic test prompts, the kind of thing a real user would type. Share them: "Here are a few test cases I'd like to try. Do these look right, or do you want to add more?" Then run them.

Save them to `evals/evals.json` in the skill directory. Do not write assertions yet; those come in the next step while runs are in progress.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

`references/schemas.md` has the full schema, including the `assertions` field you add later.

---

## Running and evaluating test cases

This is one continuous sequence. Do not stop partway through, and do not substitute another testing skill.

Put results under `~/skill-workspaces/<skill-name>-workspace/`. Organise by iteration (`iteration-1/`, `iteration-2/`, ...) and, within each, a directory per test case (`eval-0/`, `eval-1/`, ...). Create directories as you go, not upfront.

### Step 1: Spawn all runs (with-skill and baseline) in the same turn

For each test case, start two subagents in the same turn, one with the skill and one without. Use the `subagent` tool with the `general` agent and `background: true`, and issue all the calls in one response so everything finishes around the same time. Do not launch the with-skill runs first and come back for baselines later.

**With-skill run**, prompt:

```
Execute this task.
- First read <skill-path>/SKILL.md in full and follow it. The skill is not in your skill list, so load it by path.
- Task: <eval prompt>
- Input files: <eval files if any, or "none">
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- Outputs to save: <what the user cares about, e.g. "the .docx file", "the final CSV">
```

**Baseline run**, same prompt, and the baseline depends on context:

- **New skill**: no skill at all. Same prompt, no skill path, save to `without_skill/outputs/`.
- **Improving an existing skill**: the old version. Before editing, snapshot it (`cp -r <skill-path> <workspace>/skill-snapshot/`), point the baseline subagent at the snapshot, and save to `old_skill/outputs/`.

Write an `eval_metadata.json` for each test case (assertions may be empty for now). Give each eval a descriptive name that says what it tests, not just "eval-0", and use it for the directory too. If an iteration uses new or modified prompts, write these files again for each new directory; do not assume they carry over.

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

### Step 2: While runs are in progress, draft assertions

Use the waiting time. Draft quantitative assertions for each test case and explain them to the user. If assertions already exist in `evals/evals.json`, review them and explain what they check.

Good assertions are objectively verifiable and have descriptive names that read clearly in the benchmark viewer. Subjective skills (writing style, design quality) are better judged qualitatively, so do not force assertions onto them.

Update `eval_metadata.json` and `evals/evals.json` once drafted. Also tell the user what the viewer will show: the qualitative outputs and the quantitative benchmark.

### Step 3: Capture timing as runs complete

When a subagent finishes, you get a completion notice. If it reports `total_tokens` and `duration_ms`, save them straight away to `timing.json` in that run's directory, because this is the only time the data is available:

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

If the notice carries no usage numbers, record wall-clock seconds from when you launched and when the notice arrived, and leave `total_tokens` out. The aggregation script tolerates missing values and says so in the benchmark notes. Handle each notice as it arrives instead of batching.

### Step 4: Grade, aggregate, launch the viewer

When all runs are done:

1. **Grade each run.** Spawn a grader subagent (or grade inline) that reads `agents/grader.md` and checks each assertion against the outputs. Save to `grading.json` in each run directory. The expectations array must use the fields `text`, `passed` and `evidence`, because the viewer depends on those exact names. For assertions that can be checked in code, write and run a script instead of eyeballing; it is faster, more reliable and reusable across iterations.

2. **Aggregate into a benchmark.** From the skill-creator directory:

   ```bash
   cd <skill-creator-path> && python3 -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
   ```

   This writes `benchmark.json` and `benchmark.md` with pass rate, time and tokens per configuration (mean ± stddev, and the delta). If you build `benchmark.json` by hand, follow `references/schemas.md`. List each with-skill run before its baseline counterpart.

3. **Do an analyst pass.** Read the benchmark and surface what the aggregates hide, following the "Analyzing Benchmark Results" section of `agents/analyzer.md`: assertions that pass regardless of the skill (non-discriminating), high-variance evals (possibly flaky), and time and token tradeoffs. Add your notes to the `notes` list in `benchmark.json` after any notes the script already wrote; do not replace those.

4. **Launch the viewer** with outputs and benchmark together. Run it as a background shell command so you can stop it later:

   ```bash
   python3 <skill-creator-path>/eval-viewer/generate_review.py \
     <workspace>/iteration-N \
     --skill-name "my-skill" \
     --benchmark <workspace>/iteration-N/benchmark.json
   ```

   For iteration 2 and later, add `--previous-workspace <workspace>/iteration-<N-1>`. On a machine with no display (a remote workspace), add `--static <output_path>` to write a standalone HTML file; feedback then downloads as `feedback.json` when the user clicks "Submit All Reviews", and you copy it into the workspace. Use `generate_review.py` as is; do not write custom HTML.

5. **Tell the user** something like: "I've opened the results in your browser. 'Outputs' lets you click through each test case and leave feedback, 'Benchmark' shows the quantitative comparison. Come back and tell me when you're done."

Generate the viewer before you evaluate the outputs yourself. Get the examples in front of the human early.

### What the user sees in the viewer

The "Outputs" tab shows one test case at a time: the prompt, the output files rendered inline where possible, the previous iteration's output (collapsed, iteration 2+), formal grades (collapsed), a feedback box that auto-saves, and the previous feedback (iteration 2+). The "Benchmark" tab shows pass rates, timing and token use per configuration with per-eval breakdowns and the analyst's observations. Navigation is by prev/next or arrow keys. "Submit All Reviews" saves everything to `feedback.json`.

### Step 5: Read the feedback

```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "the chart is missing axis labels", "timestamp": "..."},
    {"run_id": "eval-1-with_skill", "feedback": "", "timestamp": "..."},
    {"run_id": "eval-2-with_skill", "feedback": "perfect, love this", "timestamp": "..."}
  ],
  "status": "complete"
}
```

Empty feedback means the user thought it was fine. Focus on the cases with specific complaints. Stop the viewer when you are done with it.

---

## Improving the skill

This is the heart of the loop.

### How to think about improvements

1. **Generalise from the feedback.** You and the user iterate on a few examples because it is fast, but the skill will be used across many different prompts. Avoid fiddly, overfitted changes and oppressively rigid MUSTs. If something stubborn keeps failing, try a different metaphor or a different working pattern; it is cheap to try.

2. **Keep the prompt lean.** Remove what is not pulling its weight. Read the transcripts, not just the final outputs. If the skill makes the model waste time on unproductive steps, cut the parts that cause it and see what happens.

3. **Explain the why.** Today's models are smart. Give them the reasoning behind each instruction so they can go beyond rote following. Even if the user's feedback is terse or frustrated, work out what they actually need and put that understanding into the instructions. Writing ALWAYS or NEVER in capitals is a yellow flag; reframe it with a reason where you can.

4. **Look for repeated work across test cases.** If every subagent independently wrote a similar helper script, bundle that script in `scripts/` and tell the skill to use it. Write it once instead of having every future run reinvent it.

Take your time. Write a draft revision, look at it again as the user would, and improve it.

### The iteration loop

1. Apply the improvements.
2. Rerun all test cases into `iteration-<N+1>/`, including baselines. For a new skill the baseline stays `without_skill`. For an existing skill, choose the original version or the previous iteration, whichever answers the user's question.
3. Launch the viewer with `--previous-workspace` pointing at the previous iteration.
4. Wait for the user to finish reviewing.
5. Read the feedback, improve, repeat.

Stop when the user is happy, all feedback is empty, or you are not making meaningful progress.

---

## Blind comparison (optional)

When the user asks whether a new version is really better, give two outputs to an independent subagent without saying which is which, let it judge, then analyse why the winner won. Read `agents/comparator.md` and `agents/analyzer.md`. The human review loop is usually enough.

---

## Description optimization

The description decides whether the skill is chosen at all. opencode shows the model each permitted skill's ID and description at every step, and the model loads the full body through the `skill` tool. Agents in this setup are also told by `AGENTS.md` to look for relevant skills at the start of a session, which raises triggering compared with a stock setup, so an under-triggering description is less common here and a vague one that fires on everything is the bigger risk. Offer this step once the skill itself is in good shape.

### Step 1: Write trigger eval queries

Make 20 queries, a mix of should-trigger and should-not-trigger, saved as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

They must be realistic and specific, the kind of thing a user would actually type, with file paths, personal context, column names, company names, a little backstory. Some in lowercase, with abbreviations or typos, in a mix of lengths. Focus on edge cases, not clear-cut ones.

Bad: `"Format this data"`, `"Extract text from PDF"`, `"Create a chart"`.

Good: `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a percentage. The revenue is in column C and costs are in column D i think"`

For the 8-10 **should-trigger** queries, vary the phrasing (formal and casual), include cases where the user never names the skill or file type but clearly needs it, include uncommon uses, and include cases where this skill competes with another but should win.

For the 8-10 **should-not-trigger** queries, the valuable ones are near-misses that share keywords with the skill but need something else: adjacent domains, ambiguous phrasing where naive keyword matching would fire, and cases where another skill is the better tool. Obviously irrelevant negatives test nothing. Check the negatives against the real skill list (for example [[polars]] versus [[spark]]) so you are not asserting something another skill legitimately handles.

Queries must be substantive. A one-step request the model can do with basic tools may never consult any skill, whatever the description says, so it makes a poor test.

### Step 2: Review with the user

1. Read the template `assets/eval_review.html`.
2. Replace `__EVAL_DATA_PLACEHOLDER__` with the JSON array (no quotes, it is a JS assignment), `__SKILL_NAME_PLACEHOLDER__` with the skill name and `__SKILL_DESCRIPTION_PLACEHOLDER__` with the current description.
3. Write it to `/tmp/eval_review_<skill-name>.html` and open it with `open`.
4. The user edits queries, toggles should-trigger, adds or removes entries and clicks "Export Eval Set". It downloads to `~/Downloads/eval_set.json`; check for the newest copy if several exist.

Bad queries produce bad descriptions, so this step matters.

### Step 3: Run the optimization loop (experimental)

`scripts/run_loop.py` splits the eval set 60/40 into train and held-out test, scores the current description (each query run several times), asks the model to propose a better one from the failures, and repeats up to a maximum number of iterations. It picks `best_description` by test score, not train score, to avoid overfitting.

```bash
cd <skill-creator-path> && python3 -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <provider/model, e.g. claude-agent/sonnet> \
  --max-iterations 5 \
  --verbose
```

Run it as a background shell command and tail the output so you can report progress.

**Status: experimental.** Upstream ran this through `claude -p`. Here the scripts were ported to `opencode run --format json`. Each query runs in a throwaway directory holding a candidate skill under `.opencode/skills/`, and counts as a trigger when the first tool call is `skill` with that candidate's ID. The event parsing was checked against a live run, but in testing the candidate skill was not reliably visible to the model when run through the shared background service, so a result of 0% triggered may mean "the harness could not see the skill", not "the description is bad". Before you trust any numbers:

1. Run `python3 -m scripts.run_eval` on a one-query set whose query is a close paraphrase of the description, with a model that is not too weak, and confirm it triggers at least once.
2. If it never does, stop. Do not let the loop rewrite descriptions against noise. Fall back to manual tuning: read the near-miss queries together with the user, compare the description against them, and iterate by hand.

### Step 4: Apply the result

Take `best_description`, update the frontmatter, show the user before and after with the scores, and keep it inside the 1024-character limit and the "Use when" convention from [[opencode]].

---

## Finish

1. **Validate**: `python3 <skill-creator-path>/scripts/quick_validate.py <skill-dir>` (needs PyYAML, so `uv run --with pyyaml python3 ...` works anywhere). It checks frontmatter, that the name matches the directory, the "Use when" opening, balanced code fences, double-bracket cross-links that point at sibling skills, and that there is exactly one `SKILL.md`.
2. Walk through the validation checklist in [[opencode]], including running the examples and three realistic sample prompts.
3. Set `review_after` about a month out.
4. Commit in the pyinfra repo. Org-specific skills go in `.gitignore` instead, as [[opencode]] describes, with a reminder to back them up.
5. Restart opencode or start a new session so the skill appears in the list.

`scripts/package_skill.py` builds a `.skill` archive, which is only for sharing a skill outside the repo; deploying here is just committing the directory.

---

## Reference files

`agents/` holds instructions for specialised subagents. Read them when you spawn the relevant one:

- `agents/grader.md` evaluates assertions against outputs
- `agents/comparator.md` runs a blind A/B comparison of two outputs
- `agents/analyzer.md` analyses why one version beat another

`references/schemas.md` has the JSON structures for `evals.json`, `grading.json`, `benchmark.json` and the rest.

---

Repeating the core loop for emphasis:

- Work out what the skill is about
- Draft or edit it
- Run subagents with access to the skill on the test prompts
- Evaluate the outputs with the user: build `benchmark.json`, run `eval-viewer/generate_review.py`, run the quantitative checks
- Repeat until you and the user are satisfied
- Validate, commit, restart

Add these steps to your to-do list so you do not skip any, in particular "create evals and run `generate_review.py` so the user can review the test cases".
