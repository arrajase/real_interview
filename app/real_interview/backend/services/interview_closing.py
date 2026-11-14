"""Interview closing phase: limits, detection, and panel messages."""

import re

from app.real_interview.backend.config.configuration import get_interview_limits_config

MIN_MAX_QUESTIONS_PER_INTERVIEWER = 4


def default_max_questions_per_interviewer() -> int:
    return int(get_interview_limits_config().get("max_questions_per_interviewer", 8))


def max_questions_per_interviewer() -> int:
    """App default from params.yaml (no user override)."""
    return default_max_questions_per_interviewer()


def question_limit_from_state(state: dict | None) -> int:
    if isinstance(state, dict):
        raw = state.get("max_questions_per_interviewer")
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    return default_max_questions_per_interviewer()


def max_candidate_qa_turns() -> int:
    return int(get_interview_limits_config().get("max_candidate_qa_turns", 2))


def _normalize_counts(raw: dict | list | None, panel_size: int) -> dict[int, int]:
    counts: dict[int, int] = {i: 0 for i in range(panel_size)}
    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < panel_size:
                counts[idx] = int(value or 0)
    elif isinstance(raw, list):
        for idx, value in enumerate(raw):
            if idx < panel_size:
                counts[idx] = int(value or 0)
    return counts


def all_panelists_at_question_limit(
    counts: dict[int, int] | dict | list | None,
    panel_size: int,
    *,
    limit: int | None = None,
) -> bool:
    if panel_size <= 0:
        return False
    normalized = _normalize_counts(counts, panel_size)
    effective_limit = limit if limit is not None else default_max_questions_per_interviewer()
    return all(normalized.get(i, 0) >= effective_limit for i in range(panel_size))


def increment_interviewer_question_count(
    counts: dict[int, int] | dict | list | None,
    panel_size: int,
    interviewer_index: int,
    *,
    delta: int = 1,
) -> dict[int, int]:
    normalized = _normalize_counts(counts, panel_size)
    if 0 <= interviewer_index < panel_size:
        normalized[interviewer_index] = normalized.get(interviewer_index, 0) + delta
    return normalized


def counts_for_state(counts: dict[int, int]) -> dict[str, int]:
    return {str(k): v for k, v in counts.items()}


def counts_from_state(raw: dict | list | None, panel_size: int) -> dict[int, int]:
    return _normalize_counts(raw, panel_size)


_NO_QUESTION_PATTERNS = (
    r"^\s*no\s*[.!]?\s*$",
    r"\bno questions?\b",
    r"\bnothing to ask\b",
    r"\bdon'?t have any questions?\b",
    r"\bdo not have any questions?\b",
    r"\bthat'?s all\b",
    r"\bi'?m good\b",
    r"\ball good\b",
    r"\bno,?\s*thank(s| you)\b",
)


_CLARIFY_PATTERNS = (
    r"\b(re-?phrase|re-?frame|re-?word|repeat|restate)\b",
    r"\bsay (that|it) again\b",
    r"\bcome again\b",
    r"\bpardon\b",
    r"\bwhat do you mean\b",
    r"\bwhat (exactly )?are you asking\b",
    r"\b(did ?n'?t|do ?n'?t|did not|do not) (understand|get|follow)\b",
    r"\bnot sure what you(\'re| are) asking\b",
    r"\b(clarify|explain) (the|your|that) question\b",
    r"\bcan you clarify\b",
)

# Clarification requests are short; longer messages that merely contain "clarify"
# or "repeat" are treated as real answers.
_CLARIFY_MAX_WORDS = 20


def candidate_requested_clarification(text: str) -> bool:
    """True when the candidate asks the interviewer to repeat/rephrase/clarify the last question."""
    raw = (text or "").strip()
    if not raw or len(raw.split()) > _CLARIFY_MAX_WORDS:
        return False
    lowered = raw.lower()
    return any(re.search(pattern, lowered) for pattern in _CLARIFY_PATTERNS)


def candidate_declined_questions(text: str) -> bool:
    """True when the candidate indicates they have no questions for the panel."""
    raw = (text or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if "?" in raw and len(raw) > 15:
        if not re.search(r"^\s*no\s*\?", lowered):
            return False
    for pattern in _NO_QUESTION_PATTERNS:
        if re.search(pattern, lowered):
            return True
    return False


def candidate_asked_question(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or candidate_declined_questions(raw):
        return False
    if "?" in raw:
        return True
    lowered = raw.lower()
    starters = ("what ", "how ", "why ", "when ", "where ", "who ", "can ", "could ", "is ", "are ", "do ", "does ")
    return any(lowered.startswith(s) for s in starters)


def ask_candidate_questions_message(interviewer_index: int) -> str:
    code = f"I{interviewer_index + 1}"
    return (
        f"[{code}]: We've covered a solid set of topics. Before we wrap up, "
        f"do you have any questions for us about the role, the team, or the interview process?"
    )


def panel_closing_message(interviewer_index: int = 0) -> str:
    code = f"I{interviewer_index + 1}"
    return (
        f"[{code}]: Thank you for your time today. That concludes our interview. "
        f"We'll share feedback with you shortly."
    )
