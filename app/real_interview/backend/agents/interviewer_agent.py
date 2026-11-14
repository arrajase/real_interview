import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_first_impression, format_parsed_resume
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.tools.tavily_search import get_interviewer_tools

INTERVIEWER_PROMPTS = {
    "positive": (
        "You are a senior technical interviewer for the role of {candidate_role}, known for being "
        "encouraging without lowering the bar. Ground every question in a specific detail from the "
        "candidate's resume or stated experience — ask them to walk through a real project, name the "
        "metric or outcome, and explain their specific individual contribution versus the team's. "
        "When an answer is strong, go one level deeper (a trade-off they considered, an alternative "
        "approach, what they'd do differently now) instead of moving on; when an answer is weak or "
        "vague, give them one chance to clarify with a narrower or easier version of the same question "
        "before moving on — don't accept vagueness just because your tone is warm. Note what's "
        "genuinely strong and genuinely missing as you go and let it steer your next question; your "
        "warmth should shape your delivery, not your judgment. "
        "Never tell the candidate during the interview whether they would be selected — keep "
        "your assessment to yourself."
    ),
    "negative": (
        "You are a senior technical interviewer for the role of {candidate_role}, known for being "
        "rigorous and hard to impress — but your rigor comes from depth, not hostility. Never accept a "
        "surface-level answer: anchor every question in a specific resume detail, and when the "
        "candidate gives a plausible-sounding answer, push on it — ask for the actual metric, the "
        "alternative they didn't choose and why, or what broke when they tried it. If an answer is "
        "vague or sounds rehearsed, say so directly and ask them to be concrete. Your tone can be terse "
        "and skeptical, but never dismissive, sarcastic, or designed to unsettle rather than assess — a "
        "real tough interviewer is hard to satisfy with vague answers, not unpleasant to talk to. "
        "Never tell the candidate during the interview whether they would be selected — keep "
        "your assessment to yourself."
    ),
    "objective": (
        "You are a senior technical interviewer for the role of {candidate_role} who runs a "
        "structured, methodology-driven interview. Keep track of distinct competencies as the interview "
        "progresses — technical depth, problem-solving process (not just the final answer), "
        "communication clarity, and ownership/specificity of past work — and prioritize breadth "
        "across them when your question budget is tight rather than clustering on one. Prefer process "
        "questions over trivia: ask how they approached a problem, what alternatives they considered, "
        "how they'd validate a solution, and how they'd handle a constraint relevant to "
        "{candidate_role} (time, scale, a difficult stakeholder). Stay even-keeled regardless of "
        "answer quality — neither warmer nor harsher — so the signal comes from the questions, not "
        "your reaction. "
        "Never tell the candidate during the interview whether they would be selected — keep "
        "your assessment to yourself."
    ),
}


class InterviewerAgent:
    """Technical interviewer with optional Tavily search."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        logger.info("[InterviewerAgent] initialized")
        self._llm_wrapper = llm_wrapper or OpenAILLM()
        self._tools = get_interviewer_tools()
        self._tools_by_name = {t.name: t for t in self._tools}

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

    def _question_bank_context(self, seeds: List[Dict[str, Any]], interviewer_type: str) -> str:
        if not seeds:
            return (
                "\n\nNo curated question bank exists yet for this role and level. "
                "Generate appropriate questions from the resume, job description, and HR summary."
            )
        lines = []
        for i, item in enumerate(seeds, 1):
            text = (item.get("text") or "").strip()
            if not text:
                continue
            topic = (item.get("topic") or "").strip()
            suffix = f" (topic: {topic})" if topic else ""
            lines.append(f"{i}. {text}{suffix}")
        if not lines:
            return (
                "\n\nNo unused question-bank seeds remain; continue based on the conversation and resume."
            )
        return (
            "\n\nCurated question bank (prefer these; personalize; do not repeat questions already answered):\n"
            + "\n".join(lines)
        )

    def _summary_context(self, interview_summary: str) -> str:
        summary = (interview_summary or "").strip()
        if not summary:
            return ""
        return (
            "\n\nInterview progress summary (use as context; interview may have been paused and resumed):\n"
            + summary
        )

    def _panel_context(self, panel_plan: Dict[str, Any], interviewer_index: int) -> str:
        selected = panel_plan.get("selected_interviewers") or []
        if not selected:
            return ""
        roster = []
        for i, style in enumerate(selected):
            label = f"I{i + 1} ({style})"
            if i == interviewer_index:
                label += " — you"
            roster.append(label)
        return (
            "\n\nLive panel interview — all interviewers are in the room and hear every answer.\n"
            "Panel present: "
            + ", ".join(roster)
            + ".\n"
            "Ask one concise follow-up question grounded in what the candidate just said. "
            "Do not repeat questions another panelist already asked earlier in the interview."
        )

    def run_turn(
        self,
        *,
        interviewer_type: str,
        candidate_role: str,
        parsed_data: Dict[str, Any],
        first_impression: Dict[str, Any],
        messages: List[BaseMessage],
        interview_summary: str = "",
        question_bank_seeds: Optional[List[Dict[str, Any]]] = None,
        panel_plan: Optional[Dict[str, Any]] = None,
        interviewer_index: int = 0,
        turn_mode: str = "technical",
    ) -> AIMessage:
        logger.info(
            "[InterviewerAgent] run_turn type=%s index=%s mode=%s",
            interviewer_type,
            interviewer_index,
            turn_mode,
        )
        llm = self._llm_wrapper.get_llm_model().bind_tools(self._tools)
        max_tool_rounds = int(os.getenv("INTERVIEWER_MAX_TOOL_ROUNDS", "3").strip() or "3")

        panel_block = ""
        if panel_plan:
            panel_block = self._panel_context(panel_plan, interviewer_index)
        if turn_mode == "candidate_qa":
            panel_block += (
                "\n\nThe candidate is asking questions for the panel. Answer briefly and professionally "
                "about the role, team, or process. Do not ask a new technical interview question."
            )
        elif turn_mode == "clarification":
            panel_block += (
                "\n\nThe candidate asked you to repeat, rephrase, or clarify your last question. "
                "Restate that same question more simply — add a concrete example or narrow the scope if it "
                "helps — but do not change the topic, ask a different question, or comment on their request."
            )

        experience_level = ((panel_plan or {}).get("experience_level") or "").strip()
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
                    if turn_mode not in ("candidate_qa", "clarification")
                    else ""
                )
            )
        )
        convo: List[BaseMessage] = [system] + list(messages)

        for _ in range(max_tool_rounds):
            response = llm.invoke(convo)
            if not getattr(response, "tool_calls", None):
                return response if isinstance(response, AIMessage) else AIMessage(content=str(response.content))

            convo.append(response)
            for call in response.tool_calls:
                name = call.get("name") if isinstance(call, dict) else call["name"]
                args = call.get("args") if isinstance(call, dict) else call["args"]
                tool = self._tools_by_name.get(name)
                if tool:
                    try:
                        result = tool.invoke(args)
                    except Exception as exc:
                        result = f"Tool error: {exc}"
                else:
                    result = f"Unknown tool: {name}"
                convo.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=call.get("id") if isinstance(call, dict) else call["id"],
                    )
                )

        final = llm.invoke(convo)
        return final if isinstance(final, AIMessage) else AIMessage(content=str(final.content))

    def opening_message(
        self,
        *,
        interviewer_type: str,
        candidate_role: str,
        parsed_data: Dict[str, Any],
        first_impression: Dict[str, Any],
        interview_summary: str = "",
        question_bank_seeds: Optional[List[Dict[str, Any]]] = None,
        panel_plan: Optional[Dict[str, Any]] = None,
        interviewer_index: int = 0,
        is_lead: bool = True,
        prior_messages: Optional[List[BaseMessage]] = None,
    ) -> AIMessage:
        if is_lead:
            prompt_text = (
                "Start the live panel interview. Welcome the candidate, note that the full panel is present, "
                "introduce yourself briefly in character, then ask your first question. "
                "If a fellow panelist has already introduced themselves, do not repeat their introduction. "
                "Prefer an unused question-bank seed if available; otherwise base it on the resume and HR summary."
            )
        else:
            prompt_text = (
                "The live panel interview is starting. Briefly greet the candidate and introduce yourself "
                "in character — one or two sentences, no more. The lead panelist will speak right after you "
                "and ask the opening question, so do NOT ask a question of your own."
            )
        prompt = HumanMessage(content=prompt_text)
        convo = list(prior_messages or []) + [prompt]
        return self.run_turn(
            interviewer_type=interviewer_type,
            candidate_role=candidate_role,
            parsed_data=parsed_data,
            first_impression=first_impression,
            messages=convo,
            interview_summary=interview_summary,
            question_bank_seeds=question_bank_seeds,
            panel_plan=panel_plan,
            interviewer_index=interviewer_index,
        )
