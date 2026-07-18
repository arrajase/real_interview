"""
Fixed role/category/keyword config for Interview Trap Drills (v2 §5.1-§5.3).

This is a config list, not a hardcoded enum/schema: new roles or categories
can be added here without any Mongo schema migration (see
trap-drills-implementation-guardrails.md §3).
"""

from typing import Any, Dict, List, Optional

ROLES_CONFIG: List[Dict[str, Any]] = [
    {
        "name": "Agile / Scrum",
        "keywords": [
            "scrum", "agile coach", "scrum master", "product owner",
            "agile", "release train engineer", "safe agilist",
        ],
        "categories": [
            "Role Boundaries",
            "Estimation/Velocity",
            "Prioritization Under Pressure",
            "SAFe/Scaling",
            "Ceremony Ownership",
        ],
    },
    {
        "name": "Backend Engineering",
        "keywords": [
            "backend", "back-end", "back end", "server-side", "server side",
            "api engineer", "software engineer", "sde", "platform engineer",
        ],
        "categories": [
            "API Design",
            "Data Consistency",
            "Failure Handling",
            "Performance/Scaling",
            "Observability",
        ],
    },
    {
        "name": "Frontend Engineering",
        "keywords": [
            "frontend", "front-end", "front end", "ui engineer",
            "react developer", "web developer",
        ],
        "categories": [
            "Rendering/Performance",
            "State Management",
            "Accessibility",
            "Browser Compatibility",
            "Component Architecture",
        ],
    },
    {
        "name": "Data Science / ML",
        "keywords": [
            "data scientist", "machine learning", "ml engineer", "data science",
            "applied scientist", "ai engineer",
        ],
        "categories": [
            "Model Evaluation",
            "Data Leakage",
            "Feature Engineering",
            "Bias/Fairness",
            "Experiment Design",
        ],
    },
    {
        "name": "DevOps / SRE",
        "keywords": [
            "devops", "sre", "site reliability", "platform reliability",
            "infrastructure engineer", "cloud engineer",
        ],
        "categories": [
            "Incident Response",
            "Deployment Strategy",
            "Monitoring/Alerting",
            "Capacity Planning",
            "Access/Security",
        ],
    },
    {
        "name": "Product Management",
        "keywords": [
            "product manager", "product management", "pm ", "group product manager",
            "senior product manager",
        ],
        "categories": [
            "Prioritization",
            "Stakeholder Management",
            "Metrics/Success Criteria",
            "Roadmapping",
            "Scope Tradeoffs",
        ],
    },
]

ROLE_NAMES: List[str] = [role["name"] for role in ROLES_CONFIG]


def get_role_config(role_name: str) -> Optional[Dict[str, Any]]:
    for role in ROLES_CONFIG:
        if role["name"] == role_name:
            return role
    return None


def is_valid_role(role_name: str) -> bool:
    return role_name in ROLE_NAMES


def get_categories_for_role(role_name: str) -> List[str]:
    role = get_role_config(role_name)
    return list(role["categories"]) if role else []


def detect_role_from_text(job_role_text: str) -> Optional[str]:
    """Simple keyword match — never an LLM call (v2 §3, §5.2)."""
    text = (job_role_text or "").strip().lower()
    if not text:
        return None
    for role in ROLES_CONFIG:
        for keyword in role["keywords"]:
            if keyword in text:
                return role["name"]
    return None
