import { Plugin } from "@opencode/plugin/tui"
import { readdir, readFile } from "fs/promises"
import { join } from "path"
import { homedir } from "os"

export default Plugin.define({
  id: "skill-freshness",
  setup(context) {
    const stop = context.data.on("session.created", () => {
      void checkSkillFreshness(context)
    })
    return () => stop()
  },
})

type ToastContext = {
  ui: {
    toast: {
      show(toast: { message: string; variant: string; duration?: number }): void
    }
  }
}

// JSONC-aware parse: strips `//` and `/* */` comments and trailing commas
// while respecting string literals, so values like "https://..." survive.
function parseJsonc(text: string): unknown {
  let out = ""
  let i = 0
  let inString = false
  let escaped = false
  while (i < text.length) {
    const ch = text[i]
    if (inString) {
      out += ch
      if (escaped) escaped = false
      else if (ch === "\\") escaped = true
      else if (ch === '"') inString = false
      i++
      continue
    }
    if (ch === '"') {
      inString = true
      out += ch
      i++
      continue
    }
    if (ch === "/" && text[i + 1] === "/") {
      while (i < text.length && text[i] !== "\n") i++
      continue
    }
    if (ch === "/" && text[i + 1] === "*") {
      i += 2
      while (i < text.length && !(text[i] === "*" && text[i + 1] === "/")) i++
      i += 2
      continue
    }
    if (ch === ",") {
      let j = i + 1
      while (j < text.length && /\s/.test(text[j])) j++
      if (text[j] === "}" || text[j] === "]") {
        i++
        continue
      }
    }
    out += ch
    i++
  }
  return JSON.parse(out)
}

async function getSkillPaths(): Promise<string[]> {
  const defaultPath = join(homedir(), ".config", "opencode", "skills")
  const paths = [defaultPath]

  try {
    const configPath = join(homedir(), ".config", "opencode", "opencode.jsonc")
    const raw = await readFile(configPath, "utf-8")
    const config = parseJsonc(raw) as { skills?: string[] | { paths?: string[] } }
    // V2 config: `skills` is an ordered array. Fall back to the V1
    // `skills.paths` object so the plugin still works against an unmigrated config.
    const configured: string[] = Array.isArray(config?.skills)
      ? config.skills
      : (config?.skills?.paths ?? [])
    for (const p of configured) {
      const expanded = p.replace(/^~/, homedir())
      if (!paths.includes(expanded)) paths.push(expanded)
    }
  } catch {
    // config unreadable or no skills paths — use default only
  }

  return paths
}

async function checkSkillFreshness(context: ToastContext) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const stale: string[] = []
  const seen = new Set<string>()
  const skillPaths = await getSkillPaths()

  for (const skillsDir of skillPaths) {
    try {
      const entries = await readdir(skillsDir, { withFileTypes: true })
      for (const entry of entries) {
        if (!entry.isDirectory()) continue
        if (seen.has(entry.name)) continue
        seen.add(entry.name)
        try {
          const skillContent = await readFile(join(skillsDir, entry.name, "SKILL.md"), "utf-8")
          const parsed = parseReviewAfter(skillContent, entry.name)
          if (parsed && parsed.date <= today) {
            stale.push(`${parsed.name} (due ${parsed.reviewAfter})`)
          }
        } catch {
          // no SKILL.md or no metadata — skip silently
        }
      }
    } catch {
      // directory doesn't exist — skip
    }
  }

  if (stale.length === 0) return

  const message =
    stale.length === 1
      ? `Skill may be outdated — consider refreshing: ${stale[0]}`
      : `${stale.length} skills may be outdated — consider refreshing: ${stale.join(", ")}`

  try {
    context.ui.toast.show({ message, variant: "warning", duration: 600_000 })
  } catch {
    console.warn(`[skill-freshness] ${message}`)
  }
}

function parseReviewAfter(
  content: string,
  dirName: string,
): { name: string; reviewAfter: string; date: Date } | null {
  const fm = content.match(/^---\n([\s\S]*?)\n---/)
  if (!fm) return null

  const frontmatter = fm[1]
  const nameMatch = frontmatter.match(/^name:\s*(.+)$/m)
  const name = nameMatch ? nameMatch[1].trim() : dirName

  const reviewAfterMatch = frontmatter.match(/review_after:\s*["\']?([^"\'\n\r]+)["\']?/)
  if (!reviewAfterMatch) return null

  const reviewAfter = reviewAfterMatch[1].trim()
  const date = new Date(reviewAfter)
  if (isNaN(date.getTime())) return null

  date.setHours(0, 0, 0, 0)
  return { name, reviewAfter, date }
}
