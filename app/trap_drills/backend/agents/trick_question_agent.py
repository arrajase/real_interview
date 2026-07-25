"""
TrickQuestionAgent (v2 §7): AI-assisted question *content* generation only —
never used for role matching (that stays keyword-based, see config/roles_config.py).

Reuses the existing OpenAILLM wrapper and llm.with_structured_output(...)
pattern already used by FeedbackAgent, CandidateAvatarAgent, and
SummarizerAgent in app/real_interview — no new LLM client, no different
structured-output approach (guardrails §2).
"""

from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.real_interview import logger
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.trap_drills.backend.state.schemas import (
    PersonalizedTrickQuestionBatch,
    PersonalizedTrickQuestionItem,
    TrickQuestionBatch,
    TrickQuestionItem,
)

_SYSTEM_PROMPT = (
    "You write 'trick' interview questions that test precise role boundaries and judgment "
    "calls within a profession — not surface trivia or generic textbook questions. Each "
    "question needs: a plausible-but-wrong 'trap' answer (the common misconception a "
    "candidate might confidently give), the actual correct answer, and a clear explanation "
    "of why the trap is wrong and the correct answer is right. Be factually accurate — this "
    "content teaches real candidates preparing for real interviews, so never invent or guess "
    "when unsure of a fact."
)


class TrickQuestionAgent:
    """Phase 1 (global bank) and Phase 2 (personalized) question generation."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        self._llm_wrapper = llm_wrapper or OpenAILLM()
        logger.info("[TrickQuestionAgent] initialized")

    def generate_questions(self, *, role: str, category: str, count: int = 5) -> List[TrickQuestionItem]:
        """Phase 1: operator-triggered global bank generation for one role/category (v2 §7.1)."""
        logger.info("[TrickQuestionAgent] generate_questions role=%s category=%s count=%s", role, category, count)
        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(TrickQuestionBatch)

        system = SystemMessage(content=_SYSTEM_PROMPT)
        user = HumanMessage(
            content=(
                f"Role: {role}\n"
                f"Category: {category}\n\n"
                f"Generate {count} distinct trick questions for this role and category. "
                "Avoid generic questions already common in interview-prep lists; focus on "
                "specific, commonly-confused boundaries, ownership, or judgment calls someone "
                "in this role should get right under pressure."
            )
        )
        try:
            result: TrickQuestionBatch = structured.invoke([system, user])
            logger.info("[TrickQuestionAgent] produced %s question(s)", len(result.questions))
            return result.questions
        except Exception:
            logger.exception("[TrickQuestionAgent] generate_questions failed")
            return []

    def _format_qa_pairs(self, qa_pairs: List[Dict[str, str]]) -> str:
        lines: List[str] = []
        for idx, item in enumerate(qa_pairs, start=1):
            question = (item.get("question") or "").strip()
            answer = (item.get("candidate_answer") or "").strip()
            if not question:
                continue
            lines.append(f"{idx}. Interviewer asked: {question}")
            lines.append(f"   Candidate answered: {answer or '(no answer captured)'}")
        return "\n".join(lines) if lines else "(no Q&A pairs available)"

    def generate_personalized_questions(
        self,
        *,
        role: str,
        categories: List[str],
        qa_pairs: List[Dict[str, str]],
        feedback: Optional[Dict[str, Any]] = None,
        count: int = 5,
    ) -> List[PersonalizedTrickQuestionItem]:
        """
        Phase 2: personalized questions from one completed real_interview session
        (v2 §7.2) — private to the user who took that interview, never shown to
        anyone else (guardrails §4).
        """
        logger.info(
            "[TrickQuestionAgent] generate_personalized_questions role=%s qa_pairs=%s",
            role,
            len(qa_pairs),
        )
        if not qa_pairs:
            return []

        feedback = feedback or {}
        areas_to_improve = feedback.get("areas_to_improve") or []

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(PersonalizedTrickQuestionBatch)

        system = SystemMessage(
            content=(
                _SYSTEM_PROMPT
                + "\n\nThis batch is personalized: base it on a specific candidate's real "
                "interview transcript and feedback, targeting the areas they actually "
                "struggled with. Tag each question with the single category from the "
                "provided list it best fits."
            )
        )
        user = HumanMessage(
            content=(
                f"Role: {role}\n"
                f"Allowed categories (choose the closest match — copy one of these strings "
                f"EXACTLY, do not invent a new category name): {', '.join(categories) or '(none)'}\n\n"
                f"Areas to improve (from post-interview feedback): {areas_to_improve or '(none noted)'}\n\n"
                f"Interview Q&A transcript:\n{self._format_qa_pairs(qa_pairs)}\n\n"
                f"Generate up to {count} trick questions targeting this candidate's weak spots. "
                "Only generate questions clearly grounded in the transcript or feedback above."
            )
        )
        try:
            result: PersonalizedTrickQuestionBatch = structured.invoke([system, user])
            logger.info("[TrickQuestionAgent] produced %s personalized question(s)", len(result.questions))
            return result.questions
        except Exception:
            logger.exception("[TrickQuestionAgent] generate_personalized_questions failed")
            return []
