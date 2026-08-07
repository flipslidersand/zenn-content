#!/usr/bin/env python3
"""
Render development-activity-report.md (human-readable) from the raw JSON.
Internal companion to the raw data (uses real repo names). Objective only:
no seniority / productivity / "N people's work" claims. AI-assisted signals
are reported strictly as git-observable facts, kept separate from the
externally-given fact that the author works in an AI-assisted workflow.
"""
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/zenn-content/reports/dev-activity"
raw = json.load(open(os.path.join(OUT, "development-activity-raw.json")))
s = raw["summary"]
dq = raw["data_quality"]

N_DEEP = s["repositories_deep_analyzed"]
N_GH = sum(1 for r in raw["repositories"] if r.get("pull_requests") or r.get("issues") or r.get("ci_cd"))
# categories that have repos but no deep-analyzed (git) coverage
_gap = sorted(k for k, v in s["activity_by_category"].items() if v["repos"] and not v["deep_analyzed"])

def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)

L = []
def w(x=""): L.append(x)

w("# Development Activity Report")
w()
w(f"**Analysis period:** {raw['analysis_period']['start']} → {raw['analysis_period']['end']}  ")
w(f"**Collected at:** {raw['collected_at']} ({raw['timezone']})  ")
w(f"**Subject:** GitHub `{raw['subject_identity']['github_login']}` (id {raw['subject_identity']['github_id']})  ")
w(f"**Data basis:** {s['repositories_deep_analyzed']} repositories deep-analyzed from Git history; "
  f"{s['total_repositories']} repositories inventoried for breadth.")
w()
w("> This report presents only what is reproducible from Git and the GitHub API. "
  "Fields that could not be collected are marked `null` / *unavailable* rather than estimated. "
  "All commit/LOC figures are counted on each repository's default branch (`HEAD`, no-merges), "
  "attributed to the subject by author identity, in Asia/Tokyo.")
w()

# ---- Executive Summary ----
w("## Executive Summary")
w()
w(f"Between {raw['analysis_period']['start']} and {raw['analysis_period']['end']}, the subject account owns "
  f"**{s['total_repositories']} repositories**, of which **{s['repositories_active_in_window']}** were pushed to "
  f"within the window and **{s['archived_repositories']}** are archived "
  f"({s['public_repositories']} public / {s['private_repositories']} private).")
w()
w(f"**{N_DEEP} repositories** spanning several domains were cloned and analysed in depth at the Git level "
  f"(of which {N_GH} also have GitHub PR/Issue/CI coverage). Across the {N_DEEP}, the "
  f"subject authored **{fmt(s['author_commits_deep'])} commits** on default branches over "
  f"**{s['total_active_days_union_deep']} active days**, with a longest unbroken run of "
  f"**{s['longest_active_streak_deep']} consecutive active days** (median "
  f"**{s['median_commits_per_active_day_deep']}** / mean {s['mean_commits_per_active_day_deep']} commits per active day).")
w()
w(f"The end-to-end delivery path is observable in the data: **{fmt(s['total_issues_created_deep'])} issues**, "
  f"**{fmt(s['total_prs_created_deep'])} pull requests created / {fmt(s['total_prs_merged_deep'])} merged**, and "
  f"**{fmt(s['total_workflow_runs_deep'])} GitHub Actions workflow runs** across the {N_GH} repositories with "
  f"GitHub API coverage. Effective "
  f"code churn (generated files and lockfiles excluded, over all {N_DEEP} Git-analyzed repos) is "
  f"**+{fmt(s['effective_lines_added_deep'])} / −{fmt(s['effective_lines_deleted_deep'])} lines**.")
w()

# ---- Activity Timeline ----
w("## Activity Timeline")
w()
w(f"Monthly activity across the {N_DEEP} deep-analyzed repositories (commits and effective LOC from Git over all "
  f"{N_DEEP}; PRs from the GitHub API over the {N_GH} API-covered repos). Issue counts are reported as totals in "
  "*Delivery Metrics* rather than monthly (see *Limitations*).")
w()
w("| Month | Commits | PRs created | PRs merged | Effective LOC (Δ) |")
w("|-------|--------:|------------:|-----------:|------------------:|")
for m, v in raw["monthly_activity"].items():
    w(f"| {m} | {v['commits']} | {v['prs_created']} | {v['prs_merged']} | {fmt(v['effective_loc'])} |")
w()
w(f"Continuity indicators (union of the {N_DEEP} repositories): **{s['total_active_days_union_deep']} active days**, "
  f"longest streak **{s['longest_active_streak_deep']} days**, median **{s['median_commits_per_active_day_deep']} "
  f"commits per active day**. Attributed activity spans {min(raw['monthly_activity'])} through "
  f"{max(raw['monthly_activity'])}.")
w()

# ---- Delivery Metrics ----
w("## Delivery Metrics")
w()
w("Pull-request throughput and lead time per deep-analyzed repository. Lead time is `merged_at − created_at`; "
  "merge is determined by a non-null `merged_at` (the list API's `merged` boolean is unreliable). "
  "`median_time_to_first_review` is *unavailable* (per-PR review data not collected).")
w()
w("| Repository | PRs created | merged | closed-unmerged | open | median lead time (h) |")
w("|-----------|------------:|------:|----------------:|----:|---------------------:|")
for r in raw["repositories"]:
    pr = r.get("pull_requests")
    if pr:
        lt = pr['median_lead_time_hours']
        lt = "n/a" if lt is None else lt
        w(f"| {r['repo_name']} | {pr['prs_created']} | {pr['prs_merged']} | {pr['prs_closed_unmerged']} | "
          f"{pr['prs_currently_open']} | {lt} |")
w()
w("Issues and CI per deep-analyzed repository:")
w()
w("| Repository | issues created | open | closed | workflow runs | deployments |")
w("|-----------|---------------:|----:|------:|--------------:|:-----------:|")
for r in raw["repositories"]:
    iss = r.get("issues"); ci = r.get("ci_cd")
    if iss or ci:
        iss = iss or {}; ci = ci or {}
        wf = ci.get('workflow_runs_total')
        wf = "n/a" if wf is None else wf
        w(f"| {r['repo_name']} | {iss.get('issues_created')} | {iss.get('issues_currently_open')} | "
          f"{iss.get('issues_closed')} | {wf} | unavailable |")
w()
w("Workflow-run **success/failure split is not reported**: only a non-representative most-recent 30-run sample "
  "was retrievable per repository, and extrapolating it would be an estimate. Deployments are *unavailable* "
  "(the GitHub Deployments API is not exposed by the available tooling); external CI/CD systems were not inspected.")
w()

# ---- Development Areas ----
w("## Development Areas")
w()
w("Repository categories across the full inventory (category assigned by name heuristic; deep-analyzed repos "
  "additionally cross-checked against observed languages/paths). `deep_analyzed` shows how many in each category "
  "carry Git-level churn data.")
w()
w("| Category | Repositories | Deep-analyzed | Author commits (deep) | Effective churn (deep) |")
w("|----------|-------------:|--------------:|----------------------:|-----------------------:|")
for k, v in s["activity_by_category"].items():
    w(f"| {k} | {v['repos']} | {v['deep_analyzed']} | {fmt(v['author_commits'])} | {fmt(v['effective_loc'])} |")
w()
_covered = sorted(k for k, v in s["activity_by_category"].items() if v["deep_analyzed"])
w("The inventory spans product, frontend, backend, infrastructure, data-pipeline, AI/LLM, automation, "
  "documentation and experiment repositories. Deep (Git) churn data is present for categories: "
  + ", ".join(_covered) + ".")
if _gap:
    w("")
    w("Categories present in the inventory but **not yet in the deep-analyzed set** (their repositories are "
      "private and could not be attached for cloning during collection): **" + ", ".join(_gap) +
      "** (see *Limitations*).")
w()

# ---- Technology Breadth ----
w("## Technology Breadth")
w()
w("Languages by effective churn (added+deleted), aggregated over the deep-analyzed repositories:")
w()
w("| Language | Effective churn |")
w("|----------|----------------:|")
for l in s["top_languages"]:
    w(f"| {l['language']} | {fmt(l['effective_churn'])} |")
w()
w("Observed technology domains (from file paths/extensions) include frontend (TypeScript/JavaScript/HTML), "
  "backend (Python), infrastructure (YAML, Dockerfiles, Terraform/HCL where present), CI/CD "
  "(`.github/workflows`), automation (Shell) and documentation (Markdown). Domain classification is derived "
  "only from objective path/extension evidence; unmatched files are counted as `Other`.")
w()

# ---- Representative Repository Activity ----
w("## Representative Repository Activity")
w()
w("The most active repositories (by author commits) illustrate the range of the deep-analyzed set. Figures are "
  "default-branch, author-attributed, within the window.")
w()
reps = [r for r in raw["repositories"] if r["deep_analyzed"]]
reps = sorted(reps, key=lambda r: -(r["git"]["author_commits"]))[:5]
for r in reps:
    g = r["git"]; pr = r.get("pull_requests") or {}; iss = r.get("issues") or {}; ci = r.get("ci_cd") or {}
    ca = r.get("contributor_attribution", {})
    w(f"### {r['repo_name']}  ·  *{r['category']}*  ·  {r['visibility']}")
    w(f"- Commits (author / repo-total in window): **{g['author_commits']} / {g['total_commits']}** "
      f"(author share {ca.get('author_commit_share')})")
    w(f"- Active days **{g['active_days']}**, longest streak **{g['longest_active_streak']}**, "
      f"effective LOC **+{fmt(g['effective_lines_added'])} / −{fmt(g['effective_lines_deleted'])}**")
    w(f"- Commit types: {g['commit_types']}")
    if pr:
        w(f"- PRs: {pr['prs_created']} created / {pr['prs_merged']} merged / {pr['prs_currently_open']} open; "
          f"median lead time {pr['median_lead_time_hours']} h")
    if iss:
        w(f"- Issues: {iss.get('issues_created')} created ({iss.get('issues_currently_open')} open); "
          f"workflow runs {ci.get('workflow_runs_total')}")
    w(f"- Contributors observed: {ca.get('contributor_count')} distinct author identities")
    w()

# ---- AI-Assisted Development ----
w("## AI-Assisted Development")
w()
w("The subject develops in an AI-assisted workflow (an externally-provided fact). This section reports **only "
  "the objective Git signals** of that workflow, and does not infer AI involvement beyond what commit metadata "
  "shows.")
w()
w(f"- **AI-agent-authored commits** (Git author is an AI agent, e.g. `Claude <noreply@anthropic.com>`): "
  f"**{fmt(s['ai_agent_authored_commits_deep'])}** across the deep-analyzed set.")
w(f"- **AI co-authored commits** (person-authored commits carrying a `Co-Authored-By: <AI>` trailer): "
  f"**{fmt(s['ai_coauthored_person_commits_deep'])}**.")
w()
w("Per-repository AI-authorship breakdown:")
w()
w("| Repository | AI-agent authored | AI co-authored (person commits) | AI author identities |")
w("|-----------|------------------:|--------------------------------:|----------------------|")
for r in raw["repositories"]:
    if r["deep_analyzed"]:
        g = r["git"]; ca = r.get("contributor_attribution", {})
        aiv = ", ".join(ca.get("ai_agent_identity_variants", {}).keys()) or "—"
        w(f"| {r['repo_name']} | {g['ai_agent_authored_commits_in_window']} | "
          f"{g['ai_coauthored_person_commits_in_window']} | {aiv} |")
w()
w("These are commit-metadata facts only. They quantify how AI authorship appears in history; they are **not** a "
  "measure of how much of the code was AI-generated, which Git cannot determine.")
w()

# ---- Measurement Methodology ----
w("## Measurement Methodology")
w()
w("- **Commit scope:** `git log HEAD --no-merges`, per repository default branch, author date, Asia/Tokyo. "
  "Default-branch (not all-refs) counting is deliberate: it excludes unmerged/rebased branch duplicates and is "
  "the more conservative, verifiable basis.")
w("- **Author attribution:** commits are attributed to the subject only for the identities "
  f"`{', '.join(raw['subject_identity']['git_author_emails'])}` and names "
  f"`{', '.join(raw['subject_identity']['git_author_names'])}`. Every distinct author identity is retained in the "
  "raw data (`all_authors`) so attribution is auditable. AI-agent and bot identities are classified separately "
  "and never counted as the subject's authored commits.")
w("- **Effective LOC:** raw churn minus generated/vendored/lockfile/minified/binary content. Exclusion ruleset "
  "(recorded verbatim in the raw JSON):")
er = raw["methodology"]["effective_loc_exclusion_rules"]
w(f"    - path substrings: `{', '.join(er['path_substrings'])}`")
w(f"    - basenames: `{', '.join(er['basenames'])}`")
w(f"    - suffixes: `{', '.join(er['suffixes'])}`")
w(f"    - generated patterns: `{', '.join(er['generated_regex'])}`; binary files excluded (numstat `-`).")
w("- **Pull requests:** GitHub `list_pull_requests` (state=all). Merge = non-null `merged_at`. Lead time = "
  "`merged_at − created_at`.")
w("- **Issues / CI:** GitHub `list_issues` (`totalCount` + open count) and Actions `list_workflow_runs` "
  "(`total_count`).")
w("- **Reproducibility:** `scripts/dev-activity/git_analyze.py` (per-repo Git) and `build_report.py` "
  "(aggregation) regenerate every figure from the same inputs.")
w()

# ---- Limitations ----
w("## Limitations")
w()
w("**Obtained:**")
for x in dq["obtained"]:
    w(f"- {x}")
w()
w("**Not obtained / unavailable:**")
for x in dq["not_obtained"]:
    w(f"- {x}")
w()
w("**Data-quality notes:**")
for x in dq["data_quality_notes"]:
    w(f"- {x}")
w()
w("**Changes to collection logic vs. any prior aggregation:**")
for x in dq["changed_collection_logic"]:
    w(f"- {x}")
w()
w("This report deliberately avoids subjective judgements (e.g. seniority, productivity level, or "
  "\"equivalent headcount\") that Git history cannot substantiate. It reports scope, continuity, domain breadth, "
  "the Issue→PR→Merge→CI delivery path, and change lead time as third-party-verifiable facts.")
w()

with open(os.path.join(OUT, "development-activity-report.md"), "w") as f:
    f.write("\n".join(L) + "\n")
print("wrote development-activity-report.md")
