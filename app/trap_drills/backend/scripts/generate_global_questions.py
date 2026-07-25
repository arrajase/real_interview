"""
Operator-triggered Phase 1 AI seeding (v2 §7.1, Module 10). Deliberately NOT
exposed via any HTTP route or App Picker UI — run manually to seed
pending-review global questions for a role/category. They stay invisible to
every due queue until approved via the Manage Questions screen (Module 7).

Usage:
    python -m app.trap_drills.backend.scripts.generate_global_questions \
        "Backend Engineering" "API Design" --count 5
"""

import argparse

from app.trap_drills.backend.config.roles_config import ROLE_NAMES
from app.trap_drills.backend.services.ai_seeding_service import generate_global_questions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate AI trick-question candidates for the global bank (pending review)."
    )
    parser.add_argument("role", help=f"One of: {', '.join(ROLE_NAMES)}")
    parser.add_argument("category", help="Category name within the role")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    result = generate_global_questions(args.role, args.category, count=args.count)
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(result.get("message", result))


if __name__ == "__main__":
    main()
