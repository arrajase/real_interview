# Architecture Review — `real_interview`

**Repo:** https://github.com/arrajase/real_interview
**Reviewed:** 2026-11-14
**Scope:** Full codebase (Flask + LangGraph + MongoDB), both sub-apps (`real_interview`, `trap_drills`), deployment config, auth, and data layer.

## Context

This is a solo-built, ~6-month-old project (23 commits since May 2026, ~12.2k lines of Python, ~5.1k lines of JS/HTML) deployed live on Render's free tier. It's a Flask monolith that walks a candidate through resume upload → job application → an AI-run mock panel interview (via LangGraph + OpenAI), produces a structured post-interview report, and includes two standout extras: a "Candidate Avatar" (an AI model of the user they can practice interviewing, or be interviewed by), and a second sibling app, Trap Drills, which runs spaced-repetition (Leitner-box) drilling on role-specific trick questions, personalized from the user's own completed interviews, with AI-generated questions gated behind a human approve/reject queue before they ever reach a live user.

For a project described as "vibe coded," the actual engineering maturity is noticeably higher than that term usually implies — several decisions below are the kind a junior engineer typically gets wrong and this codebase gets right. The review below is organized so you can see what's already solid (worth knowing explicitly, since this is good material for an interview story) and where the highest-leverage next investments are.

## What's Already Solid

**JWT configuration is actively defended, not just implemented.** `jwt_auth.py` refuses to boot in production with a missing secret, a secret under 32 characters, or a known placeholder value (`change-me`, etc.), and has a clearly-gated, explicitly-logged insecure-dev escape hatch (`ALLOW_INSECURE_JWT_DEV`). Most side projects ship with a hardcoded or trivially weak secret; this one makes that mistake hard to make by accident.

**Authorization is checked at the object level, not just the route level.** `interview_session_owned_by()` and `interviewer_practice_session_owned_by()` verify that the session ID being acted on actually belongs to the requesting user before returning data — this is exactly the IDOR (insecure direct object reference) gap that's easy to miss when wiring up routes quickly, and it's handled here.

**Rate limiting and LangGraph checkpointing are both MongoDB-backed**, meaning they're correct across multiple Gunicorn workers and across process restarts, not just correct on a single dev machine. The project currently runs single-worker on Render's free tier, but the persistence layer underneath it already assumes you'll eventually scale horizontally — that's the right thing to get right early, since it's hard to retrofit.

**The LangGraph-in-Flask adaptation is a genuinely good architectural call.** LangGraph assumes a long-running, continuously-executing graph; Flask is stateless request/response. Rather than fighting that mismatch, the project splits the interview into four separately-compiled sub-graphs (`start`, `chat`, `feedback`, `advance`), each invoked per HTTP call, with a shared Mongo checkpointer carrying state between calls. That's a legitimate, non-obvious solution to a real architectural tension — worth being able to explain clearly if asked "how did you make a stateful agent framework work inside a stateless web server."

**LLM calls degrade gracefully.** `PanelCoordinatorAgent` uses structured output (a Pydantic schema) for deciding which panel members speak next, clamps the returned indices to a valid range, and falls back to a deterministic rule (round-robin / fixed pair) if the LLM call fails or returns garbage. The interview doesn't break because a model call hiccuped.

**The AI-generated content has a human gate before it reaches users.** Trap Drills' "Phase 1" question generation goes through an approve/reject review queue before anything lands in a live due-queue — a real trust/quality control, not just "let the model write it and ship it."

## Where to Invest Next

### 1. Zero test coverage on the core product (highest leverage)

`trap_drills` has two test files (Leitner logic, dashboard weak-category rule). `real_interview` — the resume parsing, the routing/agent graph, the interview state machine, the feedback generation — has none. This is the single highest-leverage gap, for a specific reason: the bugs most likely to bite you here aren't syntax errors, they're *state-machine* bugs — a routing conditional sends the graph down the wrong edge, a node reads stale state, a summarization threshold fires at the wrong turn — and those are exactly the bugs that regress silently when you touch unrelated code weeks later, with no test to catch it before a real interview session breaks mid-conversation.

Start narrow and cheap: unit tests for the routing functions in `interview_nodes.py` (`route_after_start`, `should_summarize`, the advance-graph branch) don't need a real LLM call — they're pure functions over state, so they're fast to write and fast to run. Then add one or two tests per agent that mock the LLM call and assert the fallback path actually fires when the model call raises (you already wrote the fallback logic in `PanelCoordinatorAgent` — a test proves it still works after the next refactor).

### 2. No CI pipeline

`.github/workflows/` exists but contains only a `.gitkeep` — there's no automated gate running on push or PR. Once even a handful of tests exist from #1, a minimal GitHub Actions workflow (install deps, run pytest, maybe a lint pass) closes the loop: tests that exist but never run automatically catch far fewer regressions than tests wired into CI.

### 3. Model selection is centralized but hardcoded

Every agent shares one `OpenAILLM` wrapper, and that wrapper hardcodes `gpt-4o-mini` in exactly one place (`llm/openaillm.py`). The centralization is already correct — this is a one-line change, not a refactor — but right now every agent (panel coordinator deciding "who speaks next," full feedback-report generation, resume parsing, the summarizer) uses the same model regardless of how much reasoning the task actually needs. `params.yaml` already exists as the place interview tuning lives (token thresholds, question limits, etc.) — extending it to carry per-agent or per-task model selection would let you deliberately route cheap/fast tasks (panel-speaker selection, routing) to a smaller model and reserve the more capable one for tasks where output quality actually matters (feedback generation, candidate avatar answers), without touching code to do it.

### 4. Frontend has no build step or shared structure

Four hand-written vanilla-JS files (`app.js`, `admin.js`, `feedback.js`, plus Trap Drills' `app.js`) with no component reuse, no bundler, no type checking. Fine for the current size, but Trap Drills alone already needed four screens (Today's Review, Category Dashboard, Manage Questions, History) — this is the part of the codebase that will get noticeably harder to extend first as more screens get added, not because anything's broken today, but because duplication across hand-written DOM manipulation compounds quietly.

### 5. Repo hygiene — dead files

`app.py` (0 bytes — `main.py` is the real entrypoint), `research.ipynb` (0 bytes), and `schema.yaml` (0 bytes) sit in the repo root with no content and no obvious purpose. Harmless, but worth a cleanup pass so a new reader (or you, in six months) isn't left guessing whether they're vestigial or load-bearing.

## Trade-off: Where To Put Limited Time First

| Option | Effort | Risk reduced | Notes |
|---|---|---|---|
| **A. Tests on the LangGraph routing/state logic** | Low–Medium | High | Pure-function routing tests are cheap; mocked-LLM fallback tests are cheap. This is where silent regressions actually happen. |
| **B. CI pipeline** | Low | Medium | Nearly free once (A) exists; multiplies the value of every future test you write. |
| **C. Per-agent model tiering via `params.yaml`** | Low | Low (cost/latency, not correctness) | Worth doing, but it's a cost/performance lever, not a stability one — sequence it after A/B. |
| **D. Frontend framework/build step migration** | High | Low today, rising over time | Not urgent. Revisit if you're about to add several more screens, not before. |

Recommended order: **A → B → C**, with **D** deferred until the frontend's screen count grows enough to justify the migration cost.

## Action Items

1. [ ] Write unit tests for `route_after_start`, `should_summarize`, and the advance-graph branch condition in `interview_nodes.py` — pure functions, no LLM calls needed.
2. [ ] Add 1–2 tests per LLM-backed agent asserting the fallback path fires correctly when the model call raises or returns an invalid structured output.
3. [ ] Add a minimal GitHub Actions workflow: install deps, run the test suite, on every push/PR.
4. [ ] Move the hardcoded `gpt-4o-mini` model name into `params.yaml` (or env var), and decide per-agent whether it needs the full model or a cheaper one.
5. [ ] Delete or populate the three 0-byte root files (`app.py`, `research.ipynb`, `schema.yaml`) so the entrypoint and project structure read unambiguously.
6. [ ] Revisit frontend structure only once Trap Drills or Real Interview adds its next couple of screens — not before.
