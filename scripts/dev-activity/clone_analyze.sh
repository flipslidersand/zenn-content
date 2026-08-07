#!/usr/bin/env bash
# Clone (full history) -> git-analyze -> save JSON -> delete clone.
# Disk-safe: one repo at a time. Usage: clone_analyze.sh repo1 repo2 ...
set -uo pipefail
SP=/tmp/claude-0/-home-user-zenn-content/a775d997-e159-577a-b977-33c0d1af528b/scratchpad
CLONES="$SP/clones"
OUT="$SP/git-json"
SCRIPT=/home/user/zenn-content/scripts/dev-activity/git_analyze.py
mkdir -p "$CLONES" "$OUT"
for repo in "$@"; do
  dir="$CLONES/$repo"
  if [ -f "$OUT/$repo.json" ]; then echo "SKIP $repo (already analyzed)"; continue; fi
  echo "=== $repo: cloning ==="
  rm -rf "$dir"
  if git clone --quiet "https://github.com/${DEV_ACT_OWNER:-flipslidersand}/$repo" "$dir" 2>/dev/null; then
    if git -C "$dir" rev-parse HEAD >/dev/null 2>&1; then
      python3 "$SCRIPT" "$dir" --start 2026-04-01 --end 2026-08-07 > "$OUT/$repo.json" 2>"$OUT/$repo.err"
      ac=$(python3 -c "import json;print(json.load(open('$OUT/$repo.json'))['git']['author_commits'])" 2>/dev/null || echo ERR)
      commits=$(git -C "$dir" log --oneline | wc -l | tr -d ' ')
      echo "  OK $repo: total_commits=$commits author_commits=$ac"
    else
      echo "  FAIL $repo: empty/broken clone"; echo "{}" > "$OUT/$repo.json"
    fi
  else
    echo "  FAIL $repo: clone error"
  fi
  rm -rf "$dir"
done
echo "=== done ==="
du -sh "$CLONES" 2>/dev/null