---
name: plain-english
description: Use when writing or reviewing any text that people will read, such as code comments, docstrings, READMEs, commit messages, merge request or pull request descriptions, issue text, changelogs, wiki pages and documentation, even if the user never mentions style or English. Load it together with the python skill whenever a docstring or comment is written. Gives simple, easy to read English rules for a team of non-native speakers, with no backticks, no em dashes and few special characters. Not for translation, code logic or formal marketing text.
metadata:
  review_after: "2026-12-07"
---

# plain-english

Goal: write text that a non-native English reader understands on the first read. Our team is international, and most of us do not have English as a first language. Simple words and short sentences are faster to read, easier to translate, and leave less room for mistakes.

**Related skills**: [[python]] for docstring layout (Google style) and code style. This skill covers the words. The python skill covers the structure. [[caveman]] is only for terse chat replies. Text that is saved or shared always follows this skill, even when caveman is on. This skill does not apply to chat replies. Both skills are loaded in every session through the instructions list in the opencode config, so they do not conflict: caveman for chat, this skill for code, docstrings and comments.

## Core rules

1. **Use short sentences.** Aim for 15 to 20 words. If a sentence has two ideas, split it in two.
2. **Use common words.** Choose the simple word. See the word list below.
3. **Use the active voice.** Say who does what. Write "The function reads the file", not "The file is read by the function".
4. **Use the present tense.** Write "Returns the user", not "Will return the user". The one exception is the summary line of a docstring, which uses the imperative mood ("Return the user"). See Docstrings.
5. **Put the main point first.** Start with what the code does. Add details after.
6. **Use one word for one idea.** If you say "folder" once, do not say "directory" or "path" later for the same thing. Pick one term and keep it.
7. **Avoid idioms and slang.** Phrases like "out of the box", "under the hood", "a no brainer", "bite the bullet" or "ballpark" are hard to translate. Say the plain meaning.
8. **Avoid phrasal verbs when a single verb exists.** Write "remove" instead of "take out", "start" instead of "kick off", "find" instead of "figure out".
9. **Do not use humor, sarcasm or hints.** They do not translate well.
10. **Be specific.** Write "Raises an error if the file is empty", not "Handles bad input".
11. **Do not start a sentence with a code name.** Function, variable, class and column names stay lowercase, and they do not begin a sentence. Start with the role instead, such as "The function" or "This step". Write "The classify_taxon function must return the bare name", not "Classify_taxon must return the bare name". Do not uppercase the first letter of a code name either.

## Characters to avoid

Many special characters make text hard to read and hard to search. They also break in some tools.

- **No backticks.** Do not wrap names in backticks inside comments, docstrings, commit messages or MR text. Write the name as plain text. Example: "Pass the user_id to the function."
- **No em dashes and no en dashes.** Use a period, a comma, or brackets instead. Split the sentence if needed.
- **No arrows in prose.** Write "to" instead, for example "from the file to the table". The `->` arrow is allowed in code, such as type hints, as the python skill says. No unicode symbols.
- **No emoji.**
- **No fancy quotes.** Use plain straight quotes, and only when really needed.
- **Avoid semicolons.** Use two sentences.
- **Use brackets and exclamation marks rarely.** One short bracket is fine. Do not use exclamation marks.
- **Avoid slashes for "or" and "and".** Write "read or write", not "read/write".
- **Avoid bold, italics and long lists inside code comments and docstrings.** Plain text is enough there.

Exception: if a tool needs a special format (for example Markdown headings in a README), use only the minimum the format needs. Code blocks belong in README and docs pages. Docstrings never use code blocks or backticks, so write examples there as indented plain text (see the python skill).

## Word list

| Instead of | Write |
|---|---|
| utilize, leverage | use |
| initiate, commence | start |
| terminate | stop, end |
| facilitate | help, allow |
| in order to | to |
| prior to | before |
| subsequent to | after |
| due to the fact that | because |
| in the event that | if |
| a number of | some, several |
| approximately | about |
| additional | more, extra |
| demonstrate | show |
| obtain | get |
| require | need |
| modify | change |
| indicate | show |
| ensure | make sure |
| however | but |
| therefore | so |
| numerous | many |
| endeavor, attempt | try |
| is able to | can |
| deprecated | old, will be removed |
| gracefully | without an error |
| under the hood | inside |
| out of the box | by default |
| kick off, spin up | start |
| figure out | find, work out |
| deal with | handle |
| a lot of | many, much |

## Docstrings

Follow the Google layout from the python skill. Use these word rules on top:

- The first line is one short sentence. It starts with an imperative verb, as the python skill says: "Return", "Read", "Check", "Build". Use the same form as the surrounding code.
- Say what the function does and why it exists. Do not repeat the code line by line.
- Describe each argument in a short phrase. Add the unit or the allowed values if it matters (for example "in seconds").
- Say when it raises an error, and which error.
- Skip sections that add nothing. A short function can have only one line.

Before:

```python
def get_rows(path):
    """Utilizes pandas in order to obtain the rows -- will return None if the file isn't there!"""
```

After:

```python
def read_rows(path):
    """Read the rows from a CSV file.

    Args:
        path: Path to the CSV file.

    Returns:
        A list of rows, or None if the file does not exist.
    """
```

## Code comments

- Explain why, not what. The code already shows what.
- Keep them short. One line is best.
- Update or delete a comment when the code changes.
- Write a TODO as `# TODO(owner): reason`, with the reason as a full sentence. Example: "# TODO(data-team): Remove this when the API v1 is turned off." The python skill sets this format.

Before:

```python
# increment i by one (this is a hack, don't judge me!)
```

After:

```python
# The API starts counting at 1, so add 1 to the index.
```

## Commit messages

- Subject line: imperative, 50 characters or less, no period. Example: "Add retry to the upload job".
- Leave one empty line, then a short body if needed.
- The body says why the change is needed and what changed. It does not retell the diff.
- Follow any format the repo already uses (for example conventional commits). This skill only sets the wording.

Before: "Refactored the upload stuff -- it was kinda broken, so now it gracefully retries".

After:

```text
Add retry to the upload job

The upload failed when the network was slow. Now the job tries
three times before it stops with an error.
```

## Merge request and pull request descriptions

Use three short parts, in this order:

1. **What**: one or two sentences about the change.
2. **Why**: the problem it solves, with a link to the issue.
3. **How to test**: numbered steps, one action per step.

## READMEs and documentation

- Start with one sentence that says what the project does.
- Use short headings and short paragraphs.
- Write steps as a numbered list with one action per step.
- Show an example before a long explanation.
- Explain an acronym the first time you use it.
- Write "you" for the reader, and "we" only for the team.

## Check before you finish

Read the text once and ask:

- Is every sentence short and clear on the first read?
- Is there a simpler word for any word I used?
- Did I use the same word for the same idea?
- Are there backticks, em dashes, arrows, emoji or idioms left?
- Does the first line say the main point?
- Would a colleague who reads English slowly understand this?

When you review other people's text, suggest the simple version and say why in one short sentence. Do not rewrite meaning, only wording.
