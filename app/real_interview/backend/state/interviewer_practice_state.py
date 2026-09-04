from typing import Annotated, Any, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InterviewerPracticeState(TypedDict, total=False):
    """LangGraph workflow state for the interviewer-practice module."""

    customer_id: str
    resume_id: str
    job_application_id: str
    session_id: str
    practice_record_id: str

    parsed_data: dict[str, Any]
    # Deliberately not "job_role": maybe_summarize_node's question-bank extraction
    # (nodes/interview_nodes.py:_update_question_bank_from_messages) no-ops when
    # job_role is falsy, so leaving that key unset keeps practice transcripts out
    # of the candidate-side question bank.
    target_role: str
    job_description: str

    running_summary: str
    summary_snapshots: List[str]
    last_summarized_message_count: int
    force_summarize: bool

    messages: Annotated[List[BaseMessage], add_messages]

    question_count: int
    max_questions_soft_cap: int
    session_complete: bool

    # Same shape as InterviewPipelineState's field — reused CandidatePostInterviewFeedback.
    candidate_post_interview_feedback: dict[str, Any]

    error: Optional[str]
    step: str
