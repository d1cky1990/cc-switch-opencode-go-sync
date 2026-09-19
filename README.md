# cc-switch-opencode-go-sync
> [中文说明](README.zh-CN.md)

Sync the [OpenCode Go (Zen)](https://opencode.ai/zen) model list into the
[cc-switch](https://github.com/farion1231/cc-switch) Codex provider mapping table,
so you no longer have to hand-fill menu display name, request model id and
context window every time OpenCode adds or rotates models (including limited-time ones).

No npm package to publish — install straight from GitHub with the skills CLI:

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync -g -y
```

---

## For everyday users: install & use (no coding needed)

### 1. Install the skill (one time)

Pick one:

**Option A — one-line install (recommended).** Works for Codex, Claude Code,
OpenCode and most other agents; `-g` installs globally so every project can use it:

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync -g -y
```

Only want it in Codex?

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync -g -a codex -y
```

Just want to see what would be installed first (changes nothing)?

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync --list
```

**Option B — manual clone.** Clone this repo where your agent looks for skills
(e.g. `<project>/.agents/skills/` or your global skills dir):

```powershell
git clone https://github.com/d1cky1990/cc-switch-opencode-go-sync.git
```

Keep it fresh later with:

```powershell
npx skills update d1cky1990/cc-switch-opencode-go-sync -g -y
```

### 2. Use it: just talk to your AI

You never need to run the script yourself. In any agent that has this skill,
say something like:

- "Sync the new OpenCode Go models into cc-switch"
- "OpenCode Go seems to have limited-time models — sync them for me"
- "同步一下 OpenCode Go 的模型"

What happens next:

1. The agent fetches the latest upstream list and shows you a **diff table**
   (new models / window fixes / display-name updates / possibly-removed ones),
   with a recommended action per row.
2. You confirm — "follow the recommendations" is enough, or decide row by row
   (e.g. "also drop the removed ones").
3. The agent backs up your cc-switch DB + catalog, writes back only the model
   mapping table, and tells you how to make it take effect: re-select the
   provider in cc-switch (or restart cc-switch), then **restart Codex**
   (the model catalog is loaded at startup only).

---

## For developers / AI agents: how it works

This repo is laid out as an
[AI agent skill](https://github.com/mattpocock/skills): `SKILL.md` at the root
(the workflow your agent follows) plus `scripts/` (the sync script).

### Workflow

1. Locates the Codex provider whose `base_url` contains `opencode.ai/zen/go`
   (matched by characteristic, never a hard-coded provider id).
2. Reads the authoritative account-visible model ids from `{base_url}/models`
   using the key already stored in cc-switch (memory only — never printed,
   never written anywhere).
3. Reads display names + context windows from the `opencode-go` entry of
   `https://models.dev/api.json` (maintained by the OpenCode team).
4. Prints a diff table (`NEW` / `LIVE-ONLY` / `CTX` / `NAME` / `STALE`) for the
   user to confirm, backs up the cc-switch DB + catalog, then writes back only
   the `modelCatalog.models` array. `auth` and `config` are left untouched.
5. Writes are always alphabetically sorted by model id, so the switcher menu
   stays easy to scan.

### Requirements

- Windows + Python 3 (standard library only, no dependencies)
- cc-switch with an OpenCode Go (Zen) provider configured for the Codex app

### Script usage

Dry-run first (read-only, changes nothing):

```powershell
python scripts/sync_opencode_go.py
```

Apply after the user confirmed the table (backs up first):

```powershell
python scripts/sync_opencode_go.py --apply --skip-new ox-alpha-free --add-live deepseek-flash --drop-stale
```

| Flag | Effect |
|---|---|
| `--apply` | write back to the cc-switch DB (backs up DB + catalog first) |
| `--keep-names` | skip display-name updates |
| `--rename ID=NAME` | force one display name (repeatable; pairs with `--keep-names`) |
| `--skip-new ID` | skip one NEW entry this time (repeatable) |
| `--add-live ID` | add a LIVE-ONLY id with display name = id and blank window (repeatable) |
| `--set-window ID=NUM` | force a context window (repeatable) |
| `--drop-stale` | delete STALE entries instead of keeping them marked |
| `--no-live` | skip the authenticated live check (diff from the directory only) |

### Window-equivalence notes

`1000000 / 1024000 / 1048576` are treated as the same "1M tier"
(and `256000 / 262144` as "256K tier") — notation differences are not flagged,
only real cross-tier changes are. Unknown ids get a blank window (safe:
cc-switch falls back to 128K, which only compacts earlier instead of breaking).

### Safety red lines (enforced by `SKILL.md`)

- The provider key goes DB → memory → HTTPS Authorization header only. It is
  never passed via CLI args, env vars, files, logs, or error output.
- Default is dry-run; every write is backed up first and needs explicit user
  confirmation. `auth` / `config` fields and other providers are never touched.

## License

MIT — see [LICENSE](LICENSE).
