"""Build the player-safe War Table snapshot the Discord bot reads.

Usage:
    python build_snapshot.py EXPORT_DIR OUT_FILE [--changes-file CHANGES.json]

EXPORT_DIR holds one folder per War Table collection, one JSON file per
document (the layout ArtifactData's out_dir produces):
    quests/  factions/  regions/  characters/  pursuits/  meta/state.json

Only player-facing collections and fields are read. The `drafts` and `dm`
collections are never opened, so hidden quests and DM notes cannot leak
into Discord even if they sit in the same folder.

CHANGES.json (optional) is {"title": "...", "changes": ["...", ...]}: the
approved, player-safe changelog the bot announces once.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

WAR_TABLE_URL = "https://texansfan1337.github.io/war-table-feed/"
QUEST_FIELDS = ["title", "category", "status", "region", "giver", "owners", "factions", "stakes", "lead", "lastSession"]
PURSUIT_FIELDS = ["pc", "kind", "title", "pickLabel", "filled", "total", "status", "teacher"]
STATUSES = {"active", "rumored", "dormant", "resolved", "failed"}
CATEGORIES = {"main", "side", "personal", "faction", "request"}


def docs(root: Path, name: str):
    d = root / name
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        body = json.loads(f.read_text(encoding="utf-8"))
        body = body.get("data", body) if isinstance(body, dict) and "data" in body and "id" in body else body
        out.append((f.stem, body))
    return out


def date_label(m: dict) -> str:
    if not m.get("year"):
        return "Date not set"
    if m.get("fest"):
        return f"{m['fest']}, {m['year']} DR"
    return f"{m.get('day')} {m.get('month')} {m['year']} DR"


def build(root: Path, changes: dict | None) -> dict:
    meta_file = root / "meta" / "state.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    meta = meta.get("data", meta)

    regions = {i: b.get("name", i) for i, b in sorted(docs(root, "regions"), key=lambda x: x[1].get("order", 99))}
    characters = [{"id": i, "name": b.get("name", i), "cls": b.get("cls", "")}
                  for i, b in sorted(docs(root, "characters"), key=lambda x: x[1].get("order", 99))]
    factions = [{"id": i, "name": b.get("name", i), "blurb": b.get("blurb", "")}
                for i, b in sorted(docs(root, "factions"), key=lambda x: x[1].get("order", 99))]

    quests = []
    for i, b in docs(root, "quests"):
        q = {"id": i, **{k: b.get(k) for k in QUEST_FIELDS}}
        q["status"] = q["status"] if q["status"] in STATUSES else "rumored"
        q["category"] = q["category"] if q["category"] in CATEGORIES else "side"
        q["owners"] = q["owners"] or []
        q["factions"] = q["factions"] or []
        quests.append(q)
    quests.sort(key=lambda q: q["title"])

    pursuits = [{"id": i, **{k: b.get(k) for k in PURSUIT_FIELDS}} for i, b in docs(root, "pursuits")]

    snap = {
        "schema": 1,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warTableUrl": WAR_TABLE_URL,
        "calendar": {"label": date_label(meta), "year": meta.get("year"), "month": meta.get("month"),
                     "day": meta.get("day"), "fest": meta.get("fest"), "nextSession": meta.get("session")},
        "regions": regions,
        "characters": characters,
        "factions": factions,
        "quests": quests,
        "pursuits": pursuits,
    }
    if changes and changes.get("changes"):
        snap["changesTitle"] = changes.get("title") or "The War Table has been updated"
        snap["changes"] = list(changes["changes"])
        snap["changesId"] = hashlib.sha1(json.dumps(snap["changes"]).encode()).hexdigest()[:12]
    return snap


STATUS_WORDS = {"active": "now active", "rumored": "rumored", "dormant": "gone quiet",
                "resolved": "completed", "failed": "failed"}


def diff_changes(prev: dict, snap: dict) -> list[str]:
    """Player-safe changelog from two snapshots (titles and statuses only)."""
    old = {q["id"]: q for q in prev.get("quests", [])}
    new = {q["id"]: q for q in snap.get("quests", [])}
    out = []
    for i, q in new.items():
        if i not in old:
            out.append(f"New quest: {q['title']}")
        elif q["status"] != old[i]["status"]:
            out.append(f"{q['title']}: {STATUS_WORDS.get(q['status'], q['status'])}")
        elif (q.get("lead"), q.get("stakes"), q.get("title")) != (old[i].get("lead"), old[i].get("stakes"), old[i].get("title")):
            out.append(f"Updated: {q['title']}")
    for i, q in old.items():
        if i not in new:
            out.append(f"Removed: {q['title']}")
    if prev.get("calendar", {}).get("label") != snap["calendar"]["label"]:
        out.append(f"The date is now {snap['calendar']['label']}")
    return out


def same_board(a: dict, b: dict) -> bool:
    strip = lambda s: {k: v for k, v in s.items() if k not in ("generated", "changes", "changesTitle", "changesId")}
    return strip(a) == strip(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("out_file")
    ap.add_argument("--changes-file")
    a = ap.parse_args()
    changes = json.loads(Path(a.changes_file).read_text(encoding="utf-8")) if a.changes_file else None
    snap = build(Path(a.export_dir), changes)
    out = Path(a.out_file)
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    if prev and same_board(prev, snap):
        print("NO CHANGE: the board matches the current snapshot; nothing written.")
        return
    if prev and not changes:
        auto = diff_changes(prev, snap)
        if auto:
            snap["changesTitle"] = "The War Table has been updated"
            snap["changes"] = auto[:15]
            snap["changesId"] = hashlib.sha1(json.dumps(snap["changes"]).encode()).hexdigest()[:12]
    Path(a.out_file).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_file).write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {a.out_file}: {len(snap['quests'])} quests, {len(snap['factions'])} factions, "
          f"{len(snap['pursuits'])} pursuits, {snap['calendar']['label']}")


if __name__ == "__main__":
    main()
