"""
Structured LLM output schemas for AI-assisted question seeding (v2 §7).
Mirrors the BankQuestionItem/QuestionBankExtract pair in
app/real_interview/backend/state/interview_schemas.py.
"""

from typing import List

from pydantic import BaseModel, Field


class TrickQuestionItem(BaseModel):
    """A single AI-generated candidate trick question (pending human review)."""

    prompt: str = Field(default="", description="The trick question text")
    trap_answer: str = Field(default="", description="The common, plausible-but-wrong answer")
    correct_answer: str = Field(default="", description="The correct answer")
    explanation: str = Field(default="", description="Why the trap answer is wrong and the correct one is right")


class TrickQuestionBatch(BaseModel):
    """TrickQuestionAgent output: a batch of candidate questions for one role/category."""

    questions: List[TrickQuestionItem] = Field(default_factory=list)


class PersonalizedTrickQuestionItem(TrickQuestionItem):
    """Phase 2 (v2 §7.2): also tags the category the LLM judged this question belongs to."""

    category: str = Field(default="", description="One of the role's known categories")


class PersonalizedTrickQuestionBatch(BaseModel):
    """TrickQuestionAgent Phase 2 output: personalized questions from one completed interview."""

    questions: List[PersonalizedTrickQuestionItem] = Field(default_factory=list)
