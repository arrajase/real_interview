import os
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.real_interview import logger
from app.real_interview.backend.llm.openaillm import OpenAILLM


class JobApplicationExtractionModel(BaseModel):
    """Structured job posting fields for storage and downstream agents."""

    job_role: str = Field(
        default="",
        description="Primary role or job title the candidate is applying for",
    )
    job_description: str = Field(
        default="",
        description=(
            "Agent-readable job description: clear sections (role, company if known, "
            "responsibilities, requirements, location, compensation if stated). Use plain text."
        ),
    )


class JobApplicationAgent:
    """Uses the same OpenAI stack as resume parsing to normalize job postings."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        logger.info("[JobApplicationAgent] init")
        self._llm_wrapper = llm_wrapper or OpenAILLM()

    def extract_from_text(
        self,
        raw_text: str,
        *,
        source: str = "description",
        application_link: Optional[str] = None,
    ) -> Dict[str, str]:
        logger.info("[JobApplicationAgent] extract_from_text source=%s", source)
        if not raw_text or not raw_text.strip():
            return {"job_role": "", "job_description": ""}

        max_chars = int(os.getenv("JOB_APPLICATION_MAX_CHARS", "16000").strip() or "16000")
        snippet = raw_text.strip()[:max_chars]
        if len(raw_text.strip()) > max_chars:
            snippet += "\n\n[... text truncated for parsing ...]"

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(JobApplicationExtractionModel)

        link_note = ""
        if application_link:
            link_note = f"\nThe posting was loaded from this URL: {application_link}\n"

        system = SystemMessage(
            content=(
                "You extract job application data from job posting text (web page text or user paste). "
                "Set job_role to the primary position title. "
                "Set job_description to a clean, agent-readable summary using labeled sections "
                "(Role, Company, Location, Responsibilities, Requirements, Nice-to-have, Compensation). "
                "Use only information present in the text. Do not invent employers or requirements."
            )
        )
        user = HumanMessage(
            content=(
                f"Source type: {source}.{link_note}\n"
                "Extract job_role and job_description from the following text.\n\n"
                f"{snippet}"
            )
        )

        try:
            parsed: JobApplicationExtractionModel = structured.invoke([system, user])
            data = parsed.model_dump()
            return {
                "job_role": (data.get("job_role") or "").strip(),
                "job_description": (data.get("job_description") or "").strip(),
            }
        except Exception:
            logger.exception("[JobApplicationAgent] LLM extraction failed")
            return {"job_role": "", "job_description": snippet[:8000]}

    def approximate_from_role(
        self,
        *,
        job_title: str,
        company: str = "",
        location: str = "",
    ) -> Dict[str, str]:
        """
        Draft a typical job description for interview practice when the real posting has
        expired. Only the title/company/location are known, so this describes the role in
        general terms and must not present invented company specifics as fact.
        """
        logger.info("[JobApplicationAgent] approximate_from_role title=%r", job_title)
        title = (job_title or "").strip()
        fallback = "\n".join(
            line
            for line in (
                f"Role: {title}",
                f"Company: {company.strip()}" if company and company.strip() else "",
                f"Location: {location.strip()}" if location and location.strip() else "",
            )
            if line
        )
        if not title:
            return {"job_role": "", "job_description": ""}

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(JobApplicationExtractionModel)
        system = SystemMessage(
            content=(
                "The original job posting has expired; only its title, company and location are known. "
                "Write a realistic, typical job description for this role to be used for interview practice. "
                "Set job_role to the title as given. Set job_description using labeled sections "
                "(Role, Company, Location, Responsibilities, Requirements, Nice-to-have). "
                "Base responsibilities and requirements on what this title and its seniority usually "
                "involve across the industry. Name the company only as the employer: do not state "
                "specific facts about it (products, teams, tech stack, benefits, compensation) as if "
                "they came from the posting. Plain text."
            )
        )
        user = HumanMessage(
            content=f"Title: {title}\nCompany: {company or 'unknown'}\nLocation: {location or 'unknown'}"
        )
        try:
            parsed: JobApplicationExtractionModel = structured.invoke([system, user])
            data = parsed.model_dump()
            return {
                "job_role": (data.get("job_role") or title).strip(),
                "job_description": (data.get("job_description") or fallback).strip(),
            }
        except Exception:
            logger.exception("[JobApplicationAgent] approximate_from_role failed")
            return {"job_role": title, "job_description": fallback}
