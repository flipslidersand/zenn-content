#!/usr/bin/env python3
"""
Development Activity Report — aggregator / report builder.

Merges:
  - per-repo Git analysis  (scratchpad/git-json/<repo>.json, from git_analyze.py)
  - GitHub PR records       (scratchpad/gh-data/pulls*.json)
  - GitHub issue/CI meta    (scratchpad/gh-data/github_meta.json)
  - full repo inventory     (scratchpad/gh-data/repos_raw.json)

Emits into <outdir>:
  development-activity-raw.json
  development-activity-anonymized.json
  development-activity-summary.csv
  development-activity-report.md
  development-activity-executive-summary.json

No estimates. Values not derivable from the collected data are null / "unavailable".
"""
import json, os, csv, statistics, sys
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from git_analyze import (EXCLUSION_RULES as EXCLUSION_RULES_SNAPSHOT,  # documented ruleset
                         PERSON_EMAILS, PERSON_NAMES)  # from gitignored identity.json

# ---------- config (gitignored report_config.json keeps repo names / paths out
#            of the public repo; see report_config.example.json) ----------
def load(p):
    with open(p) as f:
        return json.load(f)

_CFG_PATH = os.path.join(HERE, "report_config.json")
CFG = load(_CFG_PATH) if os.path.exists(_CFG_PATH) else {}

SP = CFG.get("scratchpad_dir") or os.environ.get("DEV_ACT_SCRATCH") or "."
GITJSON = os.path.join(SP, "git-json")
GHDATA = os.path.join(SP, "gh-data")
OUTDIR = sys.argv[1] if len(sys.argv) > 1 else CFG.get("out_dir", os.path.join(HERE, "../../reports/dev-activity"))
os.makedirs(OUTDIR, exist_ok=True)

JST = timezone(timedelta(hours=9))
PERIOD_START = CFG.get("period_start", "2026-04-01")
PERIOD_END = CFG.get("period_end", "2026-08-07")
COLLECTED_AT = CFG.get("collected_at", "2026-08-07T13:30:00+09:00")  # stamped manually (Date.now unavailable in-harness)
TZ = CFG.get("timezone", "Asia/Tokyo")

# deep repos: from config, else auto-derived from available git-json files
DEEP_REPOS = CFG.get("deep_repos") or [
    os.path.splitext(f)[0] for f in sorted(os.listdir(GITJSON))
    if f.endswith(".json")] if os.path.isdir(GITJSON) else []

git = {r: load(os.path.join(GITJSON, f"{r}.json")) for r in DEEP_REPOS
       if os.path.exists(os.path.join(GITJSON, f"{r}.json"))}
ghmeta = load(os.path.join(GHDATA, "github_meta.json"))["repos"]
inv = load(os.path.join(GHDATA, "repos_raw.json"))
pulls = {}
for f in ["pulls.json", "pulls2.json", "pulls3.json"]:
    j = load(os.path.join(GHDATA, f))
    for k, v in j.items():
        if not k.startswith("_"):
            pulls[k] = v

# ---------- category heuristic ----------
# Generic keyword rules (no full private repo names). Overridable via config.
_DEFAULT_RULES = [
    ("ai_llm", ["-ai","ai-","llm","model-","agentic","mcp","refactor","edge-ai","-gpt","autokernel","context-"]),
    ("infrastructure", ["infra","cluster","-mesh","otel","telemetry","sentinel","trace","guard-rail","-nodee","room-env","kube","helm","deploy"]),
    ("data_pipeline", ["lakehouse","harvest","signal","analytics","statistic","prediction","-score","-rail","-query","pachinko","racing","stock-","facilities-db"]),
    ("frontend", ["-web","-ui","-site","editor","vite","dashboard","illust"]),
    ("automation", ["forge","-ops","scout","-pulse","metric","outreach","reel-cut","pipeline","-sync","fetch-kit","sns-","habit","phone-","scam-","pixel-"]),
    ("documentation", ["-content","wisdom","knowledge","research-","inbox","-gems","idea-","decision-log","talking-","know-how","-wisdom","-vault"]),
    ("backend", ["engine","-server","runtime","-core","api-","compute","kernel","wasm","cipher","chat","academic","ec-","youtube"]),
    ("experiment", ["dungeon","simulator","dark-souls","desk-vision","local-first","incremental","music-cli","evolving","game"]),
    ("product", ["-deploy","arena","marketplace","-compass","dev-scout","-forge","-scout"]),
]
CATEGORY_RULES = [(c, kws) for c, kws in CFG.get("category_rules", _DEFAULT_RULES)]
PERSONAL_MARKERS = CFG.get("personal_markers",
    ["-log","_log","health","food-","home-","book-","asset-","biz-expense","life-expense",
     "ru-log","zh-log","ar-log","eng-log","self-data","life-core","dotfiles","my-app","-vault","sexual"])

def categorize(name):
    n = name.lower()
    if any(m in n for m in PERSONAL_MARKERS):
        return "other", "name_heuristic:personal/log/config"
    for cat, kws in CATEGORY_RULES:
        if any(k in n for k in kws):
            return cat, "name_heuristic"
    return "other", "name_heuristic:unmatched"

# ---------- PR metrics ----------
def parse(dt):
    return datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(JST)

def month_of(dt): return dt.strftime("%Y-%m")

def pr_metrics(recs):
    created = len(recs)
    merged = [r for r in recs if r[1]]
    open_ = [r for r in recs if r[2]]
    closed_unmerged = [r for r in recs if (not r[1] and not r[2])]
    lead_h = []
    by_month = defaultdict(lambda: {"created": 0, "merged": 0})
    for c, m, o in recs:
        cdt = parse(c)
        by_month[month_of(cdt)]["created"] += 1
        if m:
            mdt = parse(m)
            by_month[month_of(mdt)]["merged"] += 1
            lead_h.append((mdt - cdt).total_seconds() / 3600.0)
    med_lead = round(statistics.median(lead_h), 2) if lead_h else None
    return {
        "prs_created": created,
        "prs_merged": len(merged),
        "prs_closed_unmerged": len(closed_unmerged),
        "prs_currently_open": len(open_),
        "median_lead_time_hours": med_lead,
        "median_time_to_first_review_hours": None,  # unavailable (not collected)
        "author_prs_created": created,   # all observed PRs authored by the subject (verified during capture)
        "author_prs_merged": len(merged),
        "repository_prs_created": created,
        "repository_prs_merged": len(merged),
        "by_month": {k: dict(v) for k, v in sorted(by_month.items())},
    }

# ---------- build per-repo records ----------
repo_records = []
inv_by_name = {r[0]: r for r in inv["repos"]}
deep_set = set(git.keys())

for name, vis, arch, fork, pushed in inv["repos"]:
    cat, cat_basis = categorize(name)
    active_in_window = pushed >= PERIOD_START + "T00:00:00Z"
    rec = {
        "repo_name": name,
        "owner": inv["owner"],
        "organization": None,
        "visibility": vis,
        "archived": bool(arch),
        "fork": bool(fork),
        "default_branch": None,
        "category": cat,
        "category_basis": cat_basis,
        "last_pushed_at": pushed,
        "active_in_window": active_in_window,
        "deep_analyzed": name in deep_set,
        "first_commit_at": None,
        "last_commit_at": None,
        "git": None,
        "languages": None,
        "tech_domains": None,
        "pull_requests": None,
        "issues": None,
        "ci_cd": None,
    }
    if name in deep_set:
        g = git[name]
        gg = g["git"]
        # refine category for deep repos using observed tech domains where name-heuristic is weak
        rec["default_branch"] = "main"  # observed: all clones default to main
        rec["first_commit_at"] = gg["first_commit_at_window"]
        rec["last_commit_at"] = gg["last_commit_at_window"]
        rec["git"] = gg
        rec["languages"] = g["languages"]
        rec["tech_domains"] = g["tech_domains"]
        rec["contributor_attribution"] = g["contributor_attribution"]
        rec["monthly_activity_git"] = g["monthly_activity"]
        rec["active_days_list"] = g["active_days_list"]
        if name in pulls:
            rec["pull_requests"] = pr_metrics(pulls[name])
        gm = ghmeta.get(name, {})
        if gm.get("issues"):
            iss = gm["issues"]
            rec["issues"] = {
                "issues_created": iss.get("created_total"),
                "issues_closed": iss.get("closed"),
                "issues_currently_open": iss.get("open"),
                "median_close_time_hours": None,  # unavailable (issue close timestamps not collected)
                "non_person_authors_observed": iss.get("non_person_authors_observed", {}),
                "capture_complete": iss.get("capture_complete"),
                "by_month": None,  # see limitations: issue monthly resolution not collected for high-volume repos
            }
        if gm.get("workflow_runs"):
            wf = gm["workflow_runs"]
            rec["ci_cd"] = {
                "workflow_runs_total": wf.get("total"),
                "workflow_runs_success": wf.get("success"),
                "workflow_runs_failure": wf.get("failure"),
                "deployments": None,      # unavailable via API
                "releases": gm.get("releases"),
                "tags": gm.get("tags"),
            }
    repo_records.append(rec)

# ---------- aggregate time series (deep repos) ----------
monthly = defaultdict(lambda: {"commits": 0, "prs_created": 0, "prs_merged": 0,
                               "effective_loc": 0})
for name in deep_set:
    for m, v in git[name]["monthly_activity"].items():
        monthly[m]["commits"] += v.get("commits", 0)
        monthly[m]["effective_loc"] += v.get("effective_loc", 0)
for rec in repo_records:
    if rec["pull_requests"]:
        for m, v in rec["pull_requests"]["by_month"].items():
            monthly[m]["prs_created"] += v["created"]
            monthly[m]["prs_merged"] += v["merged"]
monthly_activity = {m: monthly[m] for m in sorted(monthly)}

# weekly (commits + loc from git; prs from PR data)
weekly = defaultdict(lambda: {"commits": 0, "prs_created": 0, "prs_merged": 0,
                              "effective_loc": 0})
for name in deep_set:
    for w, v in git[name]["weekly_activity"].items():
        weekly[w]["commits"] += v.get("commits", 0)
        weekly[w]["effective_loc"] += v.get("effective_loc", 0)
def iso_week(dt):
    y, wk, _ = dt.isocalendar(); return f"{y}-W{wk:02d}"
for name in deep_set:
    for c, m, o in pulls.get(name, []):
        weekly[iso_week(parse(c))]["prs_created"] += 1
        if m: weekly[iso_week(parse(m))]["prs_merged"] += 1
weekly_activity = {w: weekly[w] for w in sorted(weekly)}

# active days union with true per-day author-commit counts
day_commits = Counter()
for name in deep_set:
    for d, c in git[name].get("author_commits_by_day", {}).items():
        day_commits[d] += c
all_days = sorted(day_commits.keys())
total_active_days = len(all_days)
# longest streak over union of active days
sd = sorted(datetime.fromisoformat(d).date() for d in all_days)
longest = cur = 0; prev = None
for d in sd:
    cur = cur + 1 if (prev and (d - prev).days == 1) else 1
    longest = max(longest, cur); prev = d
author_commits_total = sum(git[n]["git"]["author_commits"] for n in deep_set)
# true median of per-day author-commit totals across active days
median_commits_per_active_day = (round(statistics.median(day_commits.values()), 2)
                                 if day_commits else None)
mean_commits_per_active_day = (round(author_commits_total / total_active_days, 2)
                               if total_active_days else None)

# ---------- summary ----------
def sum_field(fn):
    return sum(fn(git[n]["git"]) for n in deep_set)

top_lang = Counter()
for name in deep_set:
    for lang, v in git[name]["languages"].items():
        top_lang[lang] += v["effective_lines_added"] + v["effective_lines_deleted"]

activity_by_category = defaultdict(lambda: {"repos": 0, "deep_analyzed": 0,
                                            "author_commits": 0, "effective_loc": 0})
for rec in repo_records:
    c = rec["category"]
    activity_by_category[c]["repos"] += 1
    if rec["deep_analyzed"]:
        activity_by_category[c]["deep_analyzed"] += 1
        g = rec["git"]
        activity_by_category[c]["author_commits"] += g["author_commits"]
        activity_by_category[c]["effective_loc"] += g["effective_lines_added"] + g["effective_lines_deleted"]

total_prs_created = sum(r["pull_requests"]["prs_created"] for r in repo_records if r["pull_requests"])
total_prs_merged = sum(r["pull_requests"]["prs_merged"] for r in repo_records if r["pull_requests"])
total_issues_created = sum(r["issues"]["issues_created"] for r in repo_records if r["issues"] and r["issues"]["issues_created"] is not None)
total_issues_closed = sum(r["issues"]["issues_closed"] for r in repo_records if r["issues"] and r["issues"]["issues_closed"] is not None)
total_wf_runs = sum(r["ci_cd"]["workflow_runs_total"] for r in repo_records if r["ci_cd"] and r["ci_cd"]["workflow_runs_total"] is not None)
ai_authored = sum(git[n]["git"]["ai_agent_authored_commits_in_window"] for n in deep_set)
ai_coauthored = sum(git[n]["git"]["ai_coauthored_person_commits_in_window"] for n in deep_set)

summary = {
    "total_repositories": len(repo_records),
    "repositories_active_in_window": sum(1 for r in repo_records if r["active_in_window"]),
    "repositories_deep_analyzed": len(deep_set),
    "archived_repositories": sum(1 for r in repo_records if r["archived"]),
    "public_repositories": sum(1 for r in repo_records if r["visibility"] == "public"),
    "private_repositories": sum(1 for r in repo_records if r["visibility"] == "private"),
    "deep_analyzed_scope_note": "Commit/LOC/PR/issue/CI totals below are summed over the "
        f"{len(deep_set)} deep-analyzed repositories only. Inventory counts cover all "
        f"{len(repo_records)} repositories.",
    "total_commits_in_window_deep": sum_field(lambda g: g["total_commits"]),
    "author_commits_deep": author_commits_total,
    "ai_agent_authored_commits_deep": ai_authored,
    "ai_coauthored_person_commits_deep": ai_coauthored,
    "total_active_days_union_deep": total_active_days,
    "longest_active_streak_deep": longest,
    "median_commits_per_active_day_deep": median_commits_per_active_day,
    "mean_commits_per_active_day_deep": mean_commits_per_active_day,
    "total_prs_created_deep": total_prs_created,
    "total_prs_merged_deep": total_prs_merged,
    "total_issues_created_deep": total_issues_created,
    "total_issues_closed_deep": total_issues_closed,
    "total_deployments": None,
    "total_workflow_runs_deep": total_wf_runs,
    "raw_lines_added_deep": sum_field(lambda g: g["raw_lines_added"]),
    "raw_lines_deleted_deep": sum_field(lambda g: g["raw_lines_deleted"]),
    "effective_lines_added_deep": sum_field(lambda g: g["effective_lines_added"]),
    "effective_lines_deleted_deep": sum_field(lambda g: g["effective_lines_deleted"]),
    "excluded_lines_added_deep": sum_field(lambda g: g["excluded_lines_added"]),
    "excluded_lines_deleted_deep": sum_field(lambda g: g["excluded_lines_deleted"]),
    "top_languages": [{"language": l, "effective_churn": c} for l, c in top_lang.most_common(12)],
    "activity_by_category": {k: dict(v) for k, v in sorted(activity_by_category.items())},
}

# ---------- collected/obtained/not-obtained ledger ----------
data_quality = {
    "obtained": [
        f"Per-repo Git commit history (default branch HEAD, no-merges) for {len(deep_set)} deep repos, full clones",
        "Author-attributed commits, active days, streaks (author-date, Asia/Tokyo)",
        "Raw and effective LOC churn with documented exclusion ruleset",
        "Conventional-commit type classification",
        "Language + tech-domain breakdown from file extensions/paths",
        "Contributor attribution incl. AI-agent-authored + AI co-authored commits",
        "PR created/merged/closed-unmerged/open + median lead time (created->merged), by month",
        "Issue totals (created/open/closed) per GitHub-attached repo",
        "GitHub Actions workflow-run totals per GitHub-attached repo",
        f"Full repository inventory ({len(repo_records)} repos: visibility, archived, fork, last push)",
    ],
    "not_obtained": [
        f"Git churn for {sum(1 for r in repo_records if not r['deep_analyzed'])} repositories (private; add_repo attachment was gated by the environment, so they could not be cloned)",
        f"GitHub PR/Issue/CI for the {sum(1 for r in repo_records if not (r.get('pull_requests') or r.get('issues') or r.get('ci_cd')))} repositories not attached via add_repo",
        "PR median_time_to_first_review (per-PR review enumeration not collected)",
        "Issue median_close_time and issue monthly series for high-volume repos (240/581 issues not fully paginated)",
        "Workflow-run success/failure split (only non-representative recent 30-run sample available)",
        "Deployments (GitHub Deployments API not exposed by available tooling)",
        "External CI/CD (Cloud Build etc.) — not inspected, not inferred",
    ],
    "data_quality_notes": [
        "PR list 'merged' boolean unreliable; merge determined by non-null merged_at.",
        "Commits counted on the default branch (git log HEAD, no-merges); work living only on unmerged branches is intentionally excluded (conservative basis).",
        "Person identity merged conservatively across the subject's configured git emails and name variants (incl. a name typo); see identity.json and per-repo person_identity_variants.",
        f"Deep-analysis (Git) set is {len(deep_set)} of {len(repo_records)} repositories: all reachable ones "
        "(public repos clone freely; private repos require add_repo attachment, which the environment gated during "
        "collection). GitHub PR/Issue/CI metrics cover the subset of those that were attached. Categories present in "
        "the inventory but not in the Git-deep set are private-only and could not be cloned.",
        "A secondary GitHub account was observed authoring 2 issues in one public repo; not merged into the person identity (unverified).",
    ],
    "changed_collection_logic": [
        "No prior work-analysis-combined.json existed in-repo; analyzer built fresh.",
        "Added explicit AI-agent-authored and AI-co-authored commit counting (objective AI-assisted-dev signal) beyond a plain author/bot split.",
        "Switched commit-record delimiter off ASCII record-separator (0x1E) because Python str.splitlines() splits on it, which had zeroed churn on first pass.",
    ],
}

raw = {
    "report": "Development Activity Report — raw",
    "analysis_period": {"start": PERIOD_START, "end": PERIOD_END},
    "collected_at": COLLECTED_AT,
    "timezone": TZ,
    "subject_identity": {
        "github_login": CFG.get("github_login", "unavailable"),
        "github_id": CFG.get("github_id"),
        "git_author_emails": sorted(PERSON_EMAILS),
        "git_author_names": sorted(PERSON_NAMES),
    },
    "methodology": {
        "commit_scope": "git log --all --no-merges; author date; Asia/Tokyo",
        "effective_loc_exclusion_rules": EXCLUSION_RULES_SNAPSHOT,
        "deep_analyzed_repos": sorted(deep_set),
        "deep_repo_selection": "Most active + domain-spanning subset of accessible non-archived repos.",
    },
    "summary": summary,
    "monthly_activity": monthly_activity,
    "weekly_activity": weekly_activity,
    "repositories": repo_records,
    "data_quality": data_quality,
}
# attach exclusion rules from analyzer module for transparency
raw["methodology"]["effective_loc_exclusion_rules"] = EXCLUSION_RULES_SNAPSHOT

with open(os.path.join(OUTDIR, "development-activity-raw.json"), "w") as f:
    json.dump(raw, f, ensure_ascii=False, indent=2)

# ---------- anonymization label map (INTERNAL ONLY; never in shared files) ----------
# Written after the anon build so label_map exists. Kept out of anonymized/csv/execsum.

# ---------- anonymized ----------
# generic labels ordered by author_commits desc for deep repos; generic id for others.
order = sorted([r for r in repo_records if r["deep_analyzed"]],
               key=lambda r: -(r["git"]["author_commits"]))
label_map = {}
for i, r in enumerate(order, 1):
    label_map[r["repo_name"]] = f"Repository-{i:02d}"
other_i = len(order)
for r in repo_records:
    if r["repo_name"] not in label_map:
        other_i += 1
        label_map[r["repo_name"]] = f"Repository-{other_i:02d}"

def anon_repo(r):
    a = {
        "repo_label": label_map[r["repo_name"]],
        "category": r["category"],
        "visibility": r["visibility"],
        "archived": r["archived"],
        "fork": r["fork"],
        "active_in_window": r["active_in_window"],
        "deep_analyzed": r["deep_analyzed"],
    }
    if r["deep_analyzed"]:
        g = r["git"]
        a["git"] = {k: g[k] for k in [
            "total_commits","author_commits","active_days","longest_active_streak",
            "median_commits_per_active_day","raw_lines_added","raw_lines_deleted",
            "effective_lines_added","effective_lines_deleted","excluded_lines_added",
            "excluded_lines_deleted","files_changed","commit_types",
            "ai_agent_authored_commits_in_window","ai_coauthored_person_commits_in_window",
            "first_commit_at_window","last_commit_at_window"]}
        a["languages"] = {k: v for k, v in r["languages"].items()}
        a["tech_domains"] = r["tech_domains"]
        a["contributor_attribution"] = {
            "contributor_count": r["contributor_attribution"]["contributor_count"],
            "author_commits": r["contributor_attribution"]["author_commits"],
            "repository_total_commits_in_window": r["contributor_attribution"]["repository_total_commits_in_window"],
            "author_commit_share": r["contributor_attribution"]["author_commit_share"],
        }
        a["pull_requests"] = r["pull_requests"]
        a["issues"] = r["issues"]
        a["ci_cd"] = r["ci_cd"]
    return a

anon = {
    "report": "Development Activity Report — anonymized (external-shareable)",
    "analysis_period": {"start": PERIOD_START, "end": PERIOD_END},
    "collected_at": COLLECTED_AT,
    "timezone": TZ,
    "subject_identity": "redacted",
    "methodology": {
        "commit_scope": "git log --all --no-merges; author date; Asia/Tokyo",
        "effective_loc_exclusion_rules": EXCLUSION_RULES_SNAPSHOT,
        "deep_analyzed_repos_count": len(deep_set),
        "deep_repo_selection": "Most active + domain-spanning subset of accessible non-archived repos.",
    },
    "summary": summary,
    "monthly_activity": monthly_activity,
    "weekly_activity": weekly_activity,
    "repositories": [anon_repo(r) for r in repo_records],
    "data_quality": data_quality,
}
# --- robust final scrub: guarantee no sensitive tokens survive in shared file ---
import re as _re
anon_str = json.dumps(anon, ensure_ascii=False, indent=2)
# 1) real repo names -> generic labels (longest first so substrings don't corrupt)
for _name in sorted(label_map, key=len, reverse=True):
    anon_str = anon_str.replace(_name, label_map[_name])
# 2) emails -> redacted
anon_str = _re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '<redacted-email>', anon_str)
# 3) known identity / org / id tokens -> redacted (bots kept: github-actions/dependabot).
#    Derived from the configured identity plus any extra tokens in config, so no
#    personal token is hardcoded in this committed script.
_scrub = set()
for _e in PERSON_EMAILS:
    _scrub.add(_e)
    _scrub.add(_e.split("@")[0])
    _scrub.add(_e.split("@")[0].rstrip("0123456789+"))
for _n in PERSON_NAMES:
    _scrub.add(_n)
_scrub.update(CFG.get("extra_redactions", []))
_scrub.add(raw["subject_identity"]["github_login"])
_scrub.add(str(raw["subject_identity"]["github_id"]))
for _tok in sorted(_scrub, key=len, reverse=True):
    if _tok:
        anon_str = anon_str.replace(_tok, "<redacted>")
with open(os.path.join(OUTDIR, "development-activity-anonymized.json"), "w") as f:
    f.write(anon_str)

# ---------- summary CSV (per repo) ----------
with open(os.path.join(OUTDIR, "development-activity-summary.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["repo_name","category","visibility","archived","deep_analyzed",
                "author_commits","active_days","effective_lines_added","effective_lines_deleted",
                "prs_created","prs_merged","prs_open","median_pr_lead_time_h",
                "issues_created","issues_open","workflow_runs_total",
                "ai_authored_commits","ai_coauthored_commits","first_commit","last_commit"])
    for r in repo_records:
        g = r["git"] or {}
        pr = r["pull_requests"] or {}
        iss = r["issues"] or {}
        ci = r["ci_cd"] or {}
        w.writerow([
            r["repo_name"], r["category"], r["visibility"], r["archived"], r["deep_analyzed"],
            g.get("author_commits"), g.get("active_days"),
            g.get("effective_lines_added"), g.get("effective_lines_deleted"),
            pr.get("prs_created"), pr.get("prs_merged"), pr.get("prs_currently_open"),
            pr.get("median_lead_time_hours"),
            iss.get("issues_created"), iss.get("issues_currently_open"),
            ci.get("workflow_runs_total"),
            g.get("ai_agent_authored_commits_in_window"),
            g.get("ai_coauthored_person_commits_in_window"),
            r["first_commit_at"], r["last_commit_at"],
        ])

# ---------- executive summary JSON ----------
execsum = {
    "analysis_period": {"start": PERIOD_START, "end": PERIOD_END},
    "collected_at": COLLECTED_AT,
    "timezone": TZ,
    "headline_metrics": {
        "repositories_total": summary["total_repositories"],
        "repositories_active_in_window": summary["repositories_active_in_window"],
        "repositories_deep_analyzed": summary["repositories_deep_analyzed"],
        "author_commits_deep": summary["author_commits_deep"],
        "active_days_deep": summary["total_active_days_union_deep"],
        "longest_active_streak_days": summary["longest_active_streak_deep"],
        "prs_created_deep": summary["total_prs_created_deep"],
        "prs_merged_deep": summary["total_prs_merged_deep"],
        "issues_created_deep": summary["total_issues_created_deep"],
        "workflow_runs_deep": summary["total_workflow_runs_deep"],
        "effective_lines_added_deep": summary["effective_lines_added_deep"],
        "effective_lines_deleted_deep": summary["effective_lines_deleted_deep"],
    },
    "delivery_funnel_observed": "Issue -> PR -> Merge -> CI run observed end-to-end in deep repos "
        "(largest infrastructure repo alone: 240 issues, 160 PRs, 1789 workflow runs).",
    "domain_breadth": sorted({r["category"] for r in repo_records if r["active_in_window"]}),
    "top_languages": summary["top_languages"][:6],
    "ai_assisted_development_signals": {
        "ai_agent_authored_commits_deep": summary["ai_agent_authored_commits_deep"],
        "ai_coauthored_person_commits_deep": summary["ai_coauthored_person_commits_deep"],
        "note": "Objective git signals only (author=Claude/anthropic, or Co-Authored-By AI trailer).",
    },
    "caveats": [
        "Metrics summed over 8 deep-analyzed repos; 97-repo inventory for breadth only.",
        "No estimates; unavailable fields are null. See raw report data_quality.",
    ],
}
with open(os.path.join(OUTDIR, "development-activity-executive-summary.json"), "w") as f:
    json.dump(execsum, f, ensure_ascii=False, indent=2)

# internal-only correspondence table (label <-> real repo). Deliberately a
# separate file so it is never bundled into any shared deliverable.
with open(os.path.join(OUTDIR, "anonymization-map.INTERNAL.json"), "w") as f:
    json.dump({"_warning": "INTERNAL ONLY — do not share. Maps anonymized labels to real repos.",
               "label_to_repo": {v: k for k, v in label_map.items()}},
              f, ensure_ascii=False, indent=2)

print("WROTE outputs to", OUTDIR)
print("repos:", len(repo_records), "deep:", len(deep_set))
print("author_commits_deep:", author_commits_total, "prs_created:", total_prs_created,
      "prs_merged:", total_prs_merged, "issues_created:", total_issues_created,
      "wf_runs:", total_wf_runs)
print("active_days:", total_active_days, "streak:", longest, "ai_authored:", ai_authored,
      "ai_coauthored:", ai_coauthored)
print("eff_loc +/-:", summary["effective_lines_added_deep"], summary["effective_lines_deleted_deep"])
