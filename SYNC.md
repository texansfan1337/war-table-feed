# Syncing the War Table to Discord

The Discord bot polls `snapshot.json` in this repo every 5 minutes. This is how Claude refreshes it.

1. Attach this repo with push access (`add_repo` texansfan1337/war-table-feed, access `push`) and clone it to `/home/claude/war-table-feed`.
2. Export **only** these War Table collections with ArtifactData `list` + `out_dir` into one empty folder (call it EXPORT):
   `quests`, `factions`, `regions`, `characters`, `pursuits`, `meta`.
   Artifact: https://claude.ai/artifact/A91a17n8TPbBPqft9QMrCx
   **Never export `dm` or `drafts`.** They are DM-only.
3. Run: `python3 -I tools/build_snapshot.py EXPORT snapshot.json`
   - Prints `NO CHANGE` when the board already matches: stop there, commit nothing.
   - Otherwise it writes a new snapshot with an automatic player-safe changelog (new, completed, updated and removed quest titles; date change). Pass `--changes-file` instead to supply your own changelog after an approved recap.
4. Check for leaks: `grep -ciE '"truth"|"trigger"|"pointsTo"' snapshot.json` must print 0.
5. Commit `snapshot.json` and push to `main`.
