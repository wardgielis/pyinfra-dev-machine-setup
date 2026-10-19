# Vendored Polars skill

This directory is a copy of the official Polars agent skill, with a small
number of local additions.

## Source

- Repository: https://github.com/polars-inc/skills
- Tag: `v0.3.1`
- Commit: `70bec73cd09722411492dfd3613c73bb6df979b8`
- Copied: 2026-10-19
- Licence: MIT (see `LICENSE`, Copyright 2026 Robin)

## Files copied from upstream

- `SKILL.md`
- `references/contexts.md`
- `references/expressions.md`
- `references/insight-recipes.md`
- `references/lazy-api.md`
- `references/pandas-to-polars.md`

The reference files are copied from upstream and patched for Polars 2.0; see
Local changes.

## Local changes

1. Rewrote the `description` to start with "Use when" and mention the 2.0
   streaming default. Added `review_after`, `docs_url`, `upstream_version`,
   `upstream_commit`, and `version_pinned` to the `metadata` block. Set the
   compatibility line and `version_pinned` to Polars >= 2.0.
2. Added a short routing note after the title: related skills, when to use
   `[[spark]]` instead of Polars, and the 2.x version target.
3. Added a "Polars 2.0" section with the changes that affect this skill:
   streaming default and row order, eager `read_csv`/`read_ipc`, `explode`
   empty lists, strict horizontal `concat`, renamed or removed APIs, `bin_*`
   binning, and the removed interchange protocol.
4. Added a "Presentation styling" section for the Polars display styling
   guide. The upstream skill does not cover `DataFrame.style` or Great Tables.
5. Patched three reference examples for Polars 2.0:
   - `references/insight-recipes.md`: `qcut` → `bin_quantiles`.
   - `references/pandas-to-polars.md`: `cut` → `bin_intervals`.
   - `references/expressions.md`: removed the integer-to-categorical cast
     suggestion and showed the string-first alternative.

Everything else is upstream text.

## Known drift

- Upstream v0.3.1 was published on 2026-08-21, before Polars 2.0 (2026-10-06).
  This copy adds local 2.0 patches and targets 2.x. Remove the patches when
  upstream publishes a 2.0-aware tag.

## Updating

1. Pick the new upstream tag. Do not track `main`.
2. Download and unpack it into a temporary directory:

   ```sh
   curl -fsSL https://github.com/polars-inc/skills/archive/refs/tags/<tag>.tar.gz \
     -o /tmp/polars-skill.tar.gz
   tar -xzf /tmp/polars-skill.tar.gz -C /tmp
   ```

3. Diff the new `polars/SKILL.md` and `polars/references/` against this
   directory.
4. Copy the new upstream files in. Remove reference files that upstream deleted.
5. Re-apply the local changes listed above, including the three reference
   patches. Keep them in the clearly marked sections so the next diff is easy
   to read.
6. Update the tag, commit, and date in this file and in the `metadata` block
   of `SKILL.md`.
7. Move `review_after` forward by about one month.
8. Confirm the version target still matches the installed Polars major version.
9. Run the skill checks: the directory name must match the frontmatter `name`,
   the description must stay within 1024 characters, and every `[[skill]]`
   link must point to an existing skill.

The repo's skill-freshness plugin will flag this skill when `review_after`
passes, which is the reminder to repeat this procedure.
