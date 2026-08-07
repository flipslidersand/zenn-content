#!/usr/bin/env python3
"""
Development Activity Report — per-repository Git analyzer.

Reproducible, objective Git-history analysis for a single local clone.
No estimates: values that cannot be derived from Git are omitted (the
aggregator marks them null / unavailable).

Usage:
    python3 git_analyze.py <repo_path> [--start YYYY-MM-DD] [--end YYYY-MM-DD]

Output: a single JSON object on stdout.

Author-identity matching (section 9) is intentionally conservative: only
identities listed in PERSON_EMAILS / PERSON_NAMES are attributed to the
person. Every distinct author observed is still reported under
`all_authors` so the attribution is auditable.
"""
import json
import subprocess
import sys
import re
import os
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

# ---- Person identity (auditable, conservative) --------------------------
# Loaded from identity.json (gitignored — keeps personal emails out of the
# public repo). See identity.example.json for the shape. Falls back to a
# neutral placeholder if the file is absent.
_IDENT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "identity.json")
if os.path.exists(_IDENT_PATH):
    with open(_IDENT_PATH) as _f:
        _ident = json.load(_f)
    PERSON_EMAILS = set(_ident.get("person_emails", []))
    PERSON_NAMES = set(_ident.get("person_names", []))
else:
    PERSON_EMAILS = {"author@example.com"}
    PERSON_NAMES = {"author"}
# Known non-person (bot / tool) identities. Reported separately, never
# counted as the person's authored work.
BOT_EMAIL_PATTERNS = [
    re.compile(r"users\.noreply\.github\.com$") ,  # only bots below; person's noreply handled above
]
BOT_NAME_MARKERS = ["[bot]", "github-actions", "dependabot", "renovate", "mergify"]
# AI coding-agent authorship (objective AI-assisted-development signal).
AI_NAME_MARKERS = ["claude", "copilot", "cursor", "devin", "codex", "gpt",
                   "aider", "sweep"]
AI_EMAIL_MARKERS = ["noreply@anthropic.com", "anthropic.com",
                    "copilot@", "users.noreply.github.com/copilot"]
# Co-Authored-By trailers that indicate AI pairing.
AI_COAUTHOR_RE = re.compile(
    r"co-authored-by:\s*(claude|copilot|cursor|devin|aider|gpt|codex)",
    re.I)

JST = timezone(timedelta(hours=9))

# ---- Effective-LOC exclusion rules (section 4) --------------------------
# Recorded verbatim into output so the ruleset is reproducible.
EXCLUDE_PATH_SUBSTRINGS = [
    "node_modules/", "vendor/", "dist/", "build/", "/out/", ".next/",
    "coverage/", "target/debug/", "target/release/", ".venv/", "venv/",
    "__pycache__/", ".terraform/", "site-packages/",
]
EXCLUDE_BASENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "composer.lock", "Gemfile.lock", "poetry.lock", "Pipfile.lock",
    "Cargo.lock", "go.sum", "flake.lock",
}
EXCLUDE_SUFFIXES = [
    ".min.js", ".min.css", ".map", ".lock",
    ".snap",                       # test snapshots
    ".pb.go", "_pb2.py", "_pb2_grpc.py", ".pb.cc", ".pb.h",  # generated protobufs
    ".generated.ts", ".generated.js", ".g.dart",
]
# Generated-migration / dump heuristics (path contains + suffix)
EXCLUDE_GENERATED_REGEX = [
    re.compile(r"/migrations?/.*\.(sql|py|rb|js|ts)$"),
    re.compile(r".*\.(dump|sqlite|db|bak)$"),
    re.compile(r"(^|/)dist(/|$)"),
]

EXCLUSION_RULES = {
    "path_substrings": EXCLUDE_PATH_SUBSTRINGS,
    "basenames": sorted(EXCLUDE_BASENAMES),
    "suffixes": EXCLUDE_SUFFIXES,
    "generated_regex": [r.pattern for r in EXCLUDE_GENERATED_REGEX],
    "binary_files": "excluded from effective LOC (git numstat reports '-')",
    "note": "raw_* counts everything git tracked; effective_* removes the above.",
}

# ---- Language & tech-domain mapping (section 8) -------------------------
EXT_LANG = {
    ".rs": "Rust", ".go": "Go", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".cjs": "JavaScript", ".py": "Python", ".rb": "Ruby", ".java": "Java",
    ".kt": "Kotlin", ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++",
    ".hpp": "C++", ".cs": "C#", ".php": "PHP", ".swift": "Swift",
    ".scala": "Scala", ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".sass": "SCSS", ".vue": "Vue", ".svelte": "Svelte", ".dart": "Dart",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".clj": "Clojure",
    ".hs": "Haskell", ".lua": "Lua", ".r": "R", ".jl": "Julia",
    ".md": "Markdown", ".mdx": "Markdown", ".yml": "YAML", ".yaml": "YAML",
    ".json": "JSON", ".toml": "TOML", ".tf": "HCL/Terraform", ".hcl": "HCL/Terraform",
    ".dockerfile": "Dockerfile", ".proto": "Protobuf", ".graphql": "GraphQL",
    ".ipynb": "Jupyter", ".ml": "OCaml", ".zig": "Zig", ".wat": "WebAssembly",
    ".sol": "Solidity", ".tex": "TeX",
}
BASENAME_LANG = {
    "Dockerfile": "Dockerfile", "Makefile": "Makefile",
    "docker-compose.yml": "YAML", "docker-compose.yaml": "YAML",
}

LANG_DOMAIN = {
    "TypeScript": "frontend", "JavaScript": "frontend", "Vue": "frontend",
    "Svelte": "frontend", "HTML": "frontend", "CSS": "frontend", "SCSS": "frontend",
    "Rust": "backend", "Go": "backend", "Python": "backend", "Ruby": "backend",
    "Java": "backend", "Kotlin": "backend", "C": "backend", "C++": "backend",
    "C#": "backend", "PHP": "backend", "Scala": "backend", "Elixir": "backend",
    "SQL": "database",
    "HCL/Terraform": "infrastructure", "Dockerfile": "infrastructure",
    "Makefile": "infrastructure",
    "Shell": "automation",
    "Jupyter": "data pipeline", "R": "data pipeline", "Julia": "data pipeline",
    "Protobuf": "backend", "GraphQL": "backend",
}
# Path-based domain hints (checked before language mapping for CI/infra).
def path_domain(path):
    p = path.lower()
    if ".github/workflows/" in p or "/.gitlab-ci" in p or "cloudbuild" in p \
            or "/ci/" in p or "jenkinsfile" in p.split("/")[-1]:
        return "CI/CD"
    if "/terraform/" in p or p.endswith(".tf") or "/k8s/" in p \
            or "/kubernetes/" in p or "/helm/" in p or "/infra" in p \
            or "dockerfile" in p.split("/")[-1]:
        return "infrastructure"
    if "/prompts/" in p or "/prompt/" in p or "llm" in p or "/agents/" in p \
            or "embedding" in p or "/rag/" in p:
        return "AI / LLM"
    if "/pipeline" in p or "/etl/" in p or "/ingest" in p or "airflow" in p:
        return "data pipeline"
    return None

CONVENTIONAL = ["feat", "fix", "refactor", "test", "docs", "chore",
                "ci", "build", "perf", "style", "revert"]
CC_RE = re.compile(r"^(feat|fix|refactor|test|docs|chore|ci|build|perf|style|revert)(\([^)]*\))?!?:", re.I)


def run(repo, args):
    return subprocess.run(["git", "-C", repo] + args, capture_output=True,
                          text=True, errors="replace").stdout


def is_person(name, email):
    e = (email or "").lower()
    n = (name or "").lower()
    if e in PERSON_EMAILS:
        return True
    if any(m in n for m in AI_NAME_MARKERS) or any(m in e for m in AI_EMAIL_MARKERS):
        return False
    if n in {x.lower() for x in PERSON_NAMES} and "[bot]" not in n:
        # name-only match: accept only if email is not a bot address
        if not any(m in e for m in BOT_NAME_MARKERS):
            return True
    return False


def is_ai_agent(name, email):
    e = (email or "").lower()
    n = (name or "").lower()
    if any(m in n for m in AI_NAME_MARKERS):
        return True
    if any(m in e for m in AI_EMAIL_MARKERS):
        return True
    return False


def is_bot(name, email):
    e = (email or "").lower()
    n = (name or "").lower()
    if is_ai_agent(name, email):
        return False
    return any(m in n for m in ["[bot]", "github-actions", "dependabot",
                                "renovate", "mergify"]) or e.endswith("[bot]@users.noreply.github.com")


def classify_path(path):
    base = os.path.basename(path)
    low = path.lower()
    if base in EXCLUDE_BASENAMES:
        return False
    if any(s in low for s in EXCLUDE_PATH_SUBSTRINGS):
        return False
    if any(low.endswith(sfx) for sfx in EXCLUDE_SUFFIXES):
        return False
    for rgx in EXCLUDE_GENERATED_REGEX:
        if rgx.search(low):
            return False
    return True


def lang_of(path):
    base = os.path.basename(path)
    if base in BASENAME_LANG:
        return BASENAME_LANG[base]
    _, ext = os.path.splitext(base)
    return EXT_LANG.get(ext.lower())


def domain_of(path, lang):
    d = path_domain(path)
    if d:
        return d
    return LANG_DOMAIN.get(lang)


def iso_week(dt):
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def main():
    repo = sys.argv[1]
    start = "2026-04-01"
    end = None
    for i, a in enumerate(sys.argv):
        if a == "--start":
            start = sys.argv[i + 1]
        elif a == "--end":
            end = sys.argv[i + 1]

    start_dt = datetime.fromisoformat(start).replace(tzinfo=JST)
    end_dt = (datetime.fromisoformat(end).replace(tzinfo=JST)
              if end else datetime.now(JST))

    repo_name = os.path.basename(os.path.abspath(repo))

    # --- enumerate commits with author identity & timestamp (all history) ---
    # format: sha<TAB>author_name<TAB>author_email<TAB>iso_date<TAB>subject
    log = run(repo, ["log", "--no-merges", "HEAD",
                     "--pretty=format:%H\x1f%an\x1f%ae\x1f%aI\x1f%s"])
    all_authors = Counter()
    person_id_variants = Counter()
    bot_id_variants = Counter()
    ai_id_variants = Counter()
    ai_commits_in_window = 0
    bot_commits_in_window = 0

    # repo-wide & person commit lists within window
    repo_commits_in = []      # (sha, dt, subject, is_person)
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) < 5:
            continue
        sha, an, ae, aiso, subj = parts[0], parts[1], parts[2], parts[3], parts[4]
        try:
            dt = datetime.fromisoformat(aiso).astimezone(JST)
        except ValueError:
            continue
        key = f"{an} <{ae}>"
        all_authors[key] += 1
        person = is_person(an, ae)
        ai = is_ai_agent(an, ae)
        bot = is_bot(an, ae)
        if person:
            person_id_variants[key] += 1
        elif ai:
            ai_id_variants[key] += 1
        elif bot:
            bot_id_variants[key] += 1
        if start_dt <= dt <= end_dt:
            repo_commits_in.append((sha, dt, subj, person))
            if ai and not person:
                ai_commits_in_window += 1
            if bot and not person:
                bot_commits_in_window += 1

    # --- per-commit numstat for PERSON commits in window (churn) ----------
    # Use one git log call with numstat, filtered by author emails.
    author_args = []
    for e in PERSON_EMAILS:
        author_args += ["--author", e]
    for n in PERSON_NAMES:
        author_args += ["--author", n]

    numstat = run(repo, ["log", "--no-merges", "HEAD",
                         f"--since={start}T00:00:00+09:00",
                         f"--until={end_dt.strftime('%Y-%m-%dT%H:%M:%S')}+09:00"]
                        + author_args +
                        ["--pretty=format:\x1fCOMMITREC\x1f%H\x1f%aI\x1f%s",
                         "--numstat"])

    raw_add = raw_del = eff_add = eff_del = 0
    excl_add = excl_del = 0
    files_changed = set()
    eff_files_changed = set()
    binary_files = set()
    lang_stats = defaultdict(lambda: {"effective_lines_added": 0,
                                      "effective_lines_deleted": 0,
                                      "files": set()})
    domain_stats = defaultdict(lambda: {"effective_lines_added": 0,
                                        "effective_lines_deleted": 0,
                                        "files": set()})
    commit_types = Counter()
    person_commit_shas = []
    person_days = Counter()          # date -> commit count
    monthly = defaultdict(lambda: defaultdict(int))
    weekly = defaultdict(lambda: defaultdict(int))
    cur_dt = None

    skip_commit = False
    for line in numstat.splitlines():
        if line.startswith("\x1fCOMMITREC\x1f"):
            _, _, sha, aiso, subj = line.split("\x1f")
            dt = datetime.fromisoformat(aiso).astimezone(JST)
            # re-filter on author date for consistency with the window pass
            if not (start_dt <= dt <= end_dt):
                skip_commit = True
                cur_dt = None
                continue
            skip_commit = False
            cur_dt = dt
            person_commit_shas.append(sha)
            day = dt.strftime("%Y-%m-%d")
            person_days[day] += 1
            m = dt.strftime("%Y-%m")
            wk = iso_week(dt)
            monthly[m]["commits"] += 1
            weekly[wk]["commits"] += 1
            # commit-type classification (Conventional Commits only)
            mt = CC_RE.match(subj.strip())
            if mt:
                commit_types[mt.group(1).lower()] += 1
            else:
                commit_types["other"] += 1
            continue
        if not line.strip() or cur_dt is None:
            continue
        cols = line.split("\t")
        if len(cols) != 3:
            continue
        a_str, d_str, path = cols
        # handle rename "old => new"
        if "=>" in path:
            m2 = re.search(r"\{.*=> (.*?)\}", path)
            if m2:
                path = re.sub(r"\{.*?\}", m2.group(1), path)
            else:
                path = path.split("=>")[-1].strip()
        path = path.strip()
        if a_str == "-" or d_str == "-":
            binary_files.add(path)
            files_changed.add(path)
            continue
        a, d = int(a_str), int(d_str)
        raw_add += a
        raw_del += d
        files_changed.add(path)
        m = cur_dt.strftime("%Y-%m")
        wk = iso_week(cur_dt)
        if classify_path(path):
            eff_add += a
            eff_del += d
            eff_files_changed.add(path)
            monthly[m]["effective_loc"] += (a + d)
            weekly[wk]["effective_loc"] += (a + d)
            lang = lang_of(path) or "Other"
            lang_stats[lang]["effective_lines_added"] += a
            lang_stats[lang]["effective_lines_deleted"] += d
            lang_stats[lang]["files"].add(path)
            dom = domain_of(path, lang)
            if dom:
                domain_stats[dom]["effective_lines_added"] += a
                domain_stats[dom]["effective_lines_deleted"] += d
                domain_stats[dom]["files"].add(path)
        else:
            excl_add += a
            excl_del += d

    # active-day streak
    days_sorted = sorted(person_days.keys())
    longest = cur = 0
    prev = None
    for ds in days_sorted:
        d = datetime.fromisoformat(ds).date()
        if prev is not None and (d - prev).days == 1:
            cur += 1
        else:
            cur = 1
        longest = max(longest, cur)
        prev = d

    # first/last commit dates (person + repo, in window and overall)
    def first_last(commits):
        if not commits:
            return None, None
        ds = sorted(c[1] for c in commits)
        return ds[0].isoformat(), ds[-1].isoformat()

    repo_first, repo_last = first_last(repo_commits_in)
    person_in = [c for c in repo_commits_in if c[3]]
    person_first, person_last = first_last(person_in)

    # overall first/last person commit (any date, for repo tenure)
    person_all_dates = []
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) < 5:
            continue
        _, an, ae, aiso, _ = parts[:5]
        if is_person(an, ae):
            try:
                person_all_dates.append(datetime.fromisoformat(aiso).astimezone(JST))
            except ValueError:
                pass
    person_all_first = min(person_all_dates).isoformat() if person_all_dates else None
    person_all_last = max(person_all_dates).isoformat() if person_all_dates else None

    def finalize(stats):
        out = {}
        for k, v in stats.items():
            out[k] = {
                "effective_lines_added": v["effective_lines_added"],
                "effective_lines_deleted": v["effective_lines_deleted"],
                "files_changed": len(v["files"]),
            }
        return dict(sorted(out.items(),
                           key=lambda kv: -(kv[1]["effective_lines_added"]
                                            + kv[1]["effective_lines_deleted"])))

    # --- AI co-author trailer signal (person commits in window) -----------
    coauthor_log = run(repo, ["log", "--no-merges", "HEAD",
                              f"--since={start}T00:00:00+09:00",
                              f"--until={end_dt.strftime('%Y-%m-%dT%H:%M:%S')}+09:00"]
                             + author_args +
                             ["--pretty=format:\x1fMSG\x1f%H%n%b\x1fEND\x1f"])
    ai_coauthor_commits = 0
    _cur_has = False
    for block in coauthor_log.split("\x1fMSG\x1f"):
        if AI_COAUTHOR_RE.search(block):
            ai_coauthor_commits += 1

    person_commit_count = len(person_commit_shas)
    active_days = len(person_days)
    median_cpad = None
    if person_days:
        vals = sorted(person_days.values())
        n = len(vals)
        median_cpad = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2

    result = {
        "repo_name": repo_name,
        "analysis_window": {"start": start, "end": end_dt.strftime("%Y-%m-%d")},
        "git": {
            "total_commits": len(repo_commits_in),
            "repository_total_commits_in_window": len(repo_commits_in),
            "author_commits": person_commit_count,
            "active_days": active_days,
            "unique_commit_days": active_days,
            "longest_active_streak": longest,
            "median_commits_per_active_day": median_cpad,
            "raw_lines_added": raw_add,
            "raw_lines_deleted": raw_del,
            "effective_lines_added": eff_add,
            "effective_lines_deleted": eff_del,
            "excluded_lines_added": excl_add,
            "excluded_lines_deleted": excl_del,
            "files_changed": len(files_changed),
            "effective_files_changed": len(eff_files_changed),
            "binary_files_changed": len(binary_files),
            "commit_types": dict(commit_types),
            "ai_agent_authored_commits_in_window": ai_commits_in_window,
            "bot_authored_commits_in_window": bot_commits_in_window,
            "ai_coauthored_person_commits_in_window": ai_coauthor_commits,
            "first_commit_at_window": repo_first,
            "last_commit_at_window": repo_last,
            "author_first_commit_at_window": person_first,
            "author_last_commit_at_window": person_last,
            "author_first_commit_ever": person_all_first,
            "author_last_commit_ever": person_all_last,
        },
        "languages": finalize(lang_stats),
        "tech_domains": finalize(domain_stats),
        "monthly_activity": {m: dict(v) for m, v in sorted(monthly.items())},
        "weekly_activity": {w: dict(v) for w, v in sorted(weekly.items())},
        "contributor_attribution": {
            "contributor_count": len(all_authors),
            "author_commits": person_commit_count,
            "repository_total_commits_in_window": len(repo_commits_in),
            "author_commit_share": (round(person_commit_count / len(repo_commits_in), 4)
                                    if repo_commits_in else None),
            "all_authors": dict(all_authors.most_common()),
            "person_identity_variants": dict(person_id_variants),
            "ai_agent_identity_variants": dict(ai_id_variants),
            "bot_identity_variants": dict(bot_id_variants),
        },
        "active_days_list": days_sorted,
        "author_commits_by_day": dict(person_days),
        "exclusion_rules": EXCLUSION_RULES,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
