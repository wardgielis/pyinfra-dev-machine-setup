import { Plugin } from "@opencode/plugin"

export default Plugin.define({
  id: "skill-freshness",
  setup() {
    // The freshness check runs in the CLI (TUI) entrypoint (`tui.ts`), where
    // toasts are available. This server entrypoint exists so the plugin has a
    // stable id and the documented directory layout (server + TUI entrypoints
    // kept together).
  },
})
