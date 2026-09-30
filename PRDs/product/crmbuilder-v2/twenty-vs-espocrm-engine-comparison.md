# Twenty CRM versus EspoCRM: feasibility of switching the CRM Builder engine

| | |
|---|---|
| Document | Engine comparison and switch-feasibility assessment |
| Status | Draft for decision |
| Last Updated | 09-24-26 01:32 |
| Revision | 1.0 |
| Author | Claude (Claude Code), for Doug Bower |
| Audience | CRM Builder engine decision; Cleveland Business Mentors implementation |
| Supersedes | none |
| Related | `engine-neutral-design-model-and-adapters.md` (same folder); `docs/crm-platforms/platforms/twenty.yaml` (platform profile, stale as of this review) |

## 1. Verdict

Switching CRM Builder and the Cleveland Business Mentors implementation from EspoCRM to Twenty is technically feasible but not advisable today. The switch would cost a new publish adapter plus a redesign of four capabilities the current design leans on, and Twenty does not yet have native replacements for two of them.

The four capabilities are dynamic logic (fields that become visible or required based on another field), formula fields, email templates as first-class records, and team-scoped record access. Twenty has no native formula fields and no conditional field visibility as of version 2.41.0 (September 17, 2026). Both are stated as planned. Team-scoped and record-level access exist in Twenty only in the paid Organization tier, on the cloud and self-hosted alike.

Twenty is the stronger platform on three axes that matter to CRM Builder's future: a declarative, idempotent application model (define the data model in code, plan, apply, pull), a metadata application programming interface (API) that mirrors the workspace, and native artificial intelligence (AI) and Model Context Protocol (MCP) surfaces. Those are reasons to build a Twenty adapter as a second engine, not reasons to move the first client.

Confidence: the feature facts below are verified against the vendors' documentation and release notes as of September 24, 2026 unless marked otherwise. The effort estimates in section 14 are inferred from the size of the existing EspoCRM adapter, not measured.

## 2. What was compared and how

The comparison covers the twelve areas the CRM Builder methodology touches: data model, relationships, field behaviour, automation, access control, communication, views and layouts, reporting, API and extensibility, self-hosting and operations, licensing and cost, and maturity. Each area is scored against what the Cleveland Business Mentors design actually uses, not against a generic checklist.

Sources: Twenty documentation (docs.twenty.com), Twenty GitHub releases and discussions, the Twenty licence file, Twenty's pricing page; EspoCRM documentation, the EspoCRM v10.0 release announcement, the EspoCRM extensions pages; and three independent 2026 comparisons. The full list is in section 18. The web search budget for this session was exhausted before every question was answered; items marked "not confirmed" are those.

## 3. The two products at a glance

| | Twenty | EspoCRM |
|---|---|---|
| Current version | 2.41.0, September 17, 2026 | 10.0.3, July 17, 2026 (9.3.10 maintenance line also current) |
| First release | 2023 (Y Combinator S23) | 2014, company founded 2011 |
| Vendor | Twenty, Paris; about 32 staff (Tracxn, July 2026) | Letrium Ltd, Chernivtsi, Ukraine |
| Stack | TypeScript: NestJS server, React front end, PostgreSQL 15+, Redis, separate worker container | PHP 8.2 to 8.4, MySQL 8 or MariaDB 10.3+ or PostgreSQL 15+, single-page JavaScript front end |
| Licence | AGPLv3 core; files marked Enterprise under a commercial licence; software development kit (SDK) and bundled apps MIT | AGPLv3 core; paid extensions proprietary |
| Release cadence | About weekly minor releases (2.34 to 2.41 between August 24 and September 17, 2026) | Two to three minor releases a year plus patch releases |
| Idle memory | About 750 MB to 1.2 GB across server, worker, PostgreSQL and Redis; 2 GB minimum, 4 GB recommended | About 250 to 380 MB; fits a 2 GB server |
| GitHub | About 56,000 stars, 300+ contributors, 182 open issues | About 3,300 stars, about 970 commits in the last year |
| Cloud price | Pro $9, Organization $19 per user per month (yearly); Enterprise from $50,000 a year | Basic $15, Enterprise $25, Ultimate $69 per user per month |
| Self-hosted price | Free; Organization features need a licence key (reported at $25 per user per month, not confirmed on the pricing page) | Free; Advanced Pack $395, Sales Pack $260, Outlook $240, Google $190 per instance |

## 4. Data model and customization

Both products let an administrator create custom objects and fields without code, and both expose the result through an API immediately. The differences are in field behaviour and in how the model is versioned.

**Twenty.** Custom objects and fields are unlimited and free. Field types: text, rich text, array, raw JSON, number, numeric, rating, position, date, date-time, boolean, select, multi-select, and the composite types full name, address, emails, phones, links, currency, actor and files, plus relation and morph relation. A field can be unique, searchable, audit-logged, nullable or not, and can carry a default value. A field that is not nullable must have a default. Field types cannot be changed after creation; the documented path is create a new field, migrate, deactivate the old one. There is no regular-expression or pattern validation on text fields (open feature request). Standard objects (People, Companies, Opportunities, Notes, Tasks) can be relabelled but their API names are fixed, and an app cannot modify standard fields, only add new ones.

**EspoCRM.** Custom entities are created from templates (Base, Base Plus, Person, Company, Event) and inherit that template's native fields and behaviour. Field types include varchar, text, enum, multi-enum, array, checklist, int, float, currency, date, datetime, bool, email, phone, address, url, link, link-multiple, foreign, file, attachment-multiple, image and more. Fields carry required, read-only, audited, pattern, min and max, and default. Field types can be changed with data-loss warnings. Version 10.0 added multiple pipelines per entity, cascading links (a Contact picker filtered by the chosen Account), cascade removal with restore, record locking, and categories for custom entities.

**What this means for the current design.** The Cleveland Business Mentors model uses the Person, Company and Event templates (Contact, Account, Session as a Meeting) and foreign fields that mirror a scalar from a linked record. Twenty has no foreign-field type; the equivalent is a workflow that copies the value on change, or a relation field widget on the page layout that shows the related record inline. Twenty has no Event template; a Session would be a custom object with date-time fields, and calendar views would show it.

## 5. Relationships

**Twenty.** One-to-many and many-to-one are first class. Many-to-many is implemented through a junction object and must be enabled in the beta feature list; the interface hides the junction. Polymorphic ("morph") relations let one field point at several object types, which is how Notes and Tasks attach to anything. In the application SDK every relation is declared on both sides, including relations to standard objects; omitting the reverse side fails the sync. Relations to multiple object types are not yet supported by comma-separated values (CSV) import or export.

**EspoCRM.** One-to-many, many-to-one, one-to-one, many-to-many, parent (polymorphic) and children-to-parent are all supported in the Entity Manager and through the REST API's link creation action. CRM Builder already handles the c-prefix rules and the create-link conflict behaviour.

**What this means.** The CBM model's twelve or so relationships map cleanly. Many-to-many links (if any are declared) would need the beta junction feature turned on, which is a risk for a client instance.

## 6. Field behaviour: dynamic logic, formulas, validation

This is the area where the gap is widest and it decides the verdict.

| Capability | Twenty (2.41.0) | EspoCRM (10.0) |
|---|---|---|
| Conditional visibility (show a field when another has a value) | Not available. Maintainer statement March 18, 2026: planned in the Layouts track, "one of the priorities that will come quickly after" Layouts v1. Not shipped as of September 17, 2026 | Dynamic Logic: visible, required, read-only, invalid, and option-set conditions per field, on any entity, free |
| Conditional required | Not available (same track) | Dynamic Logic |
| Formula and calculated fields | Not native. Documentation: "Twenty doesn't yet support native formula fields (coming in 2026)". Workaround: a workflow with a code step that writes the value on create and update | Formula script per entity, free; aggregate, arithmetic, string, date functions; runs before save |
| Rollup and aggregate over related records | Not native; workflow or dashboard aggregate | Formula with `entity\countRelated` and `entity\sumRelated` |
| Field validation pattern | Not available | Pattern, min, max on fields |
| Unique constraint | Yes, per field, with restore-on-import behaviour for soft-deleted matches | Duplicate-check fields per entity (Contact, Lead, Account and custom), plus unique index in metadata |
| Foreign (mirrored) field | Not available; relation field widget or workflow copy | Foreign field type |

The CBM design carries five formula fields on the mentor Contact record and type-conditional visibility on five Account fields, with `visibleWhen` and `requiredWhen` declared in YAML. On Twenty each formula becomes a workflow with a code action, and each visibility rule becomes either nothing (all fields always visible) or a page-layout split into separate tabs. Both are workable but change the user experience the CBM stakeholders approved, and each workflow is one more thing to audit and publish.

## 7. Automation

**Twenty.** Workflows are free in the community edition. Triggers: record created, updated, deleted; manual (button on a record or on a selection, with an input form); scheduled (runs in UTC); inbound webhook. Actions: create, update, delete and find records; send email through a connected account; HTTP request; TypeScript code step (logic function); form; iterator; filter; branches; delay; AI agent step. There is a soft limit of 100 runs a minute, after which runs queue. Workflows have versions, runs, and logs. An update-record trigger that updates the same record can loop; the documentation warns about this. Workflows are edited in the interface; declaring them in the application SDK is not documented as of the September 2026 developer documentation, although `yarn twenty pull` writes views, page layouts, navigation menu items and translations as typed files.

**EspoCRM.** Workflows, Business Process Management flowcharts and Reports are in the paid Advanced Pack ($395 per instance). Free automation is limited to Formula (before-save scripting) and Dynamic Logic. CRM Builder today parses `workflows:` in YAML but does not apply them (they surface as manual configuration).

**What this means.** Twenty is ahead here. It is the one area where a switch removes a paid dependency and gives CRM Builder an apply path it does not have today, provided the workflow definition can be written through the core API (the workflow, workflow version and trigger objects are exposed through the API; declaring them from the SDK is not confirmed).

## 8. Access control

| Capability | Twenty | EspoCRM |
|---|---|---|
| Roles with object-level create, read, update, delete | Yes, free; plus "destroy" (hard delete) as a separate permission | Yes, free; scope levels all, team, own, no |
| Field-level permissions | Yes, free (see, edit, no access); since 1.3.0 | Yes, free (read and edit levels) |
| Settings permissions | Yes, granular | Admin flag plus portal admin |
| Teams | No team construct. Members, roles, and row-level predicates on workspace members | Teams as first-class; records carry a team set; assignment restricted to own team; team-scoped visibility per role |
| Record-level (row-level) permissions | Organization tier only, cloud or self-hosted licence key. Predicates on fields and workspace members with AND/OR groups | Free, through role scope levels and team ownership |
| Record sharing | Enterprise-only as of 2.41.0 | Not a feature; team membership serves the purpose |
| Roles on API keys | Yes | API users carry a role |
| Portals for external users | None built in; a community portal project exists | Portals with portal roles, per-portal layouts and dashboards, free |
| Single sign-on | SAML and OIDC, Organization tier | OIDC free (no two-factor with OIDC); LDAP free |
| Two-factor authentication | Yes | Yes, time-based one-time password |
| Audit logs | Organization tier; per-field `isAuditLogged` timeline free | Stream with audited fields, action history, authentication log, free |

The CBM design publishes roles, field permissions, teams and filtered tabs through the security program. On Twenty the roles and field permissions land as-is; teams and any "own or team records only" rule need the Organization licence, which is a recurring per-seat cost for a nonprofit that currently pays nothing for the same behaviour. Filtered tabs (which navigation items a role sees) have no direct equivalent; navigation menu items are workspace-wide.

There is one open security finding to weigh: a field-level read bypass through group-by queries was reported against the Twenty server in June 2026 and was still being followed up in August 2026. EspoCRM shipped fixes for two Common Vulnerabilities and Exposures (CVE) entries in June and July 2026 (9.3.9 and 9.3.10). Both projects publish and fix; neither is clean.

## 9. Email, calendar and outbound communication

| Capability | Twenty | EspoCRM |
|---|---|---|
| Mailbox sync | Gmail and Microsoft 365 through OAuth (own client credentials on self-hosted); IMAP, SMTP and CalDAV for other providers since 1.4; sync every 5 minutes; aliases supported since August 2026 | Personal and group IMAP accounts, SMTP per account, free; Google and Outlook packs add deeper sync (paid) |
| Compose and reply from a record | No compose or reply button as of the documentation reviewed; sending happens through workflows | Compose, reply, templates, signatures in the interface |
| Email templates as records | No; the send-email workflow action holds subject and body with `{{variables}}` | Email templates entity with placeholders, free; used by mass email and workflows |
| Mass email and campaigns | Not available; vendor recommends an external tool through a workflow. Email sequences requested May 2026 | Campaigns, target lists, mass email with tracking and opt-out, free |
| Calendar | Google and Microsoft calendar sync; create events from workflows and AI; day, week, month views since August 2026 | Calendar with meetings, calls, tasks; Google and Outlook sync paid |
| Print to PDF | Through an external service in a workflow; a community billing-documents app is under construction | PDF templates per entity, free |

The CBM design declares three email templates on the mentor Contact and expects mass communication to donors and mentors. On Twenty those three templates become three workflows, and mass communication moves to an external tool (the design already assumes a separate email marketing product for newsletters, so the gap is narrower than it looks). PDF output for receipts or letters would need an external service.

## 10. Views, layouts and navigation

**Twenty.** Views are table, list, kanban and calendar, with advanced filters (nested AND/OR), sorts, group by, column aggregates, and sharing with the whole workspace. Since 2.0 record pages are built from tabs and widgets by drag and drop: field widgets, related-record tables, timeline, emails, files, notes, tasks, workflows, charts, iframes, and rich-text notes. Layouts are per object, not per role, and there is no conditional widget display yet (the columns exist in the schema; the SDK ignores the value). Navigation is customizable per user with favorites and folders. The application SDK can declare views, page layouts and navigation menu items, and `yarn twenty pull` round-trips them.

**EspoCRM.** Eighteen layout types per entity (detail, edit, list, small variants, filters, mass update, kanban, side panels, bottom panels, and more), a layout manager, dynamic logic on panels, per-team and per-portal layout sets, tab list per role through filtered tabs, dashboards with dashlets. CRM Builder's V2 audit captures all eighteen and the publish path applies them.

**What this means.** Twenty has fewer layout types but a richer record page. Around half of the eighteen EspoCRM layout types have no Twenty counterpart because Twenty does not have that surface (mass update forms, search filter layouts, small detail views). The mapping is many-to-few, which simplifies a Twenty adapter rather than complicating it.

## 11. Reporting and dashboards

**Twenty.** Dashboards with bar, pie, line and aggregate charts, iframes and rich text; count, sum and average; filters and group by; no export, no sharing outside the workspace, no gauge chart. Independent reviews call reporting basic and note that pipeline and rep performance reporting is underdeveloped. The workspace lives in its own PostgreSQL schema, so a read replica in Metabase or similar is the documented route for real reporting.

**EspoCRM.** Reports (grid and list, grouped, charted, report panels, list filters) are in the paid Advanced Pack. Free edition has dashboards with fixed dashlets.

Neither is strong out of the box. Twenty's free dashboards are roughly equal to EspoCRM's free dashlets; EspoCRM's paid reports are ahead of Twenty's dashboards.

## 12. API, extensibility and AI

**Twenty.** Two APIs, each in REST and GraphQL: a core API for records and a metadata API for objects, fields and relations. Endpoints are generated from the workspace model, so a custom object gets its endpoints on creation. Batch operations take 60 records a call; GraphQL adds batch upsert. The default rate limit is 100 requests a minute and is configurable on self-hosted instances. An OpenAPI description and interactive playground are generated per workspace. Known rough edges: the REST metadata endpoints return errors in multi-workspace mode, and cursor pagination has had regressions reported in 2026.

The application SDK (2.0, April 2026) is the decisive difference. An app is a TypeScript package with stable universal identifiers that declares objects, fields on standard objects, relations (both sides), views, page layouts, navigation menu items, one application role, logic functions on HTTP routes, cron and database events, front components, and AI skills and agents. `yarn twenty plan` previews, `yarn twenty apply` diffs against what the app owns and applies idempotently (with `--no-delete` for additive syncs), and `yarn twenty pull` writes the installed state back as define files. This is the same shape as CRM Builder's own check-then-act publish and its audit capture, done by the vendor.

AI: agents and chat are built in, model choice is a slider from fast to smart with provider and price shown, and MCP is native on the cloud. On self-hosted instances the documented route is an API key plus one of several community MCP servers; whether the native MCP endpoint is available self-hosted is not confirmed.

**EspoCRM.** One REST API covering every entity plus the administrative actions the interface uses (Entity Manager, layouts, roles, teams, settings). OpenAPI generation arrived in 9.3. Extensions are PHP packages installed through the administration screen; version 10.0 added TypeScript support for front-end extensions. No native AI or MCP; third-party extensions exist. Ecosystem: a marketplace of paid and free extensions from several vendors (Eblasoft, DevCRM and others) built up over a decade.

## 13. Self-hosting and operations

| | Twenty | EspoCRM |
|---|---|---|
| Install | Docker Compose; official install script; server, worker, PostgreSQL 15+, Redis; optional ClickHouse for analytics; optional S3 for files | Docker Compose or bare PHP; official installer script (the one CRM Builder drives over SSH) |
| Upgrade | Migrations run on server start; cross-version jumps supported from 1.23; back up first; 2.5+ runs slow encryption backfills; 2.34+ requires PostgreSQL 15 | One-step upgrades through the interface or command line; extensions can break on major versions |
| Backup | `pg_dumpall` of the container database; a documented restore that some users report as incomplete | Database dump plus the data directory |
| Configuration | Environment variables, with an admin panel that can store values in the database and silently override the environment file | `config.php` and the administration screens |
| Multi-tenant | One workspace per instance by default; multi-workspace mode for hosting several clients on one server | One instance per client |
| Mobile | Responsive web; third-party native app (TwentyMobile) | Responsive web, installable as a progressive web app; third-party native apps |
| Languages | 30+ languages, right-to-left since September 2026 | Many languages through the language packs |

Operational cost is the point to weigh. Twenty is four containers and a weekly release train; EspoCRM is two containers and a quarterly one. CRM Builder's deploy path (droplet, installer, upgrade, recovery) is built around the EspoCRM installer; the equivalent for Twenty would be a new deploy scenario with Compose files, environment generation, and the worker.

## 14. Fit against CRM Builder: what an engine switch means for the code

CRM Builder's V2 store is designed as a compiler: the database holds the engine-neutral design and a per-engine adapter generates the deployable artifact on demand (the design document is `engine-neutral-design-model-and-adapters.md` in this folder, PRJ-025). The code confirms the design only partly. Where the abstraction stops is the whole of the switching cost.

**What is engine-neutral today.** The design records (entities, fields, associations, views, rules, automations, dedup rules, message templates) and the `engine_override` record, keyed by target engine, design record and attribute, with its repository, API router, connector tools and migration. The adapter protocol `CrmAdapter` in `crmbuilder-v2/src/crmbuilder_v2/adapters/base.py` takes those records and returns a generation result with deferrals for what the engine cannot build. The neutral field vocabulary (seventeen types refined by format, display, holds, values, scale and supplied-by) and a rule that a second engine "brings its own table, not an edit to this one".

**What is EspoCRM-shaped today.** Three of the four paths.

| Path | State | What a Twenty engine needs |
|---|---|---|
| Generate | Behind the protocol; one implementation, `adapters/espocrm/`, emitting YAML and self-checking through the V1 program validator | A second implementation emitting a Twenty app (TypeScript define files) and self-checking through `yarn twenty plan`; a Twenty field-type table; condition and formula compilers have no target and return deferrals |
| Publish | Hard-wired: `publish/service.py` and `publish/run.py` import the EspoCRM adapter and write client directly; ten appliers (entities, fields, links, layouts, entity settings, filtered tabs, message templates, security, duplicate checks, governed settings); no registry or dispatch by engine | A dispatch by engine, then a Twenty publisher that runs `yarn twenty apply` (or the metadata API), parses the Terraform-style plan into the run log, and keeps the access-change confirmation gate |
| Introspect | EspoCRM-shaped client behind a named interface; eleven audit areas, reverse type mapping, reconcile into the inventory | A Twenty introspector on `yarn twenty pull` and the metadata API; fewer areas (no filtered tabs, no email templates, four view types, one page layout per object) |
| Deploy | Self-hosted EspoCRM only: DigitalOcean and Cloudflare providers, SSH server build, installer, upgrade through the container, recovery, certificate job, DNS checks | Reuse the providers, SSH, DNS and certificate work; replace the installer and upgrade steps with Compose, environment generation, secrets, worker, PostgreSQL 15 and Redis |

Two vocabulary changes precede any of that. `TARGET_ENGINES` in `access/vocab.py` is the set `espocrm` and `hubspot`, backed by a database check constraint, so adding Twenty is a migration. The design's bias guard (REQ-142) says an attribute is neutral only when it maps to both EspoCRM and HubSpot; a third engine either joins that test or is documented as an exception per attribute.

**What has no target in Twenty.** Dynamic logic (`visibleWhen`, `requiredWhen`, compiled today into EspoCRM field payload keys), formula fields (compiled into the field's `formula` key), foreign fields, email templates as records, duplicate-check field sets beyond one unique field, per-role tab lists, portals and PDF templates. Each becomes a deferral in the generation result and a redesign in the client's requirements. Two areas move the other way: workflows, which EspoCRM's free edition cannot apply and Twenty can (SDK declaration not confirmed; the core API exposes workflow and workflow-version objects), and saved views, which EspoCRM has no public write path for and Twenty declares with `defineView`.

**One EspoCRM dependency is already paid.** Filtered tabs are written through the report-filter endpoint, which needs the Advanced Pack. That is the only place the current publish path depends on a paid EspoCRM extension.

**Effort.** Inferred from the size of the EspoCRM adapter, not measured. Generate and publish are smaller builds than their EspoCRM counterparts because the SDK owns the diff and the apply. Introspect is smaller because there are fewer areas. Deploy is comparable, and the provider and DNS code carries over. The publish dispatch is a refactor of the service that exists. The unbounded part is the redesign of the unsupported capabilities, because it changes confirmed requirements and needs stakeholder approval under the requirement-first rule.

**The platform catalogue is out of date.** The profile at `docs/crm-platforms/platforms/twenty.yaml` was last reviewed on March 30, 2026, before Twenty 2.0. It records no layout or view API, roles as partial, many-to-many as planned, no workflow API and no rich-text field. All five have changed: page layouts, views and navigation are declarable in the SDK and round-trip through pull; roles carry object, field and settings permissions with row-level rules in the Organization tier; many-to-many ships behind a beta flag; workflows are exposed through the core API; and rich text is a field type. The profile should be re-reviewed before any Twenty work is planned from it.

## 15. Fit against the Cleveland Business Mentors implementation

Inventory of the confirmed design that would be affected, from the deployment validation record:

| Design element | Count | Twenty outcome |
|---|---|---|
| Custom entities (Engagement, Session, Dues, Contribution, FundraisingCampaign) | 5 | Port as custom objects; Session loses the Event template and its native calendar fields |
| Custom fields on Contact and Account | about 69 | Port as fields on People and Companies; `optionsDeferred` enum lists port as select options later |
| Custom fields on custom entities | about 56 | Port |
| Relationships | about 12 | Port; many-to-many needs the beta junction flag |
| Formula fields | 5 | Rebuild as workflows |
| Conditional visibility rules | 5 fields on Account plus others | Drop, or split into tabs; no native equivalent |
| Email templates | 3 | Rebuild as send-email workflow actions |
| Saved views | about 15 | Port as views |
| Workflows | about 4 | Gain a real target (today manual configuration) |
| Duplicate checks | about 2 | Reduce to unique-field constraints where one field suffices |
| Roles, teams, filtered tabs | security program | Roles and field permissions port; teams and tab filtering need Organization licence or are dropped |

The nonprofit gains an AI-native interface, free workflows and a modern record page. It loses free team-scoped access, conditional forms, formula fields, email templates and mass email, and it takes on a larger server and a weekly upgrade train. For a small volunteer-run organization the operational change is the larger risk.

## 16. Licensing and cost over three years (one client instance, 10 users)

| | Twenty self-hosted | EspoCRM self-hosted |
|---|---|---|
| Core licence | $0 | $0 |
| Automation | $0 (workflows free) | $395 once for Advanced Pack if workflows or reports are needed; renewal for updates after the first year (term not confirmed) |
| Team-scoped or row-level access | Organization licence key, reported $25 per user per month: $3,000 a year, $9,000 over three years (not confirmed on the pricing page) | $0 |
| Google or Microsoft mail sync | $0 (own OAuth credentials) | $190 (Google) or $240 (Outlook) once, optional |
| Server | 4 GB droplet, about $24 a month | 2 GB droplet, about $12 a month |
| Three-year total | about $900 to $9,900 depending on whether row-level access is needed | about $430 to $1,300 |

Licence terms that matter for CRM Builder as a product: both cores are AGPLv3, so hosting a modified build for a client obliges publishing the modifications; CRM Builder does not modify either engine, so this is not a constraint. Twenty's Enterprise-marked files may not be used in production without a subscription, and record sharing moved into that set in September 2026. Twenty's SDK and bundled apps are MIT, so a CRM Builder-generated app carries no copyleft obligation of its own.

## 17. Maturity and risk

**Twenty.** Fast-moving: version 2.0 in April 2026, seven releases in the four weeks before this document, breaking changes noted in release notes (for example, the AI model configuration and connection permissions in 2.41.0). Funding reports conflict (a $38 million Series A in November 2025 and a $100 million Series B in June 2026 appear in different sources; neither is confirmed here). A larger, younger community; a Discord of about 7,000; documentation that lags features. Independent reviews converge on the same shape: excellent core and developer experience, thin reporting, no marketing, and "treat the roadmap as upside, not a guarantee".

**EspoCRM.** Slow-moving and predictable: a twelve-year codebase, a small company, a forum with a decade of answers, and an extension ecosystem. Reviews converge on: fast, customizable without code, cheap, but dated interface, no AI, and reporting behind a paywall. The vendor is in Ukraine, which is a continuity consideration to name and not to overweight; the project has shipped through 2022 to 2026 without interruption.

For a nonprofit client the relevant risk is upgrade churn. Twenty's cadence means either the client runs months behind or someone applies weekly upgrades and watches for breakage. EspoCRM's cadence matches a volunteer operator.

## 18. Migration path if the decision is to switch

1. Freeze the confirmed CBM design in the V2 store; it is engine-neutral by construction.
2. Record the redesign decisions for the four unsupported capabilities as decisions with approving requirements.
3. Build the Twenty emitter against a test workspace using the SDK; publish the CBM model as one app; pull it back and diff.
4. Migrate data over the API in dependency order (Companies, People, then custom objects), matching relations on unique fields; the CSV path caps at 10,000 rows and does not carry views, workflows or permissions.
5. Rebuild the three templates as workflows and the five formulas as workflows; validate against the verification specifications.
6. Run both instances in parallel for one reporting cycle before cutover.

## 19. Recommendation and decision request

Plain-language question: does CRM Builder move its engine, and the Cleveland Business Mentors implementation with it, from EspoCRM to Twenty now?

Option A, stay on EspoCRM and revisit on a trigger. Keep the current engine for the Cleveland Business Mentors implementation. Reassess when Twenty ships native formula fields, conditional field visibility, and either free row-level access or a nonprofit price. What it does well: no redesign, no new operational load on the client, no licence cost. What it costs: CRM Builder keeps an imperative REST adapter against a PHP engine with no AI surface, and defers the declarative apply model Twenty already offers.

Option B, keep EspoCRM for the client and build a Twenty adapter as a second engine. Dogfood the adapter on CRM Builder's own needs and offer Twenty to the next client whose design has no dynamic logic or team scoping. What it does well: proves the engine-neutral store, captures the SDK's plan-apply-pull model, and positions the product for AI-native clients. What it costs: a second adapter to maintain, a second deploy scenario, and the two-engine split in documentation and support.

Option C, switch the client now. Redesign the four capabilities, rebuild, migrate. What it does well: one modern engine, free workflows. What it costs: stakeholder re-approval of confirmed requirements, a per-seat licence for team access, a weekly upgrade train for a volunteer operator, and a migration during the client's active use.

Recommendation: Option A now, with Option B queued as a project once the Master CRM Builder PRD phase is done. The cost of A is delay on the declarative publish model; the cost of B on top of A is maintenance of a second engine, which is the price of the product claim that the store is engine-neutral.

## 20. Sources

Twenty: pricing page; documentation on relation fields, permissions, formula fields, upgrade guide, APIs, apps, dashboards, data migration, application roles, relations in apps, extending objects, sync and recovery, page layouts, views, object definition; GitHub releases 2.41.0 and the releases page; licence file; discussion 18728 (conditional visibility); issues 25911 (field-level bypass), 20044 and 25874 (pagination), 16696 (metadata REST in multi-workspace mode); CVE-2026-26720 write-up.

EspoCRM: v10.0 release announcement (July 2, 2026); features page; Advanced Pack, Sales Pack and bundle pages; documentation on dynamic logic, formula, roles, portals, mass email, email accounts, printing to PDF, entity manager, 2FA, OIDC, LDAP; GitHub releases.

CRM Builder codebase: `crmbuilder-v2/src/crmbuilder_v2/` adapters, publish, introspect and deploy packages; `access/vocab.py`; `transform/normalize.py`; `docs/crm-platforms/platforms/twenty.yaml`; `PRDs/product/crmbuilder-v2/engine-neutral-design-model-and-adapters.md`; `PRDs/product/crmbuilder-automation-PRD/engine-pluggability-planning.md`.

Independent: Use Apify "Twenty CRM vs EspoCRM 2026"; OpenAlternative comparison; Dench reviews of both; TaskRhino, MakerStack and Sentisight reviews of Twenty; Tomba review of EspoCRM; wz-it release summary.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-24-26 01:32 | Claude (Claude Code) | First draft from web research and the CRM Builder codebase, for Doug's decision. |
