# Fixes: panel pacing + more realistic interviewer personas

Paste this into VS Code (or hand it to an AI coding assistant there) against the `real_interview` repo. Two separate fixes are bundled in this file:

- **Edits 1–3**: the panel asking two questions per turn, and the downstream report-pairing bug it causes.
- **Edit 4**: more realistic interviewer personas (question technique + evaluation rubric, not just tone) plus experience-level calibration.

These are unrelated concerns that happen to touch the same two agent files — commit them separately (suggested messages for each are at the bottom of their own section) rather than as one combined commit.

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
