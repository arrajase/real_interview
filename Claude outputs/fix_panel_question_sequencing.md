# Fixes: panel pacing + more realistic interviewer personas + UI redesign

Paste this into VS Code (or hand it to an AI coding assistant there) against the `real_interview` repo. Three separate, unrelated changes are bundled in this file — commit each separately (suggested messages are at the bottom of each section):

- **Edits 1–3 (Part A)**: the panel asking two questions per turn, and the downstream report-pairing bug it causes.
- **Edit 4 (Part B)**: more realistic interviewer personas (question technique + evaluation rubric, not just tone) plus experience-level calibration.
- **Part C**: a full visual redesign of all three `real_interview` frontend screens (main app, admin dashboard, feedback page) — "Slate (light)" palette, chosen after reviewing a live preview.

## Part A — Edits 1–3: panel pacing and the report bug it causes

## Why

`PanelCoordinatorAgent` is allowed to pick up to 2 speakers per turn (opening and follow-up), and `_run_panel_speakers` in `interview_nodes.py` generates a full reply from each one and returns both in the same turn — so the candidate can get two unanswered questions at once, every opening and often every follow-up. That same gap also corrupts the "ideal answers" report: `extract_interview_qa_pairs` pairs *every* pending question with whatever single answer the candidate gives next, so two different questions can end up mapped to the identical answer text. Fixing the pacing issue removes the report bug too, since `pending` will never hold more than one question once this lands.

## Edit 1 — `app/real_interview/backend/agents/panel_coordinator_agent.py`

**Give `_clamp_indices` a `max_speakers` parameter (default 2, so the opening path is unaffected):**

Find:
```python
    def _clamp_indices(self, indices: List[int], panel_size: int) -> List[int]:
        seen: set[int] = set()
        out: List[int] = []
        for raw in indices:
            idx = int(raw)
            if idx < 0 or idx >= panel_size or idx in seen:
                continue
            seen.add(idx)
            out.append(idx)
            if len(out) >= 2:
                break
        return out
```

Replace with:
```python
    def _clamp_indices(self, indices: List[int], panel_size: int, max_speakers: int = 2) -> List[int]:
        seen: set[int] = set()
        out: List[int] = []
        for raw in indices:
            idx = int(raw)
            if idx < 0 or idx >= panel_size or idx in seen:
                continue
            seen.add(idx)
            out.append(idx)
            if len(out) >= max_speakers:
                break
        return out
```

**In `plan_follow_up`, cap to exactly one speaker and update the prompt text to match:**

Find (the system message inside `plan_follow_up`):
```python
        system = SystemMessage(
            content=(
                "You coordinate a live panel interview. All interviewers are present and hear every answer.\n"
                "After each candidate answer, choose 1–2 panel members who should ask the next follow-up.\n"
                "Base questions on what the candidate just said — probe gaps, trade-offs, or depth.\n"
                "Rotate speakers; avoid the same person dominating unless their style fits the topic.\n"
                "Return speaker_indices as 0-based indices (max 2)."
            )
        )
```

Replace with:
```python
        system = SystemMessage(
            content=(
                "You coordinate a live panel interview. All interviewers are present and hear every answer.\n"
                "After each candidate answer, choose exactly ONE panel member who should ask the next follow-up.\n"
                "Base the question on what the candidate just said — probe gaps, trade-offs, or depth.\n"
                "Rotate speakers across turns; avoid the same person dominating unless their style fits the topic.\n"
                "Return speaker_indices as a list containing exactly one 0-based index."
            )
        )
```

Find (the clamp call a few lines later, inside the same method):
```python
        try:
            plan: PanelResponsePlan = llm.invoke([system, user])
            indices = self._clamp_indices(plan.speaker_indices, panel_size)
            if indices:
                logger.info("[PanelCoordinator] follow-up speakers=%s", indices)
                return indices
```

Replace with:
```python
        try:
            plan: PanelResponsePlan = llm.invoke([system, user])
            indices = self._clamp_indices(plan.speaker_indices, panel_size, max_speakers=1)
            if indices:
                logger.info("[PanelCoordinator] follow-up speakers=%s", indices)
                return indices
```

`_fallback_follow_up` already returns a single-element list — no change needed there.

**Optional tidy-up, same file, for consistency:** the `plan_opening` system message still describes the second panelist adding "one complementary opening question" — update that phrase to match Edit 2 below (second panelist introduces themselves only), so the coordinator's own prompt doesn't contradict what the interviewer agent is now told to do.

## Edit 2 — `app/real_interview/backend/agents/interviewer_agent.py`

**In `opening_message`, stop telling the second (non-lead) panelist to ask a question:**

Find:
```python
        else:
            prompt_text = (
                "You are joining an ongoing panel opening. Another panelist already welcomed the candidate. "
                "Briefly introduce yourself in character and ask one complementary opening question "
                "that fits your interviewer style. Do not repeat the other panelist's question."
            )
```

Replace with:
```python
        else:
            prompt_text = (
                "You are joining an ongoing panel opening. Another panelist already welcomed the candidate "
                "and asked the opening question. Briefly introduce yourself in character — one or two "
                "sentences, no more. Do NOT ask a question of your own; the lead panelist's question is the "
                "only question at the opening."
            )
```

## Edit 3 — `app/real_interview/backend/services/interview_qa_extract.py`

**Add a regression guard: this file should never see more than one pending question once Edits 1–2 are in place. Log loudly if it ever does, instead of silently fanning the answer out.**

Find:
```python
        if role == "user" and pending:
            for item in pending:
                pairs.append(
                    {
                        "interviewer": item["interviewer"],
                        "question": item["question"],
                        "candidate_answer": content,
                    }
                )
            pending = []
```

Replace with:
```python
        if role == "user" and pending:
            if len(pending) > 1:
                # Should not happen once the panel is capped to one active question per turn
                # (see panel_coordinator_agent.py / interviewer_agent.py). Logged, not raised,
                # so report generation still degrades gracefully if it ever recurs.
                import logging

                logging.getLogger(__name__).warning(
                    "[interview_qa_extract] %d pending questions resolved to one answer "
                    "(expected at most 1) — check panel pacing for a regression.",
                    len(pending),
                )
            for item in pending:
                pairs.append(
                    {
                        "interviewer": item["interviewer"],
                        "question": item["question"],
                        "candidate_answer": content,
                    }
                )
            pending = []
```

(If the file already has a module-level logger imported elsewhere in the codebase's style — check `app/real_interview/__init__.py`'s `logger` — prefer reusing that import instead of the inline `import logging`, to match the rest of the codebase's logging convention.)

### How to verify Part A after applying

1. Start a fresh mock interview locally and confirm the opening now shows exactly one question (the lead's), even if a second panelist's intro line appears.
2. Answer a few turns and confirm each follow-up turn produces exactly one `[I#]:` question before your next reply is expected.
3. Complete an interview with the Candidate Avatar / ideal-answers report enabled, download the report, and confirm each Q&A entry's `candidate_answer` plausibly matches its own question (no two questions sharing identical answer text).
4. Check logs for the new `[interview_qa_extract]` warning — it should never fire on a freshly-run interview after these changes.

### Suggested commit message for Part A

```
Cap panel to one active question per turn; fix downstream Q&A misattribution

- panel_coordinator_agent.py: plan_follow_up now returns exactly one
  speaker index instead of up to two, so the candidate never gets two
  unanswered questions at once.
- interviewer_agent.py: the non-lead opening panelist now introduces
  themselves only, instead of adding a second opening question.
- interview_qa_extract.py: log a warning if more than one question is
  ever still pending when an answer arrives, since that should no
  longer happen and previously caused the same candidate answer to be
  misattributed to two different questions in the ideal-answers report.
```

## Part B — Edit 4: more realistic interviewer personas + experience-level calibration

### Why

The three personas in `INTERVIEWER_PROMPTS` vary interviewer *tone* ("very positive," "very negative," "objective"), not interviewer *technique*. Real interviewers don't announce their emotional disposition — what makes one feel tough and another feel supportive is how they probe, not how harshly they react. As written, "negative" risks reading as performatively hostile rather than rigorous ("your tone is challenging"), and "positive" explicitly says "analyze answers positively; be motivating," which can bias the model toward leniency rather than fairness. Neither variant gives the model an actual interviewing technique — "test knowledge starting from basics" and "ask many process-oriented questions" are vague enough to produce generic, textbook Q&A. And there's no evaluation rubric: "state clearly whether you would select them and why" with nothing underneath it means the model forms a vibe over the conversation instead of tracking actual evidence.

There's also a concrete code gap: `experience_level` (junior/mid/senior) is computed by the router and used to pre-filter the question bank, but it's never told to the interviewer's own system prompt. `_system_prompt()` only takes `candidate_role` — so with no seed bank yet for that role/level, the interviewer has zero signal on how hard to go.

The rewrite below keeps rigor constant across all three personas and only varies *delivery* and *technique*; it adds explicit interviewing moves (anchor on resume specifics, ask for metrics/outcomes, probe alternatives and trade-offs, go deeper on strong answers, offer a narrower/easier version on weak ones instead of always starting from basics); and it threads `experience_level` into the system prompt so difficulty is explicitly calibrated rather than left to chance.

**Keep the dict keys exactly as `"positive"`, `"negative"`, `"objective"`** — `InterviewerType` in `state/interview_schemas.py` is a typed `Literal["positive", "negative", "objective"]` used elsewhere in the codebase, so only the template *text* changes, never the keys.

### Edit 4a — `app/real_interview/backend/agents/interviewer_agent.py`: rewrite `INTERVIEWER_PROMPTS`

Find:
```python
INTERVIEWER_PROMPTS = {
    "positive": (
        "You are a very experienced technical interviewer for the role of {candidate_role}. "
        "You are very positive in nature. After evaluating the candidate's resume and HR summary, "
        "test knowledge starting from basics. Questions must reflect the candidate's experience; "
        "probe further based on their answers. Analyze answers positively; be motivating. "
        "When the candidate indicates the interview is ending, state clearly whether you would "
        "select them and why."
    ),
    "negative": (
        "You are a very experienced technical interviewer for the role of {candidate_role}. "
        "You are very negative in nature. After evaluating the resume and HR summary, "
        "test from basics based on experience; probe on answers. Analyze answers critically; "
        "your tone is challenging. When the interview ends, state clearly whether you would select them."
    ),
    "objective": (
        "You are a very experienced technical interviewer for the role of {candidate_role}. "
        "You are objective and process-oriented. Ask many process-oriented questions grounded in "
        "the candidate's background and the role. When the interview ends, state clearly whether "
        "you would select them."
    ),
}
```

Replace with:
```python
INTERVIEWER_PROMPTS = {
    "positive": (
        "You are a senior technical interviewer for the role of {candidate_role}, known for being "
        "encouraging without lowering the bar. Ground every question in a specific detail from the "
        "candidate's resume or stated experience — ask them to walk through a real project, name the "
        "metric or outcome, and explain their specific individual contribution versus the team's. "
        "When an answer is strong, go one level deeper (a trade-off they considered, an alternative "
        "approach, what they'd do differently now) instead of moving on; when an answer is weak or "
        "vague, give them one chance to clarify with a narrower or easier version of the same question "
        "before moving on — don't accept vagueness just because your tone is warm. Track what's "
        "genuinely strong and genuinely missing as you go; your warmth should shape your delivery, not "
        "your judgment. When the interview ends, state clearly whether you would select them, grounded "
        "in specific examples from what they actually said."
    ),
    "negative": (
        "You are a senior technical interviewer for the role of {candidate_role}, known for being "
        "rigorous and hard to impress — but your rigor comes from depth, not hostility. Never accept a "
        "surface-level answer: anchor every question in a specific resume detail, and when the "
        "candidate gives a plausible-sounding answer, push on it — ask for the actual metric, the "
        "alternative they didn't choose and why, or what broke when they tried it. If an answer is "
        "vague or sounds rehearsed, say so directly and ask them to be concrete. Your tone can be terse "
        "and skeptical, but never dismissive, sarcastic, or designed to unsettle rather than assess — a "
        "real tough interviewer is hard to satisfy with vague answers, not unpleasant to talk to. When "
        "the interview ends, state clearly whether you would select them, citing the specific answers "
        "that drove your judgment, including where they held up under pressure and where they didn't."
    ),
    "objective": (
        "You are a senior technical interviewer for the role of {candidate_role} who runs a "
        "structured, methodology-driven interview. Track distinct competencies as the interview "
        "progresses — technical depth, problem-solving process (not just the final answer), "
        "communication clarity, and ownership/specificity of past work — and make sure your questions "
        "cover all of them rather than clustering on one. Prefer process questions over trivia: ask how "
        "they approached a problem, what alternatives they considered, how they'd validate a solution, "
        "and how they'd handle a constraint relevant to {candidate_role} (time, scale, a difficult "
        "stakeholder). Stay even-keeled regardless of answer quality — neither warmer nor harsher — so "
        "the signal comes from the questions, not your reaction. When the interview ends, give a "
        "decision grounded explicitly in each competency you tracked, naming where the evidence was "
        "strong and where it was thin."
    ),
}
```

### Edit 4b — same file: thread `experience_level` into `_system_prompt`

Find:
```python
    def _system_prompt(self, interviewer_type: str, candidate_role: str) -> str:
        template = INTERVIEWER_PROMPTS.get(interviewer_type, INTERVIEWER_PROMPTS["objective"])
        base = template.format(candidate_role=candidate_role or "the position")
        return (
            f"{base}\n\n"
            "Prefer curated question-bank seeds when provided; personalize them to this candidate's resume. "
            "Use tavily_web_search only when you need fresh technical facts or to probe deeper after a weak answer — "
            "not to fetch generic interview question lists.\n"
            "Stay in character for your interviewer style."
        )
```

Replace with:
```python
    def _system_prompt(self, interviewer_type: str, candidate_role: str, experience_level: str = "") -> str:
        template = INTERVIEWER_PROMPTS.get(interviewer_type, INTERVIEWER_PROMPTS["objective"])
        base = template.format(candidate_role=candidate_role or "the position")
        level_line = ""
        if experience_level:
            level_line = (
                f"\n\nCalibrate question difficulty to a {experience_level} candidate for this role — "
                "don't ask senior-scope system design questions of a junior candidate, and don't let a "
                "senior candidate coast on entry-level basics."
            )
        return (
            f"{base}{level_line}\n\n"
            "Prefer curated question-bank seeds when provided; personalize them to this candidate's resume. "
            "Use tavily_web_search only when you need fresh technical facts or to probe deeper after a weak answer — "
            "not to fetch generic interview question lists.\n"
            "Stay in character for your interviewer style."
        )
```

### Edit 4c — same file: pass `experience_level` through in `run_turn`

Find (inside `run_turn`, where the system message is built):
```python
        system = SystemMessage(
            content=(
                self._system_prompt(interviewer_type, candidate_role)
                + panel_block
                + "\n\nResume:\n"
                + format_parsed_resume(parsed_data)
                + "\n\nHR summary:\n"
                + format_first_impression(first_impression)
                + self._summary_context(interview_summary)
                + (
                    self._question_bank_context(question_bank_seeds or [], interviewer_type)
                    if turn_mode != "candidate_qa"
                    else ""
                )
            )
        )
```

Replace with:
```python
        experience_level = (panel_plan or {}).get("experience_level", "").strip()
        system = SystemMessage(
            content=(
                self._system_prompt(interviewer_type, candidate_role, experience_level)
                + panel_block
                + "\n\nResume:\n"
                + format_parsed_resume(parsed_data)
                + "\n\nHR summary:\n"
                + format_first_impression(first_impression)
                + self._summary_context(interview_summary)
                + (
                    self._question_bank_context(question_bank_seeds or [], interviewer_type)
                    if turn_mode != "candidate_qa"
                    else ""
                )
            )
        )
```

`opening_message` already calls `run_turn(..., panel_plan=panel_plan, ...)`, so the opening path picks up `experience_level` automatically — no separate change needed there.

### How to verify Part B after applying

1. Run one full interview per persona (positive, negative, objective) for the same resume/role and compare: all three should reach a similar verdict on a clearly weak answer — if "positive" is visibly more lenient on the same evidence, the warmth-vs-judgment separation didn't take.
2. Confirm questions reference specific resume details (a named project, a named technology) rather than generic textbook questions.
3. Give a deliberately vague answer mid-interview and confirm the interviewer pushes back for specifics rather than accepting it and moving on.
4. Run the same role with a junior-level and a senior-level candidate profile and confirm question difficulty visibly differs.
5. Check the final verdict message cites specific things the candidate said, not just a general impression.

### Suggested commit message for Part B

```
Rewrite interviewer personas for realism; calibrate difficulty to experience level

- interviewer_agent.py: INTERVIEWER_PROMPTS now varies interviewing
  technique and delivery (anchor on resume specifics, probe trade-offs,
  go deeper on strong answers, push back on vague ones) instead of just
  emotional tone, and all three personas ground their final verdict in
  specific evidence rather than general impression.
- interviewer_agent.py: _system_prompt and run_turn now thread
  experience_level from the panel plan into the interviewer's own
  system prompt, so question difficulty is explicitly calibrated
  instead of relying only on question-bank seeds that may not exist
  yet for a given role/level.
```

## Part C — Visual redesign: "Slate (light)" professional theme

### Why

The app is functionally solid but visually looked like an unstyled prototype — flat colors, no shadows/elevation, default table/pill styling, system font. This redesign is a pure CSS change: every selector in the current `styles.css` is preserved exactly (new colors, spacing, radius, and shadow values only), so no HTML or JS changes are needed and nothing you've wired up in `app.js` / `admin.js` / `feedback.js` (class toggling, `hidden` attributes, etc.) is affected. The `trap_drills/frontend` app reuses this same stylesheet and keeps working too, since none of its selectors were touched or removed.

Palette: a light, neutral "slate" theme (soft off-white background, white cards, muted blue-gray accent) plus the Inter font, elevated cards with subtle shadows, a segmented pill-style tab control, uppercase table headers, tinted status pills, and asymmetric-corner chat bubbles (speech-bubble shaping). This was chosen after reviewing a live multi-theme preview — four other palettes were also prototyped (Steel Blue dark, Slate & Graphite dark, Navy & Gold dark, Warm Stone light) in case you want to revisit the direction later; this file implements the one you picked.

### Edit 5 — `app/real_interview/frontend/styles.css`

**Replace the entire file contents with:**

```css
:root {
  color-scheme: light;
  --bg: #f4f5f7;
  --surface: #ffffff;
  --surface-raised: #fafbfc;
  --border: #e1e4e9;
  --border-strong: #c7cdd6;
  --text: #20242c;
  --muted: #636b79;
  --accent: #4a5a78;
  --accent-dim: #374361;
  --accent-ink: #ffffff;
  --danger: #b3453f;
  --danger-tint: rgba(179, 69, 63, 0.1);
  --ok: #2f7a4d;
  --ok-tint: rgba(47, 122, 77, 0.1);
  --radius-sm: 8px;
  --radius: 12px;
  --radius-lg: 16px;
  --shadow-sm: 0 1px 2px rgba(20, 25, 35, 0.06);
  --shadow-md: 0 10px 30px rgba(20, 25, 35, 0.1);
  --font: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
}

a {
  color: var(--accent);
}

a:hover {
  color: var(--accent-dim);
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}

/* ---------- Header / layout ---------- */

.site-header {
  padding: 2rem 1.25rem 0.75rem;
  text-align: center;
}

.site-header h1 {
  margin: 0 0 0.4rem;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.tagline {
  margin: 0 auto;
  max-width: 34rem;
  color: var(--muted);
  font-size: 0.93rem;
}

.layout {
  max-width: 640px;
  margin: 0 auto;
  padding: 0.75rem 1.25rem 3rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.admin-page .admin-layout {
  max-width: 1020px;
}

/* ---------- Card ---------- */

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.5rem 1.6rem;
  box-shadow: var(--shadow-sm);
}

.card h2 {
  margin: 0 0 1.1rem;
  font-size: 1.1rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

/* ---------- Tabs (segmented control) ---------- */

.tabs {
  display: flex;
  gap: 0.3rem;
  margin-bottom: 1.1rem;
  padding: 0.25rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.tab {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-weight: 600;
  font-size: 0.88rem;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.tab.is-active {
  background: var(--surface);
  border-color: var(--border);
  color: var(--accent-dim);
  box-shadow: var(--shadow-sm);
}

.tab-panel.is-hidden {
  display: none;
}

.job-input-tabs {
  margin-bottom: 0.85rem;
}

/* ---------- Form elements ---------- */

.stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stack label {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.86rem;
  font-weight: 500;
  color: var(--muted);
}

input[type="email"],
input[type="password"],
input[type="url"],
input[type="file"],
input[type="number"],
input[type="text"],
textarea,
select {
  padding: 0.6rem 0.7rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-family: var(--font);
}

input[type="email"]:focus,
input[type="password"]:focus,
input[type="url"]:focus,
input[type="file"]:focus,
input[type="number"]:focus,
input[type="text"]:focus,
textarea:focus,
select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 16%, transparent);
  outline: none;
}

input[type="checkbox"] {
  accent-color: var(--accent);
}

input[type="file"] {
  padding: 0.45rem;
}

textarea {
  resize: vertical;
  min-height: 8rem;
  line-height: 1.5;
}

.profile-settings-form input[type="number"] {
  width: 100%;
  max-width: 8rem;
}

/* ---------- Buttons ---------- */

.btn {
  font: inherit;
  font-family: var(--font);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  padding: 0.62rem 1.1rem;
  transition: filter 0.1s ease, border-color 0.1s ease, color 0.1s ease;
}

.btn.primary {
  background: var(--accent);
  color: var(--accent-ink);
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.btn.primary:hover {
  filter: brightness(1.08);
}

.btn.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn.secondary {
  background: var(--surface-raised);
  color: var(--text);
  border-color: var(--border-strong);
}

.btn.secondary:hover {
  border-color: var(--accent);
  color: var(--accent-dim);
}

.btn.link {
  background: none;
  border: none;
  color: var(--accent);
  text-decoration: underline;
  padding: 0 0 0 0.5rem;
  display: inline;
}

.btn.link.danger-link {
  color: var(--danger);
}

.btn.danger {
  background: var(--danger);
  color: #fff;
  border-color: var(--danger);
}

.btn.danger:hover {
  filter: brightness(1.08);
}

.upload-actions {
  margin-bottom: 0.85rem;
}

/* ---------- Hints / messages / links ---------- */

.hint {
  margin: 0 0 0.85rem;
  font-size: 0.82rem;
  color: var(--muted);
  line-height: 1.5;
}

.danger-hint {
  color: var(--danger);
}

.auth-link-row {
  margin: 0.5rem 0 0;
  text-align: center;
  font-size: 0.88rem;
}

.auth-link-sep {
  color: var(--muted);
  margin: 0 0.35rem;
}

label.confirm-delete {
  flex-direction: row;
  align-items: flex-start;
  gap: 0.5rem;
  color: var(--text);
  font-size: 0.88rem;
}

label.confirm-delete input {
  margin-top: 0.2rem;
  width: auto;
}

.message {
  margin: 1rem 0 0;
  min-height: 1.25rem;
  font-size: 0.9rem;
}

.message.is-error {
  color: var(--danger);
}

.message.is-ok {
  color: var(--ok);
}

.optional {
  color: var(--muted);
  font-weight: 400;
  font-size: 0.85em;
}

.signed-in {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.86rem;
  margin: 0 0 1.15rem;
  color: var(--muted);
}

.signed-in code {
  font-size: 0.8rem;
  word-break: break-all;
  color: var(--text);
  background: var(--bg);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.session-label {
  font-size: 0.78rem;
  color: var(--muted);
  margin-left: 0.5rem;
}

/* ---------- Tables / resume list ---------- */

.resume-list-wrap {
  margin-bottom: 1rem;
  overflow-x: auto;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.table-wrap .data-table {
  border: none;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
}

.data-table th,
.data-table td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--border);
  text-align: left;
}

.data-table th {
  background: transparent;
  color: var(--muted);
  font-weight: 600;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom: 1px solid var(--border-strong);
}

.data-table tbody tr.is-selected {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}

.resume-link {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: var(--accent);
  text-decoration: underline;
  cursor: pointer;
}

.resume-selected-wrap {
  margin-bottom: 0.85rem;
}

#resume-parsed-display {
  font-family: ui-monospace, "Cascadia Code", "Segoe UI Mono", monospace;
  font-size: 0.8rem;
}

#btn-continue-job {
  margin-bottom: 1rem;
}

.result {
  margin-top: 1rem;
  padding: 0.85rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg);
  font-size: 0.78rem;
  overflow: auto;
  max-height: 320px;
  white-space: pre-wrap;
}

.result.is-hidden {
  display: none;
}

/* ---------- Paused interview banner ---------- */

.paused-interview-banner {
  margin: 1rem 0;
  padding: 1rem 1.1rem;
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--accent) 8%, var(--surface));
}

.paused-interview-banner p {
  margin: 0 0 0.75rem;
}

/* ---------- Chat ---------- */

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 380px;
  overflow-y: auto;
  padding: 1rem;
  margin-bottom: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
}

.chat-bubble {
  max-width: 90%;
  padding: 0.65rem 0.85rem;
  border-radius: var(--radius);
  font-size: 0.89rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: var(--shadow-sm);
}

.chat-bubble.user {
  align-self: flex-end;
  background: var(--accent);
  color: var(--accent-ink);
  border: 1px solid var(--accent);
  border-bottom-right-radius: 4px;
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.chat-bubble.avatar {
  align-self: flex-start;
  background: color-mix(in srgb, var(--accent) 10%, var(--surface));
  border: 1px solid var(--accent-dim);
  border-left: 3px solid var(--accent);
  border-bottom-left-radius: 4px;
}

.avatar-discuss-messages {
  min-height: 14rem;
}

.avatar-discuss-meta {
  margin: 0 0 0.75rem;
  font-size: 0.88rem;
  color: var(--muted);
}

.avatar-discuss-sources {
  margin: 0.5rem 0 0;
  padding-left: 1.1rem;
  font-size: 0.85rem;
}

.avatar-discuss-sources a {
  word-break: break-all;
}

.chat-form {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

.chat-form input[type="text"] {
  flex: 1;
}

.chat-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  align-items: center;
}

.email-feedback-opt {
  flex: 1 1 100%;
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  font-size: 0.88rem;
  color: var(--muted);
  margin: 0 0 0.15rem;
  cursor: pointer;
}

.email-feedback-opt input {
  margin-top: 0.2rem;
}

.interview-context {
  margin-bottom: 1rem;
  font-size: 0.85rem;
}

.interview-context summary {
  cursor: pointer;
  color: var(--accent);
  font-weight: 500;
}

#interview-context-preview {
  max-height: 180px;
  margin-top: 0.5rem;
}

/* ---------- Interview report ---------- */

.interview-feedback-wrap h3 {
  margin: 0 0 0.6rem;
  font-size: 1.02rem;
  font-weight: 600;
}

.interview-feedback-wrap .btn {
  margin-top: 0.85rem;
}

.interview-report-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 0.85rem;
}

.interview-report {
  display: grid;
  gap: 1rem;
}

.interview-report-section {
  padding: 1rem 1.1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raised);
}

.interview-report-section h4 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--accent-dim);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.interview-report-section p,
.interview-report-section ul {
  margin: 0;
}

.interview-report-meta {
  font-size: 0.9rem;
  color: var(--muted);
}

.interview-report-section ul {
  padding-left: 1.2rem;
}

.interview-report-decision {
  display: inline-block;
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  border: 1px solid var(--border);
  background: var(--surface);
}

/* ---------- Admin ---------- */

.admin-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
  align-items: flex-end;
}

.admin-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.5rem;
}

.admin-period {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.82rem;
  color: var(--muted);
  font-weight: 500;
}

.admin-period select {
  padding: 0.4rem 0.5rem;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.85rem;
  margin-bottom: 1.75rem;
}

.metric-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.95rem 1.05rem;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.metric-label {
  font-size: 0.76rem;
  color: var(--muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 0.45rem;
}

.metric-value {
  font-size: 1.6rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.admin-section-title {
  margin: 1.5rem 0 0.75rem;
  font-size: 0.98rem;
  font-weight: 600;
}

.admin-table {
  width: 100%;
  font-size: 0.86rem;
}

.admin-generated {
  margin: 0 0 1rem;
}

.status-pill {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 600;
  border: 1px solid transparent;
}

.status-active {
  color: var(--accent-dim);
  background: color-mix(in srgb, var(--accent) 14%, transparent);
}

.status-paused {
  color: var(--muted);
  background: color-mix(in srgb, var(--muted) 14%, transparent);
}

.status-completed {
  color: var(--ok);
  background: var(--ok-tint);
}

/* ---------- Profile ---------- */

.profile-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin: 1.1rem 0 1.4rem;
}

.profile-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 0.85rem;
  margin-bottom: 1.4rem;
}

.profile-stat-link {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
  padding: 0.95rem 1.1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raised);
  box-shadow: var(--shadow-sm);
  color: inherit;
  font: inherit;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.profile-stat-link:hover,
.profile-stat-link.is-active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 35%, transparent);
}

.profile-stat-value {
  font-size: 1.85rem;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.01em;
  color: var(--accent-dim);
}

.profile-stat-label {
  font-size: 0.86rem;
  color: var(--muted);
}

.app-picker-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: 0.85rem;
  margin: 1rem 0 1.25rem;
}

.app-picker-tile {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  padding: 1rem 1.1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raised);
  box-shadow: var(--shadow-sm);
  color: inherit;
  font: inherit;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.app-picker-tile:hover {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 35%, transparent);
}

.app-picker-tile-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--accent-dim);
}

.app-picker-tile-desc {
  font-size: 0.88rem;
  color: var(--muted);
}

.app-picker-update-link {
  margin: 0;
}

.profile-interviews-wrap,
.profile-resumes,
.profile-interview-settings {
  margin-top: 1.4rem;
}

.profile-interviews-wrap h3,
.profile-resumes h3,
.profile-interview-settings h3 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  font-weight: 600;
}

.profile-settings-form {
  max-width: 22rem;
}

.profile-settings-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.profile-max-questions-effective {
  margin: 0.35rem 0 0;
}

.profile-ideal-answers-setting {
  margin-top: 1.1rem;
  max-width: 36rem;
}

.profile-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-weight: 500;
  cursor: pointer;
}

.profile-toggle input {
  margin-top: 0.2rem;
}

.ideal-answer-item {
  margin: 0.75rem 0 0;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-raised);
}

.ideal-answer-item h5 {
  margin: 0 0 0.35rem;
  font-size: 0.92rem;
}

.ideal-answer-item p {
  margin: 0.35rem 0 0;
  font-size: 0.88rem;
}

.ideal-answer-sources {
  margin: 0.5rem 0 0;
  padding-left: 1.1rem;
  font-size: 0.85rem;
}

.ideal-answer-sources a {
  word-break: break-all;
}

.report-download-link {
  white-space: nowrap;
}

.profile-interviews-report-col {
  width: 4.5rem;
  text-align: center;
  vertical-align: middle;
}

.download-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.2rem;
  margin: 0 auto;
  border: none;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--accent);
  cursor: pointer;
  line-height: 0;
}

.download-icon-btn:hover,
.download-icon-btn:focus-visible {
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  outline: none;
}

.download-icon-btn svg {
  width: 1.25rem;
  height: 1.25rem;
  display: block;
}

.profile-interviews-table.profile-interviews-paused .profile-interviews-report-col {
  display: none;
}

.profile-resumes .hint {
  margin-top: 0;
}

.profile-resume-empty {
  margin: 0.5rem 0 0;
}

/* ---------- Footer / utility ---------- */

.site-footer {
  text-align: center;
  padding: 1.5rem 1rem;
  font-size: 0.78rem;
  color: var(--muted);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  align-items: center;
}

.site-footer .footer-link {
  color: var(--accent);
  text-decoration: none;
  font-size: 0.85rem;
}

.site-footer .footer-link:hover {
  text-decoration: underline;
}

.site-footer code {
  font-size: 0.76rem;
}

.is-hidden[hidden] {
  display: none !important;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

/* ---------- Interview Trap Drills (app/trap_drills/frontend) ---------- */

.role-banner-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
}

.role-banner-info {
  font-size: 1rem;
}

.role-banner-label {
  color: var(--muted);
  margin-right: 0.35rem;
}

#role-banner-current {
  font-weight: 700;
  color: var(--accent-dim);
}

.role-banner-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.role-banner-controls select {
  padding: 0.4rem 0.5rem;
}

.trap-drills-nav {
  margin-bottom: 0;
}

.review-category {
  margin: 0 0 0.35rem;
  color: var(--muted);
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.review-prompt {
  margin: 0 0 0.85rem;
  font-size: 1.05rem;
  font-weight: 600;
}

.review-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 0.75rem;
}

.review-reveal {
  margin-top: 1rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--border);
}

.review-reveal p {
  margin: 0 0 0.5rem;
}

.review-reveal-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.role-picker-prompt {
  padding: 0.5rem 0;
}

.weak-category-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--danger-tint);
  color: var(--danger);
  font-size: 0.78rem;
  font-weight: 600;
  white-space: nowrap;
}
```

**Why a full-file replacement instead of targeted edits:** nearly every color value in the file changes (dark theme → light "slate" theme), so a line-by-line diff would be noisier than just replacing the file. Every selector from the current file is still present under the same name — confirmed by diffing the selector list between old and new before writing this — so no HTML or JS elsewhere in the repo needs to change.

### Edit 6 — add the Inter font, one line in each HTML file's `<head>`

The new stylesheet's `--font` variable asks for `"Inter"`, which isn't a system font — it needs to be loaded from Google Fonts or it'll silently fall back to the system font (harmless, but you won't get the look from the preview).

In **`app/real_interview/frontend/index.html`**, **`app/real_interview/frontend/admin.html`**, and **`app/real_interview/frontend/feedback.html`**, find this line in each file's `<head>`:

```html
    <link rel="stylesheet" href="/styles.css" />
```

Replace with (adds the font link right before your existing stylesheet link, in all three files):

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    />
    <link rel="stylesheet" href="/styles.css" />
```

### How to verify Part C after applying

1. Load `/` (main app), `/admin` (admin dashboard, assuming your admin route serves `admin.html`), and the feedback page, and confirm all three now show the light slate background, white cards with a subtle shadow, and Inter-rendered text (check DevTools' computed font-family on `body` if you want to confirm the font actually loaded rather than falling back).
2. Click through the main app's tabs (sign up / log in on the auth card) and confirm the new pill-style segmented control still switches panels correctly — this exercises `.tab` / `.tab.is-active` / `.tab-panel.is-hidden`, which `app.js` toggles via class names that didn't change.
3. Sign in and check the profile page: stat tiles, the interviews/practice-sessions tables, and the resumes table all render with the new card/table styling and remain clickable (`profile-stat-link` buttons still trigger `app.js` handlers).
4. Run or revisit a completed interview and confirm the chat bubbles render with the new asymmetric corners (user bubbles on the right in the accent color, assistant bubbles on the left), and that the interview report section still displays correctly.
5. Open the admin dashboard and confirm the metrics grid, status pills (`status-active` / `status-paused` / `status-completed`), and tables pick up the new look.
6. Open a Trap Drills screen (if you have one handy) and do a quick visual sanity check — it shares this stylesheet, and none of its selectors (`role-banner-*`, `review-*`, `weak-category-badge`) were removed, but it's worth a glance since it wasn't the primary target of this redesign.
7. Resize the browser narrow (mobile width) and confirm cards, tables (via `.table-wrap` horizontal scroll), and the chat input still lay out reasonably — no selector widths were hardcoded to large fixed pixel values, but it's worth a quick check since this wasn't explicitly tested at narrow widths.

### Suggested commit message for Part C

```
Redesign frontend with a professional "Slate" light theme

- styles.css: full rewrite of color tokens, spacing, and component
  styling (cards, tabs, buttons, tables, status pills, chat bubbles,
  admin metrics, profile tiles) to a light, neutral slate palette with
  elevation/shadows and the Inter typeface. Every existing selector is
  preserved under the same name, so no HTML/JS changes were needed and
  trap_drills/frontend (which shares this stylesheet) is unaffected.
- index.html, admin.html, feedback.html: add the Google Fonts Inter
  <link> the new stylesheet's --font variable depends on.
```
