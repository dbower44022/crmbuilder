# CRM Builder — Governance Recording Rules

> **These rules now live in V2.** Per DEC-393 (governance and spec content
> lives in V2, not files) and DEC-394 (the recording rules are V2 `requirement`
> records), the governance recording rules were migrated out of this file into
> the V2 database under topic **TOP-013 — "Governance Recording Method"**
> (PI-130, 06-04-26). **Read them there**, not here.
>
> Each rule is a `requirement` record stated in plain declarative language,
> filed under TOP-013 (or one of its child topics), and traced to the decision
> that established it via a `references` edge. The child topics group the rules
> by area:
>
> | Topic | Area |
> |---|---|
> | TOP-076 | Core Recording Principles |
> | TOP-077 | Identifier Discipline |
> | TOP-078 | Project Records |
> | TOP-079 | Session Records |
> | TOP-080 | Conversation Records |
> | TOP-081 | Decision Records |
> | TOP-082 | Planning Item Records |
> | TOP-083 | Reference Records |
> | TOP-084 | Work Ticket Records |
> | TOP-085 | Recording Mechanism |
> | TOP-086 | Wire-Format Constraints |
>
> **How to read them.** Against the live V2 API (with the `X-Engagement`
> header naming the engagement):
>
> ```bash
> # the topic and its child topics
> curl -s -H "X-Engagement: CRMBUILDER" http://127.0.0.1:8765/topics/TOP-013
> # the rules under a child topic (requirements that is_about it)
> curl -s -H "X-Engagement: CRMBUILDER" "http://127.0.0.1:8765/references?target_id=TOP-079&relationship=is_about"
> # a single rule
> curl -s -H "X-Engagement: CRMBUILDER" http://127.0.0.1:8765/requirements/REQ-077
> ```
>
> Or browse the Topics / Requirements panels in the V2 desktop app.
>
> The historical content of this file (v0.1 discussion draft) remains in git
> history prior to commit retiring it.
