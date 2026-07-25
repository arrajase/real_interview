"""
Agile / Scrum starter question set (v2 §9/Module 9). Manually authored,
grounded in the Scrum Guide's accountabilities and events. Mapped onto the
five v1 categories: Role Boundaries, Estimation/Velocity, Prioritization
Under Pressure, SAFe/Scaling, Ceremony Ownership.
"""

ROLE_NAME = "Agile / Scrum"

AGILE_SCRUM_QUESTIONS = [
    # --- Role Boundaries ---
    {
        "category": "Role Boundaries",
        "prompt": "Who owns the Definition of Done?",
        "trap_answer": "The Scrum Master.",
        "correct_answer": "The Developers (the Scrum Team upholds it collectively).",
        "explanation": (
            "Per the Scrum Guide, if no organization-wide standard exists, the Developers "
            "must create a Definition of Done appropriate for the product. The Scrum Master "
            "does not own it."
        ),
    },
    {
        "category": "Role Boundaries",
        "prompt": "Who owns the Product Backlog?",
        "trap_answer": "The Scrum Master.",
        "correct_answer": "The Product Owner.",
        "explanation": "The Product Owner is accountable for the Product Backlog's content, availability, and ordering.",
    },
    {
        "category": "Role Boundaries",
        "prompt": "Who decides how many Product Backlog items to pull into a Sprint?",
        "trap_answer": "The Product Owner.",
        "correct_answer": "The Developers.",
        "explanation": (
            "Only the Developers can realistically assess their own capacity; the Product "
            "Owner can prioritize but not dictate how much work the team commits to."
        ),
    },
    {
        "category": "Role Boundaries",
        "prompt": "Who has the authority to cancel a Sprint?",
        "trap_answer": "The Scrum Master.",
        "correct_answer": "Only the Product Owner.",
        "explanation": "The Scrum Guide explicitly reserves Sprint-cancellation authority to the Product Owner.",
    },
    {
        "category": "Role Boundaries",
        "prompt": (
            "Who is responsible for managing the Scrum Team's process and removing "
            "impediments the team can't remove themselves?"
        ),
        "trap_answer": "The Product Owner.",
        "correct_answer": "The Scrum Master.",
        "explanation": (
            "The Scrum Master serves the team by coaching and removing impediments; the "
            "Product Owner focuses on value and the Product Backlog."
        ),
    },
    {
        "category": "Role Boundaries",
        "prompt": "Who writes the acceptance criteria for a Product Backlog item?",
        "trap_answer": "The Scrum Master.",
        "correct_answer": "Typically the Product Owner, often collaboratively with the Developers.",
        "explanation": (
            "Acceptance criteria clarify the Product Owner's intent for a backlog item; the "
            "Product Owner is accountable even when Developers help draft them."
        ),
    },
    {
        "category": "Role Boundaries",
        "prompt": "Who decides the Sprint Goal?",
        "trap_answer": "The Scrum Master sets it unilaterally.",
        "correct_answer": (
            "The whole Scrum Team crafts it together during Sprint Planning, with the "
            "Product Owner proposing the objective."
        ),
        "explanation": (
            "Sprint Planning is collaborative: the Product Owner proposes what could be "
            "done, the Developers determine how, and together they craft the Sprint Goal."
        ),
    },
    {
        "category": "Role Boundaries",
        "prompt": "Who is accountable for the overall quality of the Increment?",
        "trap_answer": "Only the Scrum Master, via enforcing process.",
        "correct_answer": "The entire Scrum Team.",
        "explanation": "The whole team is accountable for producing a high-quality, usable Increment each Sprint.",
    },
    {
        "category": "Role Boundaries",
        "prompt": "Who can add items to the Sprint Backlog once the Sprint has started?",
        "trap_answer": "Only the Product Owner.",
        "correct_answer": "The Developers, as they refine their plan during the Sprint.",
        "explanation": (
            "The Sprint Backlog is owned and managed by the Developers; they can add newly "
            "discovered work as needed."
        ),
    },
    # --- Estimation/Velocity ---
    {
        "category": "Estimation/Velocity",
        "prompt": "Is velocity a good metric for comparing two different Scrum Teams?",
        "trap_answer": "Yes, higher velocity means a more productive team.",
        "correct_answer": "No, velocity is team- and context-specific and not comparable across teams.",
        "explanation": (
            "Story points are relative to each team's own baseline; comparing velocity "
            "across teams just incentivizes point inflation."
        ),
    },
    {
        "category": "Estimation/Velocity",
        "prompt": "Should a team increase its per-Sprint story point commitment because management wants more output?",
        "trap_answer": "Yes, push the team to commit to more points.",
        "correct_answer": "No — capacity should be based on the team's empirical forecasting ability, not external pressure.",
        "explanation": "Artificially inflating commitment undermines Scrum's empirical process and sustainable pace.",
    },
    {
        "category": "Estimation/Velocity",
        "prompt": "What is velocity primarily used for?",
        "trap_answer": "Evaluating individual or team performance.",
        "correct_answer": "Forecasting how much work a team can likely complete in future Sprints.",
        "explanation": "Velocity is a planning and forecasting tool, not a performance metric.",
    },
    {
        "category": "Estimation/Velocity",
        "prompt": "If a team's velocity fluctuates significantly between Sprints, what should happen first?",
        "trap_answer": "Immediately lengthen the Sprint to compensate.",
        "correct_answer": "Inspect during the Retrospective why estimates or delivery are inconsistent.",
        "explanation": "Fluctuation is a signal to inspect estimation and delivery practices, not just adjust the calendar.",
    },
    {
        "category": "Estimation/Velocity",
        "prompt": "Should story points map to a fixed number of hours (e.g., 1 point = 4 hours)?",
        "trap_answer": "Yes, a fixed hour mapping makes points meaningful.",
        "correct_answer": "No, story points are a relative, unitless measure of effort, complexity, and uncertainty.",
        "explanation": "Tying points rigidly to hours defeats the purpose of relative estimation.",
    },
    {
        "category": "Estimation/Velocity",
        "prompt": "Who should estimate the Product Backlog items?",
        "trap_answer": "The Product Owner alone.",
        "correct_answer": "The Developers who will do the work.",
        "explanation": "The people doing the work are best positioned to estimate it; the Product Owner provides context, not the estimate itself.",
    },
    {
        "category": "Estimation/Velocity",
        "prompt": "Does a higher velocity always mean better team performance?",
        "trap_answer": "Yes.",
        "correct_answer": "No — velocity says nothing about the value delivered or the quality of the work.",
        "explanation": "A team can inflate points without delivering more actual value.",
    },
    {
        "category": "Estimation/Velocity",
        "prompt": "Should unfinished story points from a Sprint count toward that Sprint's velocity?",
        "trap_answer": "Yes, count partial credit for work in progress.",
        "correct_answer": "No — only fully \"Done\" work counts toward velocity.",
        "explanation": "Velocity should reflect only Done, releasable increments; partial work doesn't count.",
    },
    # --- Prioritization Under Pressure ---
    {
        "category": "Prioritization Under Pressure",
        "prompt": "If a senior executive demands a new feature mid-Sprint, who decides whether to add it?",
        "trap_answer": "The Scrum Master must comply immediately.",
        "correct_answer": (
            "Only the Product Owner can decide, and typically only by renegotiating scope "
            "with the Developers without abandoning the Sprint Goal."
        ),
        "explanation": (
            "The Product Owner owns backlog prioritization and can renegotiate the Sprint "
            "with the Developers, but the Sprint Goal is protected, not silently expanded."
        ),
    },
    {
        "category": "Prioritization Under Pressure",
        "prompt": "Can a stakeholder ask the Developers directly to reprioritize their work during the Sprint?",
        "trap_answer": "Yes, whoever is most senior can direct the Developers' work.",
        "correct_answer": "No — stakeholders raise priorities through the Product Owner, not directly to the Developers.",
        "explanation": "Bypassing the Product Owner undermines backlog integrity and Sprint focus.",
    },
    {
        "category": "Prioritization Under Pressure",
        "prompt": "When two urgent items compete for the top of the Product Backlog, who breaks the tie?",
        "trap_answer": "Whichever Developer feels strongest about it.",
        "correct_answer": "The Product Owner, based on value.",
        "explanation": "Backlog ordering is a Product Owner accountability, not decided by individual developer opinion.",
    },
    {
        "category": "Prioritization Under Pressure",
        "prompt": "If the team realizes mid-Sprint they can't meet the Sprint Goal, what should they do first?",
        "trap_answer": "Quietly work overtime to hide the risk.",
        "correct_answer": (
            "Communicate transparently with the Product Owner and consider what scope to "
            "negotiate to still meet the Sprint Goal."
        ),
        "explanation": "Transparency and inspect-adapt are core Scrum values; hiding problems violates them.",
    },
    {
        "category": "Prioritization Under Pressure",
        "prompt": "Under deadline pressure, is it acceptable to skip the Definition of Done to ship faster?",
        "trap_answer": "Yes, if leadership approves.",
        "correct_answer": "No — the Definition of Done is a quality contract for the Increment and shouldn't be compromised.",
        "explanation": "Lowering the DoD masks technical debt and undermines the guarantee of a \"Done\" Increment.",
    },
    {
        "category": "Prioritization Under Pressure",
        "prompt": "Should the Scrum Master shield the team from all outside interruptions, always, no exceptions?",
        "trap_answer": "Yes, block every external communication no matter what.",
        "correct_answer": (
            "The Scrum Master helps the team manage focus and removes impediments, but the "
            "goal is healthy stakeholder collaboration, not total isolation."
        ),
        "explanation": "Facilitating appropriate interaction is part of the role, not blanket isolation from stakeholders.",
    },
    {
        "category": "Prioritization Under Pressure",
        "prompt": "If an urgent production issue arises mid-Sprint, who decides whether to pull it into the current Sprint?",
        "trap_answer": "The on-call engineer alone, silently.",
        "correct_answer": "The Developers decide, ideally in consultation with the Product Owner about scope trade-offs.",
        "explanation": "This is a Sprint Backlog and capacity decision for the Developers, handled transparently with the Product Owner.",
    },
    {
        "category": "Prioritization Under Pressure",
        "prompt": "When facing pressure to add scope late in the Sprint, what's the correct Scrum response?",
        "trap_answer": "Just add it since the team probably has slack.",
        "correct_answer": "Protect the Sprint Goal; any added scope is negotiated and may require removing other items.",
        "explanation": "Uncontrolled scope creep threatens the Sprint Goal and the team's predictability.",
    },
    # --- SAFe/Scaling ---
    {
        "category": "SAFe/Scaling",
        "prompt": "In SAFe, who owns the Program Backlog?",
        "trap_answer": "The Scrum Master.",
        "correct_answer": "Product Management, at the Program/ART level.",
        "explanation": "In SAFe, Product Management owns the Program Backlog; Product Owners own team-level backlogs.",
    },
    {
        "category": "SAFe/Scaling",
        "prompt": "What is the primary purpose of PI Planning in SAFe?",
        "trap_answer": "To assign story points to Product Owners.",
        "correct_answer": (
            "To align multiple teams on an Agile Release Train around a shared vision and "
            "plan for the upcoming Program Increment."
        ),
        "explanation": "PI Planning is a cross-team alignment and planning event, not just backlog administration.",
    },
    {
        "category": "SAFe/Scaling",
        "prompt": "Who typically facilitates cross-team synchronization on a SAFe Agile Release Train?",
        "trap_answer": "A single Product Owner for the whole program.",
        "correct_answer": "The Release Train Engineer (RTE).",
        "explanation": "The RTE is SAFe's dedicated facilitation role for cross-team coordination, distinct from a team-level Scrum Master.",
    },
    {
        "category": "SAFe/Scaling",
        "prompt": "In SAFe, should a single Product Owner manage the backlogs for multiple teams?",
        "trap_answer": "Yes, one Product Owner across many teams is more efficient.",
        "correct_answer": "No — each team should have its own Product Owner accountable to that team's backlog.",
        "explanation": "Spreading one Product Owner across many teams dilutes prioritization quality and stakeholder responsiveness.",
    },
    {
        "category": "SAFe/Scaling",
        "prompt": "What happens at a SAFe System Demo?",
        "trap_answer": "Each team demos its own work separately with no integration.",
        "correct_answer": "All teams on an Agile Release Train integrate their work and demo it together.",
        "explanation": "The System Demo shows integrated, cross-team value rather than isolated team output.",
    },
    {
        "category": "SAFe/Scaling",
        "prompt": "Is \"Scrum of Scrums\" the same thing as SAFe's Agile Release Train structure?",
        "trap_answer": "Yes, they're identical frameworks.",
        "correct_answer": (
            "No — Scrum of Scrums is a lightweight scaling pattern; SAFe's ART is a more "
            "prescriptive framework with dedicated roles like the RTE and Product Management."
        ),
        "explanation": "They share the goal of cross-team coordination but differ significantly in structure and prescriptiveness.",
    },
    {
        "category": "SAFe/Scaling",
        "prompt": "Who is accountable for economic sequencing of features in SAFe (e.g., using WSJF)?",
        "trap_answer": "The Scrum Master.",
        "correct_answer": "Product Management, using techniques like Weighted Shortest Job First.",
        "explanation": "WSJF-based prioritization is a Product Management responsibility at the Program level.",
    },
    # --- Ceremony Ownership ---
    {
        "category": "Ceremony Ownership",
        "prompt": "Who leads or facilitates the Daily Scrum?",
        "trap_answer": "The Scrum Master always runs it.",
        "correct_answer": (
            "The Developers own and run it; the Scrum Master ensures the event happens but "
            "doesn't have to facilitate."
        ),
        "explanation": "The Scrum Guide states the Developers are responsible for conducting the Daily Scrum.",
    },
    {
        "category": "Ceremony Ownership",
        "prompt": "Who decides the action items coming out of a Sprint Retrospective?",
        "trap_answer": "The Scrum Master unilaterally assigns them.",
        "correct_answer": "The whole Scrum Team collaboratively identifies improvements and commits to them.",
        "explanation": "Retrospective outcomes are a team decision, not something imposed by the Scrum Master.",
    },
    {
        "category": "Ceremony Ownership",
        "prompt": "Is stakeholder attendance mandatory at the Daily Scrum?",
        "trap_answer": "Yes, stakeholders must attend and give input.",
        "correct_answer": "No — the Daily Scrum is for the Developers; others may observe but not participate.",
        "explanation": "The Daily Scrum is an internal planning event for the Developers.",
    },
    {
        "category": "Ceremony Ownership",
        "prompt": "Who is responsible for ensuring the Sprint Review actually gathers useful feedback?",
        "trap_answer": "Purely the Scrum Master's job to run the meeting.",
        "correct_answer": "The Product Owner, in collaboration with the whole Scrum Team and invited stakeholders.",
        "explanation": (
            "The Sprint Review is a working session where the Product Owner and team review "
            "outcomes together with stakeholders, not a status meeting run by the Scrum Master."
        ),
    },
    {
        "category": "Ceremony Ownership",
        "prompt": "Can Sprint Planning be skipped if the team feels they already know what to do?",
        "trap_answer": "Yes, skip it to save time under pressure.",
        "correct_answer": "No — Sprint Planning is a required Scrum event that establishes the Sprint Goal and initial plan.",
        "explanation": "Skipping it undermines shared understanding and the creation of the Sprint Goal.",
    },
    {
        "category": "Ceremony Ownership",
        "prompt": "Who decides how long each Scrum event is timeboxed for a given Sprint length?",
        "trap_answer": "Individual team members can extend events as needed on the fly.",
        "correct_answer": (
            "The Scrum Guide defines timebox maximums relative to Sprint length; the Scrum "
            "Master ensures events stay within them."
        ),
        "explanation": "Timeboxes are a Scrum Guide constraint; the Scrum Master's job is to help the team respect them, not personally extend them.",
    },
    {
        "category": "Ceremony Ownership",
        "prompt": "Can a Daily Scrum end before the full 15 minutes?",
        "trap_answer": "No, it must always use the full timebox.",
        "correct_answer": "Yes — the Developers can end it once they've finished synchronizing their plan for the day.",
        "explanation": "The 15-minute timebox is a maximum, not a mandatory duration.",
    },
    {
        "category": "Ceremony Ownership",
        "prompt": "Is the Sprint Review a formal status report to management with a fixed script?",
        "trap_answer": "Yes, it's a formal presentation for approval.",
        "correct_answer": "No — it's a collaborative working session to inspect the Increment and adapt the Product Backlog.",
        "explanation": "Framing it as a rigid approval gate misrepresents its purpose under the Scrum Guide.",
    },
]
