"""Extract interviewer question / candidate answer pairs from stored chat messages."""

import re
from typing import Any, Dict, List

from app.real_interview import logger
from app.real_interview.backend.services.interview_closing import candidate_requested_clarification
from app.real_interview.backend.services.question_bank import extract_question_from_message

_SKIP_PHRASES = (
    "do you have any questions",
    "before we wrap up",
    "thank you for your time",
    "that concludes our interview",
    "we'll share feedback with you",
)

_INTERVIEWER_PREFIX = re.compile(r"^\[(I\d+)\]:\s*", re.IGNORECASE)


def _is_skippable_assistant(content: str) -> bool:
    lower = (content or "").strip().lower()
    if not lower:
        return True
    return any(phrase in lower for phrase in _SKIP_PHRASES)


def _interviewer_label(content: str) -> str:
    match = _INTERVIEWER_PREFIX.match((content or "").strip())
    return match.group(1).upper() if match else ""


def _is_technical_interviewer_message(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    if not _INTERVIEWER_PREFIX.match(text):
        return False
    if _is_skippable_assistant(text):
        return False
    question = extract_question_from_message(text)
    if not question:
        return False
    if "?" not in question and len(question) < 25:
        return False
    return True


def extract_interview_qa_pairs(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Pair each technical interviewer question with the candidate's next reply.

    The panel asks one question per turn, so each answer is paired with the most
    recent pending interviewer message. At the opening a co-panelist's intro may
    precede the lead's question; that intro is dropped rather than paired.
    """
    pairs: List[Dict[str, str]] = []
    pending: List[Dict[str, str]] = []

    for message in messages or []:
        role = (message.get("role") or "").strip().lower()
        content = (message.get("content") or "").strip()
        if not content:
            continue

        if role == "assistant":
            if _is_technical_interviewer_message(content):
                pending.append(
                    {
                        "interviewer": _interviewer_label(content),
                        "question": extract_question_from_message(content),
                        "full_question": content,
                    }
                )
            elif _is_skippable_assistant(content):
                pending = []
            continue

        if role == "user" and pending:
            if candidate_requested_clarification(content):
                # Not an answer; the interviewer's rephrase that follows replaces the question.
                pending = []
                continue
            if sum(1 for item in pending if "?" in item["question"]) > 1:
                logger.warning(
                    "[interview_qa_extract] %d pending questions before one answer "
                    "(expected 1) — check panel pacing for a regression.",
                    len(pending),
                )
            item = pending[-1]
            pairs.append(
                {
                    "interviewer": item["interviewer"],
                    "question": item["question"],
                    "candidate_answer": content,
                }
            )
            pending = []

    return pairs
