"""
One-time (idempotent) seed script that creates a demo account with one resume
per role, so demos/screenshots don't require uploading files by hand.

Run with:
    python -m app.real_interview.backend.scripts.seed_demo_user

Safe to re-run: reuses the demo account if it already exists and skips any
resume whose filename is already on the account.
"""
import os
from typing import Dict, List

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.real_interview import logger
from app.real_interview.backend.auth.email_utils import find_user_by_email
from app.real_interview.backend.services.pdfreader import resume_reader
from app.real_interview.backend.services.user_maintenance import sign_up_user
from app.real_interview.backend.utils.mongodb import get_mongodb_database

DEMO_EMAIL = "demo.candidate@realinterview.dev"
DEMO_PASSWORD = "DemoPass123!"

ROLE_RESUMES: List[Dict[str, str]] = [
    {
        "role": "Backend Engineering",
        "filename": "Alex_Chen_Backend_Engineer.pdf",
        "text": """Alex Chen
alex.chen@example.com | (555) 123-4567 | San Francisco, CA

SUMMARY
Backend engineer with 5 years building REST APIs and distributed systems in Python. Owns payment microservices handling 2M+ transactions/day.

SKILLS
Python, FastAPI, Flask, PostgreSQL, MongoDB, Redis, Docker, Kubernetes, AWS, Kafka, REST API design, system design

EXPERIENCE
Senior Backend Engineer, Acme Payments (2021-Present)
- Designed an idempotent payment charge API used across three client platforms
- Migrated a monolith to microservices, cutting p99 latency by 40 percent
- Led on-call rotation; wrote incident runbooks and postmortems

Backend Engineer, DataFlow Inc (2019-2021)
- Built ETL pipelines processing 10M records per day with Kafka and Spark
- Implemented a rate-limiting and caching layer with Redis

EDUCATION
B.S. Computer Science, University of California, Davis (2019)
""",
    },
    {
        "role": "Frontend Engineering",
        "filename": "Priya_Nair_Frontend_Engineer.pdf",
        "text": """Priya Nair
priya.nair@example.com | (555) 234-5678 | Austin, TX

SUMMARY
Frontend engineer with 4 years shipping accessible, performant React applications for consumer products.

SKILLS
JavaScript, TypeScript, React, Redux, Next.js, CSS/Sass, Webpack, Jest, Cypress, WCAG accessibility, component architecture

EXPERIENCE
Frontend Engineer, ShopWave (2021-Present)
- Rebuilt the checkout flow in React, improving conversion by 12 percent
- Led an accessibility audit that brought the app to WCAG 2.1 AA compliance
- Introduced a shared component library adopted by three product teams

UI Engineer, Bright Labs (2019-2021)
- Migrated a jQuery dashboard to React, reducing bundle size by 35 percent
- Set up Cypress end-to-end tests, cutting regression bugs in production

EDUCATION
B.S. Computer Science, University of Texas at Austin (2019)
""",
    },
    {
        "role": "Data Science / ML",
        "filename": "Jordan_Lee_Data_Scientist.pdf",
        "text": """Jordan Lee
jordan.lee@example.com | (555) 345-6789 | Seattle, WA

SUMMARY
Data scientist with 5 years building and deploying ML models for fraud detection and personalization.

SKILLS
Python, pandas, scikit-learn, PyTorch, SQL, feature engineering, A/B testing, model evaluation, Airflow, MLflow

EXPERIENCE
Data Scientist, Northwind Bank (2021-Present)
- Built a gradient-boosted fraud detection model, reducing false positives by 22 percent
- Designed an experiment framework for offline/online metric parity checks
- Audited training data for leakage and demographic bias before each release

Data Analyst, RetailMetrics (2019-2021)
- Built churn-prediction models used to target retention campaigns
- Automated weekly reporting pipelines with Airflow, saving 10 hours per week

EDUCATION
M.S. Statistics, University of Washington (2019)
""",
    },
    {
        "role": "DevOps / SRE",
        "filename": "Sam_Rivera_DevOps_Engineer.pdf",
        "text": """Sam Rivera
sam.rivera@example.com | (555) 456-7890 | Denver, CO

SUMMARY
DevOps/SRE engineer with 6 years running production infrastructure and leading incident response for high-traffic services.

SKILLS
Kubernetes, Terraform, AWS, Docker, Prometheus, Grafana, CI/CD, Ansible, on-call incident response, capacity planning

EXPERIENCE
Site Reliability Engineer, CloudPeak (2020-Present)
- Owned Kubernetes platform serving 200+ microservices across three regions
- Cut mean time to recovery by 50 percent with improved alerting and runbooks
- Introduced canary deployments, reducing failed-release incidents

DevOps Engineer, Vertex Systems (2018-2020)
- Migrated infrastructure to Terraform, eliminating manual provisioning
- Built CI/CD pipelines used by every engineering team

EDUCATION
B.S. Computer Engineering, Colorado State University (2018)
""",
    },
    {
        "role": "Product Management",
        "filename": "Morgan_Blake_Product_Manager.pdf",
        "text": """Morgan Blake
morgan.blake@example.com | (555) 567-8901 | New York, NY

SUMMARY
Product manager with 6 years leading roadmaps for B2B SaaS products, from discovery through launch.

SKILLS
Roadmapping, stakeholder management, prioritization frameworks, user research, SQL, A/B testing, agile ceremonies

EXPERIENCE
Senior Product Manager, LedgerWorks (2021-Present)
- Owned the billing product line roadmap, growing net revenue retention by 15 percent
- Ran quarterly prioritization across engineering, design, and sales stakeholders
- Defined success metrics and led A/B tests for a new onboarding flow

Product Manager, Hearth Software (2018-2021)
- Launched a self-serve pricing tier, adding 20 percent of new signups
- Facilitated sprint planning and backlog grooming for two scrum teams

EDUCATION
B.A. Economics, Columbia University (2018)
""",
    },
    {
        "role": "Agile / Scrum",
        "filename": "Taylor_Nguyen_Scrum_Master.pdf",
        "text": """Taylor Nguyen
taylor.nguyen@example.com | (555) 678-9012 | Chicago, IL

SUMMARY
Certified Scrum Master with 5 years coaching cross-functional teams through Scrum and SAFe delivery.

SKILLS
Scrum, Kanban, SAFe, sprint planning, backlog refinement, velocity tracking, stakeholder facilitation, Jira, Confluence

EXPERIENCE
Senior Scrum Master, Ironclad Systems (2021-Present)
- Coached three scrum teams (24 engineers) through a transition to SAFe
- Facilitated PI planning and removed cross-team dependencies blocking delivery
- Improved sprint predictability, cutting mid-sprint scope changes by 30 percent

Scrum Master, Beacon Software (2019-2021)
- Ran daily standups, retros, and sprint reviews for a 7-person product team
- Introduced velocity and burndown tracking to improve estimation accuracy

CERTIFICATIONS
Certified Scrum Master (CSM), SAFe Scrum Master (SSM)

EDUCATION
B.S. Business Administration, DePaul University (2018)
""",
    },
]


def _build_resume_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in text.split("\n"):
        if line.strip():
            pdf.multi_cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.ln(6)
    return bytes(pdf.output())


def _get_or_create_demo_user() -> str:
    result = sign_up_user(DEMO_EMAIL, DEMO_PASSWORD, DEMO_PASSWORD)
    if result["status_code"] == 201:
        logger.info("[seed_demo_user] created demo user %s", DEMO_EMAIL)
        return result["user_id"]

    if result["status_code"] == 409:
        users_collection_name = os.getenv("MONGODB_COLLECTION_USERS", "authentications").strip()
        db_name = os.getenv("MONGODB_DB_NAME", "real_interview").strip()
        collection = get_mongodb_database(db_name)[users_collection_name]
        doc = find_user_by_email(collection, DEMO_EMAIL)
        if not doc:
            raise RuntimeError("demo user reported as existing but could not be found")
        logger.info("[seed_demo_user] reusing existing demo user %s", DEMO_EMAIL)
        return str(doc["_id"])

    raise RuntimeError(f"failed to create demo user: {result}")


def seed_demo_resumes() -> str:
    """Create (or reuse) the demo user and upload any missing role resumes. Returns the user_id."""
    user_id = _get_or_create_demo_user()

    reader = resume_reader()
    try:
        existing_filenames = {
            r["label"] for r in reader.list_resumes_for_user(user_id)
        }
        for item in ROLE_RESUMES:
            if item["filename"] in existing_filenames:
                print(f"Skipped (already present): {item['role']} - {item['filename']}")
                continue
            pdf_bytes = _build_resume_pdf(item["text"])
            reader.save_resume(
                user_id,
                pdf_bytes,
                item["filename"],
                content_type="application/pdf",
            )
            print(f"Uploaded resume: {item['role']} - {item['filename']}")
    finally:
        reader.close()

    return user_id


if __name__ == "__main__":
    demo_user_id = seed_demo_resumes()
    print("\nDemo account ready:")
    print(f"  email:    {DEMO_EMAIL}")
    print(f"  password: {DEMO_PASSWORD}")
    print(f"  user_id:  {demo_user_id}")
