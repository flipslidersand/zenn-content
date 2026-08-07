# Development Activity Report

Reproducible, objective analysis of Git / GitHub development activity for the
period **2026-04-01 → 2026-08-07** (Asia/Tokyo), built for external technical /
hiring evaluation.

The goal is **not** to make activity look large. It is to show — in a
third-party-verifiable way — development scope, continuity, delivery capability,
the domains worked in, and the Git-observable characteristics of an AI-assisted
workflow. No values are estimated: anything not derivable from Git or the GitHub
API is `null` / *unavailable*.

## Scope

- **Inventory tier** — all **100** repositories owned by the account are
  inventoried (visibility, archived, fork, category, last push).
- **Deep tier** — **8** representative, domain-spanning repositories are cloned
  and analysed commit-by-commit (churn, effective LOC, commit types, languages,
  contributor attribution, AI-authorship, PRs, issues, CI). All per-commit /
  per-PR figures are summed over these 8. The deep set was capped by per-repo
  access-approval limits during collection; see *Limitations* in the report.

## Files

| File | Shareable? | Committed? | Contents |
|------|-----------|-----------|----------|
| `development-activity-anonymized.json` | ✅ yes | ✅ yes | Repo names generalised to `Repository-NN`; emails/URLs/usernames/IDs redacted. |
| `development-activity-executive-summary.json` | ✅ yes | ✅ yes | One-page headline metrics for a hiring one-pager. |
| `development-activity-raw.json` | ❌ internal | ⛔ gitignored | Full data incl. real private repo names, emails, per-identity attribution. |
| `development-activity-summary.csv` | ❌ internal | ⛔ gitignored | Per-repo metrics with real repo names. |
| `development-activity-report.md` | ❌ internal | ⛔ gitignored | Human-readable report with real repo names. |
| `anonymization-map.INTERNAL.json` | ❌ internal | ⛔ gitignored | `Repository-NN` ↔ real repo map. **Never share.** |

`zenn-content` is a **public** repository, so the files that contain private
repository names or personal emails are intentionally **git-ignored** (see the
repo `.gitignore`). They are produced locally by the pipeline and delivered out
of band. Only the scrubbed, shareable artifacts are committed.

## Regenerate

```bash
# 0. one-time local config (gitignored)
cp scripts/dev-activity/identity.example.json      scripts/dev-activity/identity.json
cp scripts/dev-activity/report_config.example.json scripts/dev-activity/report_config.json
#    edit both: real git author emails/names, scratchpad dir, deep-repo set

# 1. per-repo Git analysis (clone -> analyse -> cleanup, disk-safe)
bash scripts/dev-activity/clone_analyze.sh <repo> <repo> ...
python3 scripts/dev-activity/git_analyze.py <local-clone> --start 2026-04-01 --end 2026-08-07 > <scratch>/git-json/<repo>.json

# 2. GitHub PR/issue/CI snapshots -> <scratch>/gh-data/*.json
#    (captured via GitHub API; see report Measurement Methodology)

# 3. aggregate + render
python3 scripts/dev-activity/build_report.py
python3 scripts/dev-activity/render_report.py
```

## Pipeline

- `scripts/dev-activity/git_analyze.py` — single-repo Git analyzer. Default-branch
  (`HEAD`, no-merges) commits, author date, Asia/Tokyo. Raw + effective LOC with a
  documented exclusion ruleset. Commit-type, language/domain, contributor and
  AI-authorship attribution. Reads subject identities from `identity.json`.
- `scripts/dev-activity/clone_analyze.sh` — clone (full history) → analyse → delete,
  one repo at a time, to stay within disk limits.
- `scripts/dev-activity/build_report.py` — merges Git analysis + GitHub snapshots +
  inventory into the five deliverables. Repo lists / paths come from
  `report_config.json`.
- `scripts/dev-activity/render_report.py` — renders `development-activity-report.md`
  from the raw JSON.

## Key methodology choices

- **Default branch, not all refs.** Commits/churn are counted on `HEAD`, excluding
  duplicate work from unmerged/rebased branches — the conservative, verifiable basis.
- **Merge = non-null `merged_at`** (the list API's `merged` boolean is unreliable).
- **AI signals are Git facts only** — AI-agent-authored commits and `Co-Authored-By`
  AI trailers are counted; the report does not infer *how much* code was AI-generated,
  which Git cannot determine.
- **No estimates** — uncollected values are `null` / *unavailable*, listed explicitly
  in the report's *Limitations*.
