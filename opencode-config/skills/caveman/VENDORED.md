# Vendored: caveman

- **Source**: https://github.com/JuliusBrussee/caveman, file skills/caveman/SKILL.md
- **Release**: v4.0.1
- **Commit**: c310c9d300df13a1dd9f5c086120ffd857a164a1 (2026-11-07)
- **Copied on**: 2026-11-07
- **License**: Apache-2.0 (LICENSE copied from the repo root)
- **Files copied**: SKILL.md, LICENSE. Not vendored: ultracave, megacave, caveman-compress, the CLI and the proxy.

## Local changes

1. Frontmatter: description rewritten to start with "Use when" (repo rule). Caveman is on by default for chat replies, and it lists the exceptions (code, docstrings, comments, commits, docs, architecture and process explanations). Added metadata (review_after, docs_url).
2. Added a short vendoring note and a link to plain-english under the title.
3. Persistence: removed the hook, alias and mode tracking text, because only the basic caveman is vendored.
4. Rule 4: keep articles by default. Upstream makes them optional. Our readers are not native speakers, so dropped articles hurt more than they save. Example fixed to match.
5. "When to break the rules", item 5: points to plain-english, adds docstrings, and no longer mentions caveman-compress.
6. Persistence: always on by default instead of starting on request. Added item 6 to "When to break the rules": detailed architecture or process explanations use full sentences.
7. Description: removed "load it at the start of every session". The skill is already injected through the instructions list.
8. New rule 8: decisions and diagnoses get a verdict, one reason, and one next step, 5 lines or fewer. Later rules renumbered (9 session start, 10 language, 11 never perform).
9. New rule 9: announcing loaded skills at session start takes one line.
10. "When to break the rules", item 6: only an explicit "explain how it works" request gets a long answer. Item 8: only the question itself uses full sentences.
11. Pre-send check: added items 5 and 6 (cut lists, aim for 3 lines). Added an Example section with the aws MCP question.
12. Rule 8: a cause plus two or more steps or facts goes in short bullets (review feedback, iteration 1).
13. "When to break the rules", item 6: detailed explanations have a budget of about 250 words and 3 or 4 sections, main path only (review feedback, iteration 1: the long mode was still too long).

To update: diff the new upstream SKILL.md against these changes, reapply them, and update the release and commit above.
