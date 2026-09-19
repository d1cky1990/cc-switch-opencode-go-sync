#!/usr/bin/env python3
"""Sync OpenCode Go (Zen) models into the cc-switch Codex provider.

Default is dry-run (read-only): fetch upstream, print diff, change nothing.
Use --apply to write back (backs up DB + catalog first, needs user OK).

Key handling: the provider API key is read from the cc-switch DB into
memory only. It is never printed, never written to disk, never logged.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import time
import sys
import urllib.request

MATCH_HOST = "opencode.ai/zen/go"
MODELS_DEV_URL = "https://models.dev/api.json"
USER_AGENT = "opencode-go-sync/1.0 (local maintenance script)"


def norm_window(w):
    """Map same-tier notations (1000^2 vs 1024^2) to one value."""
    if w is None:
        return None
    try:
        w = int(w)
    except (TypeError, ValueError):
        return w
    if w in (1000000, 1024000, 1048576):
        return 1000000
    if w in (256000, 262144):
        return 262144
    return w


def default_paths():
    home = os.path.expanduser("~")
    return {
        "db": os.path.join(home, ".cc-switch", "cc-switch.db"),
        "backups": os.path.join(home, ".cc-switch", "backups"),
        "catalog": os.path.join(home, ".codex", "cc-switch-model-catalog.json"),
    }


def fetch_json(url, timeout, extra_headers=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch_json_retry(url, timeout, extra_headers=None, tries=3):
    last = None
    for attempt in range(1, tries + 1):
        try:
            return fetch_json(url, timeout, extra_headers)
        except Exception as exc:
            last = exc
            if attempt < tries:
                time.sleep(2 * attempt)
    raise last


def pick_provider(con, provider_id=None):
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, name, settings_config FROM providers WHERE app_type = 'codex'"
    ).fetchall()
    hits = [r for r in rows if (r["settings_config"] or "").find(MATCH_HOST) >= 0]
    if provider_id:
        hits = [r for r in hits if r["id"] == provider_id]
    return hits


def parse_provider(row):
    sc = json.loads(row["settings_config"])
    config_text = sc.get("config") or ""
    m = re.search(r'base_url\s*=\s*"([^"]+)"', config_text)
    base_url = m.group(1) if m else None
    auth = sc.get("auth") or {}
    key = auth.get("OPENAI_API_KEY")
    models = (sc.get("modelCatalog") or {}).get("models") or []
    local = {}
    for entry in models:
        mid = entry.get("model")
        if mid:
            local[mid] = entry
    return sc, base_url, key, models, local


def fetch_live(base_url, key, timeout):
    url = base_url.rstrip("/") + "/models"
    data = fetch_json_retry(url, timeout, {"Authorization": "Bearer " + key})
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None, "unexpected /models response shape"
    ids = [it.get("id") for it in items if isinstance(it, dict) and it.get("id")]
    return ids, None


def build_plan(local, upstream):
    """upstream: {id: (name, ctx)}. Returns (new_models, changes)."""
    new_models = []
    changes = {"ctx": [], "name": [], "stale": []}
    local_order = [e.get("model") for e in local.values()]
    for mid in sorted(upstream.keys()):
        uname, uctx = upstream[mid]
        if mid not in local:
            entry = {"model": mid}
            entry["displayName"] = uname if uname else mid
            entry["contextWindow"] = uctx
            new_models.append(entry)
        else:
            cur = local[mid]
            if norm_window(cur.get("contextWindow")) != norm_window(uctx):
                changes["ctx"].append((mid, cur.get("contextWindow"), uctx))
            if uname and cur.get("displayName") != uname:
                changes["name"].append((mid, cur.get("displayName"), uname))
    for mid in local_order:
        if mid not in upstream:
            changes["stale"].append(mid)
    return new_models, changes


def parse_forced_names(items):
    forced = {}
    for item in items:
        if "=" not in item:
            raise SystemExit("bad ID=NAME value: " + item)
        kid, kval = item.split("=", 1)
        forced[kid.strip()] = kval.strip()
    return forced


def print_plan(provider_name, new_models, skipped_new, live_only, live_extra, changes, live_ids, live_ok):
    print("provider: " + provider_name)
    if live_ok is False:
        print("live check: FAILED (see warnings below)")
    elif live_ids is None:
        print("live check: skipped")
    else:
        print("live check: ok (" + str(len(live_ids)) + " ids visible)")
    print("")
    print("## NEW (" + str(len(new_models)) + ")")
    for e in new_models:
        print("  [NEW] " + e["model"] + " | " + str(e.get("displayName")) + " | " + str(e.get("contextWindow")))
    if skipped_new:
        print("## skipped NEW (" + str(len(skipped_new)) + ")")
        for mid in skipped_new:
            print("  [SKIP] " + mid)
    print("## LIVE-ONLY, not in models.dev (" + str(len(live_only)) + ")")
    for mid in live_only:
        tag = " [ADD with blank window]" if mid in live_extra else ""
        print("  [LIVE-ONLY] " + mid + tag)
    print("## CTX changed (" + str(len(changes["ctx"])) + ")")
    for mid, old, new in changes["ctx"]:
        print("  [CTX] " + mid + ": " + str(old) + " -> " + str(new))
    print("## NAME changed (" + str(len(changes["name"])) + ")")
    for mid, old, new in changes["name"]:
        print("  [NAME] " + mid + ": " + str(old) + " -> " + str(new))
    print("## STALE kept (" + str(len(changes["stale"])) + ")")
    for mid in changes["stale"]:
        print("  [STALE] " + mid)
    dropped = changes.get("dropped", [])
    print("## STALE to be deleted (" + str(len(dropped)) + ")")
    for mid in dropped:
        print("  [DROP] " + mid)


def apply_overrides(new_models, changes, local, args):
    skipped_new = []
    if args.skip_new:
        skip = set(args.skip_new)
        kept = []
        for e in new_models:
            if e["model"] in skip:
                skipped_new.append(e["model"])
            else:
                kept.append(e)
        new_models[:] = kept
    if args.keep_names:
        changes["name"] = []
    if args.rename:
        forced_names = parse_forced_names(args.rename)
        for mid, newname in forced_names.items():
            if mid in local:
                changes["name"].append((mid, local[mid].get("displayName"), newname))
            else:
                for e in new_models:
                    if e["model"] == mid:
                        e["displayName"] = newname
    if args.set_window:
        forced = {}
        for item in args.set_window:
            if "=" not in item:
                raise SystemExit("bad --set-window (want ID=NUM): " + item)
        for item in args.set_window:
            kid, kval = item.split("=", 1)
            forced[kid.strip()] = int(kval.strip())
        for e in new_models:
            if e["model"] in forced:
                e["contextWindow"] = forced[e["model"]]
        kept_ctx = []
        for mid, old, new in changes["ctx"]:
            if mid in forced:
                kept_ctx.append((mid, old, forced[mid]))
            else:
                kept_ctx.append((mid, old, new))
        changes["ctx"] = kept_ctx
    if args.drop_stale:
        changes["dropped"] = list(changes["stale"])
        changes["stale"] = []
    else:
        changes["dropped"] = []
    return skipped_new


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sync OpenCode Go models into cc-switch (dry-run by default).")
    ap.add_argument("--apply", action="store_true", help="write back to cc-switch DB (backs up first)")
    ap.add_argument("--no-live", action="store_true", help="skip authenticated live /models check")
    ap.add_argument("--keep-names", action="store_true", help="skip display-name updates")
    ap.add_argument("--rename", action="append", default=[], help="force display name: ID=NAME (repeatable)")
    ap.add_argument("--skip-new", action="append", default=[], help="skip a NEW id (repeatable)")
    ap.add_argument("--add-live", action="append", default=[], help="add a LIVE-ONLY id with blank window (repeatable)")
    ap.add_argument("--db", default=None)
    ap.add_argument("--catalog", default=None)
    ap.add_argument("--provider-id", default=None)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--set-window", action="append", default=[], help="force window for an id: ID=NUM (repeatable)")
    ap.add_argument("--drop-stale", action="store_true", help="delete STALE entries instead of keeping them")
    args = ap.parse_args(argv)

    paths = default_paths()
    db_path = args.db or paths["db"]
    con = sqlite3.connect(db_path)
    try:
        hits = pick_provider(con, args.provider_id)
    finally:
        con.close()
    if len(hits) == 0:
        raise SystemExit("no Codex provider matching " + MATCH_HOST + " found")
    if len(hits) > 1:
        ids = ", ".join([h["id"] + " (" + h["name"] + ")" for h in hits])
        raise SystemExit("multiple matches, pass --provider-id. Candidates: " + ids)
    row = hits[0]
    sc, base_url, key, models, local = parse_provider(row)
    print("key: present in DB (hidden, memory-only)")
    print("base_url: " + str(base_url))

    catalog = fetch_json_retry(MODELS_DEV_URL, args.timeout)
    entry = catalog.get("opencode-go") or {}
    upstream_raw = entry.get("models") or {}
    upstream = {}
    for mid, meta in upstream_raw.items():
        if not isinstance(meta, dict):
            continue
        limit = meta.get("limit") or {}
        upstream[mid] = (meta.get("name"), limit.get("context"))
    print("upstream models.dev opencode-go: " + str(len(upstream)))

    live_ids = None
    live_only = []
    live_ok = None
    warnings = []
    if not args.no_live:
        if not base_url or not key:
            live_ok = False
            warnings.append("live check unavailable (missing base_url or key)")
        else:
            try:
                live_ids, err = fetch_live(base_url, key, args.timeout)
            except Exception as exc:
                live_ids, err = None, str(exc)
            if err:
                live_ok = False
                warnings.append("live /models failed: " + err)
            else:
                live_ok = True
                live_set = set(live_ids)
                live_only = sorted([i for i in live_set if i not in upstream and i not in local])
                for mid in upstream:
                    if mid not in local and mid not in live_set:
                        warnings.append("NEW id not visible via live /models (may be delisted for this account): " + mid)
                for mid in local:
                    if mid not in upstream and mid not in live_set:
                        warnings.append("STALE id also absent from live /models (likely retired): " + mid)

    new_models, changes = build_plan(local, upstream)
    skipped_new = apply_overrides(new_models, changes, local, args)
    live_extra = []
    for mid in args.add_live:
        if live_ids is not None and mid not in set(live_ids):
            warnings.append("asked to add LIVE id not visible via live /models: " + mid)
        if mid in local or mid in upstream:
            warnings.append("asked to add LIVE id that is already known, ignored: " + mid)
        else:
            live_extra.append({"model": mid, "displayName": mid, "contextWindow": None})
    print_plan(row["name"], new_models, skipped_new, live_only, [e["model"] for e in live_extra], changes, live_ids, live_ok)
    if warnings:
        print("## warnings (" + str(len(warnings)) + ")")
        for w in warnings:
            print("  [!] " + w)

    if not args.apply:
        print("")
        print("dry-run only: nothing written. Re-run with --apply after user confirmation.")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = paths["backups"]
    os.makedirs(backups, exist_ok=True)
    db_backup = os.path.join(backups, "db_backup_" + stamp + ".db")
    shutil.copy2(db_path, db_backup)
    print("DB backup: " + db_backup)
    catalog_path = args.catalog or paths["catalog"]
    if os.path.exists(catalog_path):
        cat_backup = catalog_path + ".bak-" + stamp
        shutil.copy2(catalog_path, cat_backup)
        print("catalog backup: " + cat_backup)

    by_id = {e["model"]: dict(e) for e in models}
    for mid, old, new in changes["ctx"]:
        by_id[mid]["contextWindow"] = new
    for mid, old, new in changes["name"]:
        by_id[mid]["displayName"] = new
    for mid in changes.get("dropped", []):
        by_id.pop(mid, None)
    ordered = [by_id[mid] for mid in [e.get("model") for e in models] if mid in by_id]
    for e in new_models:
        ordered.append(e)
        by_id[e["model"]] = e
    for e in live_extra:
        ordered.append(e)
        by_id[e["model"]] = e
    ordered.sort(key=lambda e: (e.get("model") or "").lower())
    sc["modelCatalog"]["models"] = ordered
    con2 = sqlite3.connect(db_path)
    try:
        con2.execute("UPDATE providers SET settings_config = ? WHERE id = ? AND app_type = 'codex'", (json.dumps(sc, ensure_ascii=False), row["id"]))
        con2.commit()
    finally:
        con2.close()
    print("wrote " + str(len(ordered)) + " models to provider " + row["id"])
    print("NEXT: re-select this provider (or restart cc-switch), then restart Codex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
