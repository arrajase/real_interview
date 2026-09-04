import uuid
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.real_interview import logger
from app.real_interview.backend.graphs.checkpointer import get_shared_checkpointer
from app.real_interview.backend.nodes.interviewer_practice_nodes import (
    avatar_opening_node,
    avatar_turn_node,
    feedback_node,
    load_practice_context_node,
    maybe_summarize_node,
    route_after_start,
    should_summarize,
)
from app.real_interview.backend.state.interviewer_practice_state import InterviewerPracticeState


def _build_practice_start_graph():
    graph = StateGraph(InterviewerPracticeState)
    graph.add_node("load_practice_context", load_practice_context_node)
    graph.add_node("avatar_opening", avatar_opening_node)

    graph.add_edge(START, "load_practice_context")
    graph.add_conditional_edges(
        "load_practice_context",
        route_after_start,
        {"continue": "avatar_opening", "end": END},
    )
    graph.add_edge("avatar_opening", END)
    return graph.compile(checkpointer=get_shared_checkpointer())


def _build_practice_chat_graph():
    graph = StateGraph(InterviewerPracticeState)
    graph.add_node("avatar_turn", avatar_turn_node)
    graph.add_node("summarize", maybe_summarize_node)

    graph.add_edge(START, "avatar_turn")
    graph.add_conditional_edges(
        "avatar_turn",
        should_summarize,
        {"summarize": "summarize", "skip_summarize": END},
    )
    graph.add_edge("summarize", END)
    return graph.compile(checkpointer=get_shared_checkpointer())


def _build_practice_feedback_graph():
    graph = StateGraph(InterviewerPracticeState)
    graph.add_node("summarize", maybe_summarize_node)
    graph.add_node("feedback", feedback_node)
    graph.add_edge(START, "summarize")
    graph.add_edge("summarize", "feedback")
    graph.add_edge("feedback", END)
    return graph.compile(checkpointer=get_shared_checkpointer())


@lru_cache(maxsize=1)
def get_practice_start_graph():
    logger.info("[interviewer_practice_graph] compile start graph")
    return _build_practice_start_graph()


@lru_cache(maxsize=1)
def get_practice_chat_graph():
    logger.info("[interviewer_practice_graph] compile chat graph")
    return _build_practice_chat_graph()


@lru_cache(maxsize=1)
def get_practice_feedback_graph():
    logger.info("[interviewer_practice_graph] compile feedback graph")
    return _build_practice_feedback_graph()


def make_practice_thread_id(customer_id: str, resume_id: str) -> str:
    return f"{customer_id}:{resume_id}:practice:{uuid.uuid4().hex[:10]}"
