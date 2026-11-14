"""Find LinkedIn job postings for a role via Tavily, and read a posting's description.

Cost model (Tavily credits):
- One search call per user search (1 credit). The same call returns each page's text,
  so live postings come back with their job description attached and prep needs no
  further Tavily call — the browser sends that text back when the user starts prep.
- Expired postings are kept (the role is still good practice) but their description is
  gone; prep approximates one from the title/company/location instead (LLM only).
- Only when a posting's text was not returned (Tavily sometimes returns none) does prep
  fetch it once via extract (about 1 credit).
"""

import os
import re
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

from app.real_interview import logger
from app.real_interview.backend.tools.tavily_search import _tavily_client

MAX_ROLE_CHARS = 120
MAX_LOCATION_CHARS = 80
MAX_DESCRIPTION_CHARS = 12000

STATUS_LIVE = "live"  # job description available
STATUS_EXPIRED = "expired"  # page now redirects to a LinkedIn search page; no description
STATUS_UNKNOWN = "unknown"  # Tavily returned no page text; prep will fetch it once

# Individual postings live under /jobs/view/<slug>-<numeric id>; everything else under
# /jobs/ is a listing page ("10,000+ open roles") with no single job description.
_JOB_VIEW_PATH = re.compile(r"^/jobs/view/(?:(?P<slug>[^/]*?)-)?(?P<job_id>\d{6,})/?$")
_TITLE_SUFFIXES = re.compile(
    r"\s*(\|\s*LinkedIn(\s+Jobs)?|-\s*Jobs\s*-\s*LinkedIn|-\s*LinkedIn|-\s*Jobs)\s*$", re.IGNORECASE
)
_LOCATION_SEP = re.compile(r"\s+[·–—]\s+")
_ROMAN_NUMERALS = {"ii", "iii", "iv", "vi", "vii"}

# Present on every live posting's criteria block; absent when an expired posting redirects
# to a LinkedIn search page.
_LIVE_POSTING_MARKERS = ("Seniority level", "Employment type")
_CLOSED_MARKER = "No longer accepting applications"
# Sections after the job description on LinkedIn's public page (related listings, nav).
_DESCRIPTION_END_MARKERS = ("Similar jobs", "People also viewed", "Similar Searches", "Explore collaborative articles")
_MIN_DESCRIPTION_CHARS = 400


class LinkedInJobFetchError(Exception):
    """The posting could not be read (expired, removed, or empty)."""


def _clean_job_url(url: str) -> Dict[str, str] | None:
    """Return {'url', 'job_id', 'slug'} for a LinkedIn single-posting URL, else None."""
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        return None
    match = _JOB_VIEW_PATH.match(parsed.path)
    if not match:
        return None
    path = parsed.path.rstrip("/")
    return {
        "url": f"https://www.linkedin.com{path}",
        "job_id": match.group("job_id"),
        "slug": unquote(match.group("slug") or ""),
    }


def is_linkedin_job_url(url: str) -> bool:
    return _clean_job_url(url) is not None


def _split_title(title: str, slug: str) -> Dict[str, str]:
    """
    Parse 'Role at Company · Location | LinkedIn Jobs'. Falls back to the URL slug
    ('role-words-at-company-words') when the page title is missing or generic.
    """
    text = _TITLE_SUFFIXES.sub("", (title or "").strip())
    location = ""
    parts = _LOCATION_SEP.split(text, maxsplit=1)
    if len(parts) == 2:
        text, location = parts[0].strip(), parts[1].strip()

    role, company = "", ""
    if " at " in text:
        role, company = (s.strip() for s in text.rsplit(" at ", 1))
    elif slug and "-at-" in slug:
        role_slug, company_slug = slug.rsplit("-at-", 1)
        role = " ".join(
            w.upper() if w.lower() in _ROMAN_NUMERALS else w.capitalize()
            for w in role_slug.replace("-", " ").split()
        )
        company = company_slug.replace("-", " ").strip().title()
    else:
        role = text
    return {"title": role, "company": company, "location": location}


def _markdown_to_text(raw: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", raw or "")  # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> label
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _description_from_page(raw: str) -> Dict[str, Any]:
    """
    Classify a posting page's text and pull out the job-ad portion.
    Returns {'status', 'closed', 'description'}.
    """
    text = _markdown_to_text(raw)
    if not text:
        return {"status": STATUS_UNKNOWN, "closed": False, "description": ""}
    if not any(m in text for m in _LIVE_POSTING_MARKERS):
        return {"status": STATUS_EXPIRED, "closed": False, "description": ""}
    cut = min((i for i in (text.find(m) for m in _DESCRIPTION_END_MARKERS) if i > 0), default=len(text))
    description = text[:cut].strip()[:MAX_DESCRIPTION_CHARS]
    if len(description) < _MIN_DESCRIPTION_CHARS:
        return {"status": STATUS_UNKNOWN, "closed": False, "description": ""}
    return {"status": STATUS_LIVE, "closed": _CLOSED_MARKER in text, "description": description}


def search_linkedin_jobs(role: str, location: str = "") -> List[Dict[str, Any]]:
    """
    Search recent LinkedIn postings for a role in a single Tavily call. Returns individual
    postings only (listing pages are dropped), deduplicated by LinkedIn job id, live
    postings first. Each has a status and, when live, the job description text.
    """
    role = (role or "").strip()[:MAX_ROLE_CHARS]
    location = (location or "").strip()[:MAX_LOCATION_CHARS]
    if not role:
        raise ValueError("role is required")

    max_results = int(os.getenv("LINKEDIN_JOB_SEARCH_MAX_RESULTS", "20").strip() or "20")
    query = f"{role} job posting" + (f" in {location}" if location else "")
    logger.info("[linkedin_job_search] query=%r", query)

    response = _tavily_client().search(
        query=query,
        include_domains=["linkedin.com/jobs/view"],
        max_results=max(1, min(max_results, 20)),
        time_range="month",
        include_raw_content="markdown",
    )
    results = response.get("results") if isinstance(response, dict) else []

    jobs: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in results or []:
        if not isinstance(item, dict):
            continue
        cleaned = _clean_job_url(item.get("url") or "")
        if not cleaned or cleaned["job_id"] in seen:
            continue
        seen.add(cleaned["job_id"])
        fields = _split_title(item.get("title") or "", cleaned["slug"])
        if not fields["title"]:
            continue
        page = _description_from_page(item.get("raw_content") or "")
        jobs.append({"job_id": cleaned["job_id"], "url": cleaned["url"], **fields, **page})

    order = {STATUS_LIVE: 0, STATUS_UNKNOWN: 1, STATUS_EXPIRED: 2}
    jobs.sort(key=lambda j: order[j["status"]])  # stable: keeps relevance order within a group
    counts = {s: sum(1 for j in jobs if j["status"] == s) for s in order}
    logger.info("[linkedin_job_search] %d postings from %d results %s", len(jobs), len(results or []), counts)
    return jobs


def fetch_linkedin_job_text(url: str) -> str:
    """
    Read a LinkedIn posting through Tavily extract (about 1 credit) and return the job-ad
    text. Used only when the search did not return the page text.
    """
    cleaned = _clean_job_url(url)
    if not cleaned:
        raise ValueError("not a LinkedIn job posting URL")

    try:
        response = _tavily_client().extract(urls=[cleaned["url"]])
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise LinkedInJobFetchError(f"extract failed: {exc}") from exc

    raw = ""
    for item in (response.get("results") if isinstance(response, dict) else None) or []:
        if isinstance(item, dict) and item.get("raw_content"):
            raw = item["raw_content"]
            break
    page = _description_from_page(raw)
    if page["status"] != STATUS_LIVE:
        raise LinkedInJobFetchError(f"posting not readable (status={page['status']})")
    return page["description"]
