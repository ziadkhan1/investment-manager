# Claude Code Projects — Workspace Index

This repo is a **multi-task workspace**. Each task lives in its own folder with its
own `CLAUDE.md` context. When working on a task, read that folder's `CLAUDE.md` —
it holds the detailed, task-specific instructions.

| Folder | Task | Context |
|---|---|---|
| `bluecoins/` | Bluecoins net worth: Drive `.fydb` → live-rate net worth calc → Google Sheets → web dashboard | [bluecoins/CLAUDE.md](bluecoins/CLAUDE.md) |
| `qbo/` | QuickBooks Online API → account heads / P&L → Synapse/Fabric Delta tables | [qbo/CLAUDE.md](qbo/CLAUDE.md) |
| `cloud-cost-report/` | T-SQL query work for a cloud cost report | [cloud-cost-report/CLAUDE.md](cloud-cost-report/CLAUDE.md) |

## Conventions across tasks
- **Secrets** never get committed (`*.json`, `.env`, `secrets/` are git-ignored).
  The one exception is `bluecoins/docs/manifest.json` (a public PWA manifest).
- **CI** lives in `.github/workflows/`:
  - `networth.yml` — runs the Bluecoins calculator daily (works inside `bluecoins/`).
  - `pages.yml` — deploys `bluecoins/docs` to GitHub Pages on push.
- Keep each task self-contained inside its folder; don't reintroduce shared files
  at the repo root unless they're genuinely cross-task.
