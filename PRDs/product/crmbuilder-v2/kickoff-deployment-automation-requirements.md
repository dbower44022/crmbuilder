# Kickoff — Requirements for deployment automation: client, application, deployment

**Target:** a requirements session. No planning item exists yet; this session creates the requirements, the approving decisions and the implementing planning items, grouped into projects in build order.
**Engagement:** ENG-001. **Written:** 09-24-26 01:15, from SES-433.
**Prior session's records:** DEC-1152…DEC-1160, TERM-070…TERM-075, TERM-005 v2, TERM-067.

**Version:** 1.0
**Last Updated:** 09-24-26 01:15
**Owner:** Doug Bower

---

## Orient first

Run the session bootstrap in this repo's `CLAUDE.md` before anything else: topic
**TOP-013** and its children, active `governance_rules`, active `preferences`, the
`reference_pointer` index, and `lessons` for any area you touch. The database is
the source of truth; do not orient from files, including this one.

Read these before forming a plan. They are the decisions this session builds on
and **must not relitigate**. Each records the option chosen, the option rejected
and the cost accepted.

| Record | What it settled |
|---|---|
| DEC-1155 | The model is **client → application → deployment**. A client is any organisation that uses CRMBuilder. An application is one client's complete definition of a piece of software, private or public. A deployment is one installation of one application on one hosting provider for one client, holding its credentials, setting values, secrets, run history, readiness list, release and update policy. The defining client may run a demo/test deployment. Supersedes DEC-922 (one engagement per network). |
| DEC-1152 | The custom applications' **settings list is defined in the CRMBuilder database** as system setting records on the application, valued per deployment. The custom applications code repository no longer owns it. |
| DEC-1153 | **The design records are the source of every CRM.** Publish builds each deployment's CRM; custom screen code and the two add-on products are named, versioned components of the application. Nothing is copied from Cleveland's test system. |
| DEC-1154 | **CRMBuilder deploys the custom applications** to DigitalOcean App Platform through the API: application, managed database, update policy on all three parts, address record, backups, uptime alerts, health check. No application specification is written to a file. |
| DEC-1156 | **Each deployment's client decides when it takes a release**: automatic, or on request with a scheduled time; a client may decline. The demo/test deployment is always automatic. Deployments of one application may run different releases. |
| DEC-1157 | **CRMBuilder holds a deployment's secrets**, encrypted against the deployment; a handover file goes to the client's vault after every run and every change. No secret on an operator's computer. |
| DEC-1158 | **Person-only steps form a readiness list** on the deployment, each with instructions, owner and a check CRMBuilder runs; the run starts only when every pre-run check passes and pauses only for the two steps that need something the run created (the DNS record at an unsupported provider, installing the add-ons). |
| DEC-1159 | **A client's people are CRMBuilder users** on a web application beside the desktop one, seeing only their own client: deployments, readiness list, settings questions, releases, Update, handover, who answered what. |
| DEC-1160 | **Boston finishes by hand as a test system**; its production deployment is made by the updated CRMBuilder when Boston chooses to go live. |

Glossary, approved 09-24-26: **Application** TERM-070, **Deployment** TERM-071,
**Demo/test deployment** TERM-072, **Release** TERM-073, **Update policy** TERM-074,
**Readiness list** TERM-075; **Client** TERM-005 amended; **Chapter Support
representative** TERM-067 amended. Use these words and no others for these things.
A deploy run (DEP-NNN) is one execution that builds or changes a deployment; the
DEP prefix predates the term and was not renamed.

## What the source process looks like

The process being replaced is the New Chapter Deployment Guide in the custom
applications code repository, `cbm-client-intake`, at
`prds/chapter-network/deployment-guide/` (the step data in `steps/`, one page per
stage in `guide/`). Stages 8 through 12 and 17 are the automation target. Read
stages 8, 9, 10, 11 and 12 before writing a requirement for the thing they do by
hand; each step names its inputs, outputs, check and what goes wrong.

## Build order (Doug's recommendation from SES-433, not yet ruled)

1. **Records and boundary** — client, application, deployment, application
   visibility, deployment purpose, the client boundary on every record type, and
   the migration of today's engagements and instances (DEC-1155, DEC-1159).
2. **Settings list and the web form** — system settings on the application,
   values on the deployment, the client-facing form with "not known yet",
   conditional questions and sign-off (DEC-1152, DEC-1159).
3. **Publish the CRM from the design** — screen code and add-on products as
   versioned components; the conformance check against the design, not against
   Cleveland's test system (DEC-1153).
4. **Deploy the custom applications and hold the secrets** — the hosted web
   application component; App Platform, managed database, domain, backups,
   alerts; the secret set and the handover file (DEC-1154, DEC-1157).
5. **Readiness list and update policy** — pre-run checks, the two in-run pauses,
   running and available release, Update with a schedule (DEC-1158, DEC-1156).

The cost of this order: the settings form, the thing Doug asked for first,
arrives second, because it hangs off records that do not exist yet.

## How to run the session

One requirement at a time for Doug's approval, in DETAIL mode. Every requirement
statement passes the readability gate (positive, no identifiers, no history, about
four sentences) with an objectively verifiable acceptance summary; provenance
(conversation and topic), an approving decision, and an implementing planning item
inside a project. Product names never appear in a requirement statement.

Opening answer for the session:

```
Opening answer: Write the requirements for decisions DEC-1152 through
DEC-1160 (session SES-433, 2026-09-24): the client, application and
deployment model, the settings list, publishing the CRM from the design,
deploying the custom applications, secrets, the readiness list, the update
policy, and the client web surface. Group them into projects in build order,
one requirement at a time for my approval, using glossary terms TERM-005
and TERM-070 through TERM-075. Operating mode: DETAIL.
```

## Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 09-24-26 01:15 | Written at the close of SES-433 from its nine decisions and approved glossary. |
