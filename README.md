# cc-switch-opencode-go-sync
> [中文说明](README.zh-CN.md)


Sync the [OpenCode Go (Zen)](https://opencode.ai/zen) model list into the
[cc-switch](https://github.com/farion1231/cc-switch) Codex provider mapping table,
so you no longer have to hand-fill menu display name, request model id and
context window every time OpenCode adds or rotates models (including limited-time ones).

Also usable as an [AI agent skill](https://github.com/mattpocock/skills): this repo
is laid out as one — `SKILL.md` at the root plus `scripts/`.


## How it works

1. Locates the Codex provider whose `base_url` contains `opencode.ai/zen/go`
   (matched by characteristic, never a hard-coded provider id).
2. Reads the authoritative account-visible model ids from `{base_url}/models`
   using the key already stored in cc-switch (memory only — never printed,
   never written anywhere).
3. Reads display names + context windows from the `opencode-go` entry of
   `https://models.dev/api.json` (maintained by the OpenCode team).
4. Prints a diff table (`NEW` / `LIVE-ONLY` / `CTX` / `NAME` / `STALE`) for you
   to confirm, backs up the cc-switch DB + catalog, then writes back only the
   `modelCatalog.models` array. `auth` and `config` are left untouched.
5. Writes are always alphabetically sorted by model id, so the switcher menu
   stays easy to scan.

After applying: re-select the provider in cc-switch (or restart cc-switch),
then **restart Codex** (`model_catalog_json` is loaded at startup only).

## Requirements

- Windows + Python 3 (standard library only, no dependencies)
- cc-switch with an OpenCode Go (Zen) provider configured for the Codex app

## Usage

Dry-run first (read-only, changes nothing):

```powershell
python scripts/sync_opencode_go.py
```

Apply after you confirmed the table (backs up first):

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

## Window-equivalence notes

`1000000 / 1024000 / 1048576` are treated as the same “1M tier”
(and `256000 / 262144` as “256K tier”) — notation differences are not flagged,
only real cross-tier changes are. Unknown ids get a blank window (safe:
cc-switch falls back to 128K, which only compacts earlier instead of breaking).

## License

MIT — see [LICENSE](LICENSE).
