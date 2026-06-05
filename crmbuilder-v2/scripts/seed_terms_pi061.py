"""PI-061 — migrate the five glossary.md terms and seed the agent-system terms.

Posts to the live /terms API (X-Engagement: CRMBUILDER). The five existing
terms keep their glossary.md identifiers (TERM-001..005); the agent-system terms
are server-assigned (TERM-006+). All are system-scoped (shared across
engagements). Idempotent-ish: skips a term whose explicit identifier already
exists, and skips an agent term whose name already exists.

Run:  uv run python scripts/seed_terms_pi061.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
ENGAGEMENT = "CRMBUILDER"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-Engagement", ENGAGEMENT)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"_status": exc.code, "_body": exc.read().decode()}


# The five existing terms, transcribed from specifications/glossary.md v0.2.
EXISTING = [
    {
        "identifier": "TERM-001",
        "name": "Engagement",
        "definition": (
            "A defined unit of work in which the CRMBuilder process is applied "
            "to capture the complete definition of one product — a deployed, "
            "functional application — for one client organization. Each "
            "engagement is its own partition in V2's storage system, holding a "
            "single Charter, Status, and the full set of governance and "
            "methodology records produced during the engagement's lifecycle."
        ),
        "usage_scope": (
            "Used throughout the Master CRMBuilder PRD and supporting "
            "documentation when referring to a client's structured relationship "
            "with the CRMBuilder process. Also used as the partitioning concept "
            "in V2's storage system — each engagement has its own data isolation."
        ),
        "examples": (
            "- The CRMBUILDER engagement: the dogfood engagement in which "
            "CRMBuilder uses its own process to define itself.\n"
            "- The (future) CBM engagement: Cleveland Business Mentors using the "
            "process to define their CRM-shaped system."
        ),
        "distinguishing_notes": (
            "Not synonymous with Client (a client is the organization being "
            "served; an engagement is the specific application of the process to "
            "that client). Not the same as a Session (a session is one working "
            "interaction within an engagement). Not the same as a Project in the "
            "colloquial sense."
        ),
        "related_terms": "Client, Session, Phase, Charter, Status",
    },
    {
        "identifier": "TERM-002",
        "name": "Skill",
        "definition": (
            "A reusable knowledge file containing domain-specific guidance — "
            "typical entities, personas, processes, areas of questioning, key "
            "data — for an industry vertical or business function. Loaded "
            "contextually during the process when the client makes a defining "
            "statement that triggers it."
        ),
        "usage_scope": (
            "Used as Process Support Knowledge/Tools (Category 3). Currently "
            "stored as MD files in the crmbuilder repo as temporary scaffolding; "
            "eventual V2 storage per Planning Items captured in this session."
        ),
        "examples": (
            "- A Skill for 'charitable foundation CRM' providing guidance on "
            "typical donor entities, campaign structures, regulatory "
            "considerations.\n"
            "- A Skill for 'nonprofit mentoring' covering mentor/mentee "
            "entities, engagement lifecycles, session types."
        ),
        "distinguishing_notes": (
            "This is the methodology Skill — a domain-knowledge file for the "
            "requirements process. It is NOT the agent concept; the agent-system "
            "term for a capability an agent is given is 'Agent Skill' (DEC-389). "
            "Distinction from Pattern and Inventory is still being refined: a "
            "Skill is operational guidance; a Pattern is structural; an Inventory "
            "is the list level."
        ),
        "related_terms": "Pattern, Inventory, Agent Skill, Defining Statement",
    },
    {
        "identifier": "TERM-003",
        "name": "Pattern",
        "definition": (
            "A reusable structural template describing the typical shape of a "
            "business domain or organizational type. Captures common entities, "
            "personas, processes, and their relationships, intended as a starting "
            "reference when working with clients of that type."
        ),
        "usage_scope": (
            "Used as Process Support Knowledge/Tools (Category 3). Eventual V2 "
            "storage per Planning Items captured in this session."
        ),
        "examples": (
            "- A Pattern for nonprofit mentoring organizations capturing the "
            "typical structure of mentor-mentee engagements, session types, "
            "recruiting flows.\n"
            "- A Pattern for member-based associations capturing typical "
            "membership, dues, and communications structures."
        ),
        "distinguishing_notes": (
            "Distinction from Skill and Inventory is still being refined. Not the "
            "same as an instance: a Pattern is reusable across clients; once "
            "instantiated for an engagement, the resulting entities are "
            "deliverables."
        ),
        "related_terms": "Skill, Inventory",
    },
    {
        "identifier": "TERM-004",
        "name": "Inventory",
        "definition": (
            "A reference list of typical items — entities, personas, processes — "
            "for a given domain or organizational type. Serves as a checklist or "
            "starting set when capturing a specific client's content."
        ),
        "usage_scope": (
            "Used as Process Support Knowledge/Tools (Category 3). Eventual V2 "
            "storage per Planning Items captured in this session."
        ),
        "examples": (
            "- An Inventory of typical personas for a nonprofit (Executive "
            "Director, Program Manager, Volunteer Coordinator, etc.).\n"
            "- An Inventory of typical entities for a membership organization "
            "(Member, Account, Dues Payment, Renewal, Event Registration)."
        ),
        "distinguishing_notes": (
            "Working hypothesis: an Inventory is the list level (just the items); "
            "a Pattern is the relationships among items; a Skill is the "
            "operational guidance. Not the same as a deliverable inventory of the "
            "actual items captured for one engagement."
        ),
        "related_terms": "Skill, Pattern",
    },
    {
        "identifier": "TERM-005",
        "name": "Client",
        "definition": (
            "An organization (or, less commonly, an individual) whose product is "
            "being defined through the CRMBuilder process. Each engagement serves "
            "one client; one client may have multiple engagements over time."
        ),
        "usage_scope": (
            "Used in the Master CRMBuilder PRD and supporting documentation when "
            "referring to the recipient of the engagement's work."
        ),
        "examples": (
            "- CRMBuilder is the client of its own dogfood engagement.\n"
            "- Cleveland Business Mentors is the client of the (future) CBM "
            "engagement."
        ),
        "distinguishing_notes": (
            "Not the same as Engagement (the engagement is the unit of work; the "
            "client is the organization receiving the work). Not the same as "
            "Stakeholder (specific individuals within the client). Not the same "
            "as End User."
        ),
        "related_terms": "Engagement, Stakeholder, Persona",
    },
]


# The agent-system terms (the Agent Delivery Organization vocabulary). Plain
# definitions drawn from the ADO design + evolution docs. Server-assigned ids.
_S = "Used in the Agent Delivery Organization (ADO) design and the agent layer."
AGENT_TERMS = [
    {
        "name": "Area",
        "definition": (
            "One discipline of work within an engagement — for example storage, "
            "access, api, ui, or a methodology discipline. Every Work Task names "
            "exactly one area, and agents are experts in one area."
        ),
        "usage_scope": _S,
        "distinguishing_notes": (
            "A System area is one of a fixed built-in set shared by every "
            "engagement; an Engagement area is one a specific engagement defines "
            "for itself."
        ),
        "related_terms": "Work Task, Agent, Pass",
    },
    {
        "name": "Agent",
        "definition": (
            "A spawned worker that does one piece of delivery work under a "
            "contract and then stops. An agent is an instance created on demand "
            "from an agent profile; 'standing' means a defined scope, not a "
            "process that keeps running."
        ),
        "usage_scope": _S,
        "distinguishing_notes": (
            "An agent profile is the template (an area-and-tier role); an agent "
            "is the running instance of that template for one job."
        ),
        "related_terms": "Agent Skill, Contract, Registry, Architect, Developer, Tester",
    },
    {
        "name": "Agent Skill",
        "definition": (
            "A capability given to an agent — either an instruction (guidance "
            "text) or a tool (a callable with an input/output contract). Agent "
            "Skills are held in the registry and bound to an agent profile."
        ),
        "usage_scope": _S,
        "distinguishing_notes": (
            "This is the agent concept. It is NOT the methodology Skill "
            "(TERM-002), which is a domain-knowledge file for the requirements "
            "process (DEC-389)."
        ),
        "related_terms": "Skill, Agent, Registry, Contract",
    },
    {
        "name": "Rule",
        "definition": (
            "A governance rule an agent must follow. A rule is advisory "
            "(guidance), enforced (a hard line), or enforced-with-override. "
            "Enforced rules form the part of an agent's contract it cannot break."
        ),
        "usage_scope": _S,
        "related_terms": "Registry, Contract, Agent",
    },
    {
        "name": "Registry",
        "definition": (
            "The store that holds, resolves, and grows the agents' skills, rules, "
            "and learnings. Rows are system-shared by default with optional "
            "per-engagement overlays; the resolver composes an agent's effective "
            "contract from them."
        ),
        "usage_scope": _S,
        "related_terms": "Agent Skill, Rule, Learning, Contract, Agent",
    },
    {
        "name": "Contract",
        "definition": (
            "The effective working brief the registry composes for an agent: its "
            "instructions, its tools, the enforced rules it must obey, and the "
            "active learnings for its area and tier. The runtime gives an agent "
            "its contract when it spawns it."
        ),
        "usage_scope": _S,
        "related_terms": "Registry, Agent, Agent Skill, Rule",
    },
    {
        "name": "Engagement Admin",
        "definition": (
            "The person who administers one engagement — sets it up, manages its "
            "areas and people, and is the human point of contact when an agent or "
            "phase needs attention."
        ),
        "usage_scope": _S,
        "related_terms": "Engagement, Project Manager",
    },
    {
        "name": "Pass",
        "definition": (
            "One sweep of work across the areas at a stage of delivery — Plan, "
            "Design, Develop, or Test. The agent layer is a matrix of passes "
            "(stages) crossed with area-disciplines."
        ),
        "usage_scope": _S,
        "related_terms": "Area, Finding, Architect, Developer, Tester",
    },
    {
        "name": "Finding",
        "definition": (
            "A cross-area coherence issue recorded at the end of Design at the "
            "reconciliation gate. Open blocking findings hold the Develop stage "
            "until they are resolved."
        ),
        "usage_scope": _S,
        "related_terms": "Pass, Architect",
    },
    {
        "name": "Project Manager",
        "definition": (
            "The top coordinating role: works a project's backlog of Planning "
            "Items, decides which are eligible, and dispatches them into "
            "delivery."
        ),
        "usage_scope": _S,
        "related_terms": "PI Lead, Engagement Admin",
    },
    {
        "name": "PI Lead",
        "definition": (
            "The role that runs one Planning Item through its delivery phases: "
            "starts each phase when its predecessors are done, watches the gate "
            "state, and completes a phase when its Work Tasks are all done."
        ),
        "usage_scope": _S,
        "related_terms": "Project Manager, Architect, Developer, Tester",
    },
    {
        "name": "Architect",
        "definition": (
            "The design-tier agent role for an area: produces the design for that "
            "area's part of the work before code is written. Design and "
            "methodology areas have an Architect tier only."
        ),
        "usage_scope": _S,
        "related_terms": "Developer, Tester, PI Lead, Pass",
    },
    {
        "name": "Developer",
        "definition": (
            "The build-tier agent role for an area: writes the code for that "
            "area's Work Task, with tests."
        ),
        "usage_scope": _S,
        "related_terms": "Architect, Tester, PI Lead",
    },
    {
        "name": "Tester",
        "definition": (
            "The test-tier agent role for an area: verifies that the area's work "
            "does what it should."
        ),
        "usage_scope": _S,
        "related_terms": "Architect, Developer, PI Lead",
    },
]


def main() -> int:
    existing_ids = {
        t["identifier"] for t in _req("GET", "/terms").get("data", [])
    }
    existing_names = {
        t["name"] for t in _req("GET", "/terms").get("data", [])
    }
    created = 0
    skipped = 0
    for term in EXISTING:
        if term["identifier"] in existing_ids:
            print(f"skip {term['identifier']} (exists)")
            skipped += 1
            continue
        r = _req("POST", "/terms", term)
        d = r.get("data")
        if d:
            print(f"created {d['identifier']} {d['name']}")
            created += 1
        else:
            print(f"ERROR {term['identifier']}: {r}")
            return 1
    for term in AGENT_TERMS:
        if term["name"] in existing_names:
            print(f"skip '{term['name']}' (name exists)")
            skipped += 1
            continue
        r = _req("POST", "/terms", term)
        d = r.get("data")
        if d:
            print(f"created {d['identifier']} {d['name']}")
            created += 1
        else:
            print(f"ERROR '{term['name']}': {r}")
            return 1
    print(f"\nDONE — created {created}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
