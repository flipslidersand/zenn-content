---
title: "Sandboxed Code Evaluation for AI-Generated Outputs — How I Built SafeCode Arena"
emoji: "🧪"
type: "tech"
topics: ["AI", "Rust", "CodeVerification", "Wasm", "Security"]
published: true
---

## The Problem: Candidate Code Without Trust

You're using Cursor, Claude Code, or GitHub Copilot. The AI gives you three implementation options for the same feature.

```
AI: "Here are three approaches:
  A) Quick but uses unsafe
  B) Slower but memory-safe
  C) Balanced tradeoffs"

You: "Which one should I ship?"
AI: "It depends..."
```

That **"it depends"** is where responsibility falls through the cracks.

Tests tell you if code compiles and passes specs. But they don't tell you about security, performance, maintainability, or resource limits — all at once. You end up making the call by gut feel.

**This essay is about building a system that doesn't let that happen.**

## The Solution: Multi-Axis Scoring

I built [SafeCode Arena](https://github.com/flipslidersand/safecode-arena) — an automated verifier that evaluates code candidates across five axes simultaneously, scores each, and surfaces the tradeoffs.

### The Five Axes

| Axis                | Weight | Computation                                        |
| ------------------- | ------ | -------------------------------------------------- |
| **Correctness**     | 50%    | compile (40%) + tests (40%) + property tests (20%) |
| **Security**        | 20%    | unsafe heuristics (50%) + clippy warnings (50%)    |
| **Performance**     | 15%    | relative compile+test time across candidates       |
| **Maintainability** | 10%    | function-length heuristics (60%) + clippy (40%)    |
| **Resource Usage**  | 5%     | pass/fail of sandboxed Wasm execution              |

### Why These Five?

1. **Correctness dominates** — code that doesn't work is valueless, so it's 50%
2. **Security is explicit** — `unsafe` compiles fine, but you need to detect it yourself
3. **Performance and maintainability matter equally** — a fast mess vs. a slow masterpiece aren't comparable
4. **Resource limits are real** — a 100-point algorithm that consumes 2GB is a fail in production

### Example Scorecard

```
Candidate A: 85 points
├─ correctness:     100 (all tests pass)
├─ security:        60 (2 unsafe blocks flagged)
├─ performance:     70 (10% slower than B)
├─ maintainability: 85 (avg function 25 lines)
└─ resource_usage:  80 (Wasm sandbox: 512MB, OK)

Candidate B: 92 points ✓ Recommended
├─ correctness:     95 (1 edge case warning)
├─ security:        95 (no unsafe)
├─ performance:     95 (fastest)
├─ maintainability: 88 (avg function 20 lines)
└─ resource_usage:  100 (Wasm sandbox: 200MB)
```

Now the choice is **defensible**. You can explain _why_ B won.

## Implementation Patterns

### 1. Isolate Execution with Wasm

AI-generated code can hang, crash, or consume unbounded memory. Running it bare-metal is reckless.

```rust
// Compile the candidate → link to Wasm
let instance = linker.instantiate(&module)?;
let run_fn = instance.get_typed_func::<(), ()>(&mut store, "run")?;

// Set fuel (instruction budget) and memory limit
store.set_fuel(100_000_000)?;  // ~100M instructions
store.set_memory_limit(1_000_000_000)?;  // 1GB max

// Run with hard limits
run_fn.call(&mut store, ())?;  // Will trap if it exceeds limits
```

**Result**: The code runs in a box. If it tries to loop forever or allocate unbounded memory, it's killed cleanly with a trap. No crash, no OOM, just a resource_usage score of 0.

### 2. Persist Evaluation History

Comparing one candidate is useful. Comparing against _past_ candidates is gold.

```rust
// Log every evaluation to SQLite
db.execute(
    "INSERT INTO evals
     (spec_hash, code_hash, correctness, security, perf, maintain, resource, timestamp)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    params![
        hash(spec), hash(code),
        score.correctness, score.security, score.perf, score.maintain, score.resource,
        now()
    ],
)?;

// Detect regressions
let best = db.query_row(
    "SELECT score FROM evals WHERE spec_hash = ? ORDER BY timestamp DESC LIMIT 1",
    [spec_hash],
    |row| row.get(0),
)?;

if new_score < best - threshold {
    println!("⚠️  Regression detected: {} → {}", best, new_score);
}
```

**Why this matters**: You can build a changelog of "every candidate for this spec, ranked". Future devs can see what was tried and why something was chosen. That's audit trail.

### 3. Support Multiple Languages

Rust and Python coexist everywhere now. SafeCode Arena doesn't force you to rewrite everything in one language.

```rust
let scorer = match candidate.extension() {
    "rs" => RustScorer::new(),
    "py" => PythonScorer::new(),
    _ => return Err("Unsupported"),
};

let score = scorer.evaluate(candidate, tests)?;
```

**Benefit**: You can compare "the Rust solution" vs. "the Python solution" on the same rubric. Language is transparent to the ranking.

### 4. Compose into CI/CD

```yaml
# .github/workflows/evaluate-candidate.yml
name: Evaluate PR Candidate

on: pull_request

jobs:
  safecode:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Evaluate candidates
        run: |
          safecode evaluate pr-candidate.rs \
            --tests tests/ \
            --format json \
            --db history.db > score.json

      - name: Post score to PR
        run: |
          gh pr comment -b "$(cat score.json | jq -r '.report')"
```

**Result**: Every PR that proposes code gets a scored report. Developers see the scorecard before merge. No surprises in production.

## The Deeper Point: Rubrics as Responsibility

Here's what kept me thinking while building this.

**Choosing a rubric is choosing what you trust.**

### The Old Way: "I Know It When I See It"

```
Reviewer: "This code feels unsafe."
(Why? Personal experience, gut instinct, luck)

Next reviewer: "Is that still true?"
(No way to know. Depends on their experience.)
```

This doesn't scale. It's not reproducible. It's not teachable.

### SafeCode Arena's Way: Rubric Is Explicit

```
"Unsafe block found → -5 security points (non-negotiable)"
"Property test passes → +10 correctness points"
...
```

Now:

- **Everyone uses the same standard.** No surprises.
- **You can argue about it.** ("Is that unsafe _actually_ a risk?" → investigate → possibly adjust the rubric)
- **Future you can explain past you.** Auditable.

In the age of AI-generated code, **an explicit rubric is how you take responsibility for trust.**

You're not saying "AI is always right" or "AI is always wrong." You're saying: **"Here's what I checked. Here's the score. Here's why I merged it."**

## Real-World Workflow

```bash
# 1. AI generates 3 candidates (you pick the most promising)
# 2. Run the scorer
$ safecode evaluate solution_a.rs solution_b.rs \
    --tests tests/ \
    --db evals.db

# 3. Results
SafeCode Arena Comparison Report
─────────────────────────────────
Solution A: 78 points (correctness 85, security 60, perf 70, maintain 80, resource 95)
Solution B: 91 points (correctness 100, security 90, perf 95, maintain 85, resource 100) ← Winner

# 4. Confidence
(Run regression check: best_previous_score = 75, new = 91 → no regression, all good)

# 5. Merge
You ship Solution B, confident you can explain your choice.
```

## Status & Next Steps

SafeCode Arena has completed phases 1–5:

- ✅ All 5 scoring axes implemented
- ✅ Rust & Python support
- ✅ Wasm sandbox isolation
- ✅ SQLite persistence + regression detection
- ✅ Multi-output formats (JSON, table, HTML)

Coming next:

- Go & JavaScript support
- Mutation testing (bonus axis)
- Integration with GitHub PR workflows

## Why This Matters Now

Cursor, Claude Code, GitHub Copilot, and similar tools are shipping code daily. The industry collectively acts like "the AI picked it, so it's fine," which is how you end up with security holes in production.

**SafeCode Arena is my answer to that:** Not "don't trust AI," but "trust AI + verify systematically."

---

**GitHub**: https://github.com/flipslidersand/safecode-arena  
**License**: MIT  
**Stack**: Rust, Wasm (wasmtime), SQLite, Python
