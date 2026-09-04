import type { Plugin } from "@opencode-ai/plugin"
import { readdir, readFile } from "fs/promises"
import { join } from "path"
import { homedir } from "os"

const SkillFreshnessPlugin: Plugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        await checkSkillFreshness(client)
      }
    },
  }
}

export default SkillFreshnessPlugin

async function getSkillPaths(): Promise<string[]> {
  const defaultPath = join(homedir(), ".config", "opencode", "skills")
  const paths = [defaultPath]

  try {
    const configPath = join(homedir(), ".config", "opencode", "opencode.jsonc")
    const raw = await readFile(configPath, "utf-8")
    // Strip single-line and block comments for JSONC compatibility
    const stripped = raw.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "")
    const config = JSON.parse(stripped)
    const extraPaths: string[] = config?.skills?.paths ?? []
    for (const p of extraPaths) {
      const expanded = p.replace(/^~/, homedir())
      if (!paths.includes(expanded)) paths.push(expanded)
    }
  } catch {
    // config unreadable or no skills.paths — use default only
  }

  return paths
}

async function checkSkillFreshness(client: any) {
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
    await client.tui.showToast({ body: { message, variant: "warning", duration: 600_000 } })
  } catch {
    await client.app.log({ body: { service: "skill-freshness", level: "warn", message } })
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
