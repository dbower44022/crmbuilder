# Zoom Integration Architecture

**CRM Builder — Zoom Webinar Platform Integration**

Last Updated: 04-30-26 17:00

---

## Revision Control

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0 | 04-30-26 17:00 | Doug Bower | Initial draft. Defines bidirectional integration between EspoCRM Events and Zoom Webinars, including webinar provisioning at Draft → Scheduled, registrant push from EventRegistration records, and post-webinar attendance capture. Built on the shared Bridge Service from `survey-integration-architecture.md` via a new `MeetingConnector` interface. |

### Change Log

- **1.0 (04-30-26):** Initial draft. Establishes ten-section architecture covering Zoom Webinar provisioning at the Event Draft → Scheduled status transition; always-on update sync from Event record fields to the Webinar; registrant push at EventRegistration creation with backlog-and-flush handling for registrations created before the Webinar exists; auto-cancellation of Zoom registrants when EventRegistration is cancelled; auto-sync of Contact field changes to existing Zoom registrants; webhook + polling safety net for inbound attendance; coarse-grained attendance writeback (`attendanceStatus = Attended | No-Show`); walk-in capture only for matched Contacts; Zoom Webinar deletion on Event cancellation; Postponed Events leave Webinar in place. Server-to-Server OAuth authentication, single shared host user, HMAC-SHA256 webhook signature verification, exponential-backoff retry policy, three-layer failure visibility (logs + `ZoomIntegrationLog` entity for failures only + email alerts on permanent failures).

---

## 1. Overview

This document defines the architecture for integrating Zoom Webinars with EspoCRM deployments managed by CRM Builder. The design provides a reusable, YAML-driven pattern that automates three flows:

1. Creating a Zoom Webinar when an Event in the CRM transitions from Draft to Scheduled
2. Pushing registered Contacts (via EventRegistration records) to the Zoom Webinar as registrants
3. Capturing attendance back from Zoom into the EventRegistration records once the Webinar ends

The integration runs on the same **Bridge Service** introduced in `survey-integration-architecture.md` (Section 4) — the Zoom integration adds a new connector type rather than a parallel deployment.

### 1.1 Scope

This PRD is scoped to **Events with `format = Virtual` or `format = Hybrid` in the Community Relations (CR) domain**. Every such Event maps to a Zoom Webinar with uniform treatment — there is no per-event-type variation, no per-Event configuration, no manual-approval workflow.

**Explicitly out of scope:**

- Zoom Meetings (mentoring Sessions in the MN domain — future PRD)
- Google Meet (mentoring Sessions — future PRD)
- Per-event-type configuration variants
- Manual approval of registrants
- Webinar Q&A and poll capture
- Recording retrieval (the `recordingUrl` field on Event is populated by other means, deferred to future work)

### 1.2 Goals

- Enable any CBM event coordinator to move an Event from Draft to Scheduled and have the corresponding Zoom Webinar provisioned automatically
- Automatically register contacts in Zoom when EventRegistration records are created in the CRM, including handling registrations that exist before the Event reaches Scheduled status
- Keep the Event record in the CRM as the source of truth: changes to the Event's name, dates, description, or timezone propagate to Zoom automatically
- Automatically remove registrants from Zoom when their EventRegistration is cancelled in the CRM
- Capture attendance back to EventRegistration records (`Attended` vs `No-Show`) once the Webinar ends
- Capture walk-in attendees who are existing Contacts but had no pre-existing EventRegistration
- Surface failures via three layers: structured logs, a `ZoomIntegrationLog` entity in the CRM, and email alerts when a failure becomes permanent
- Reuse the Bridge Service infrastructure (HTTP listener, scheduled tasks, retry logic, EspoCRM client, alerting) defined for the survey integration

### 1.3 System Components

| Component | Role |
|---|---|
| **EspoCRM** | Core CRM. Hosts the Event, EventRegistration, Contact, and `ZoomIntegrationLog` entities; fires webhooks on entity create/update events; provides the REST API used by the bridge for record CRUD |
| **Zoom** | External webinar platform. Hosts Webinar sessions, manages registrants, generates attendance reports, fires session-lifecycle webhooks. Single shared Zoom account for all Webinars |
| **Bridge Service** | Python middleware (shared with survey integration). Listens for triggers from EspoCRM and Zoom, orchestrates provisioning, registrant sync, and attendance capture between the two systems |
| **CRM Builder** | Deployment tool. Provisions the new Zoom-related fields on Event and EventRegistration, the `ZoomIntegrationLog` entity, the EspoCRM webhooks, and the Zoom connector configuration in the bridge service |

### 1.4 Reference Implementation

The reference deployment is Cleveland Business Mentors (CBM), a nonprofit mentoring organization. CBM uses Zoom Webinars for all virtual or hybrid CR-domain Events (workshops, networking events, donor-facing events, and any other registration-based Event the org runs virtually). A single shared Zoom account hosts all Webinars; the configured host user (the Zoom user holding the Webinar license) is the host of record for every session regardless of which CRM coordinator created the Event.

---

## 2. Data Model

This integration adds new fields to two existing entities (Event and EventRegistration) and introduces one new entity (`ZoomIntegrationLog`). The existing entity PRDs in the CBM repo (`PRDs/entities/Event-Entity-PRD.docx` and `PRDs/entities/EventRegistration-Entity-PRD.docx`) will be revised separately to incorporate these additions — see Section 10 (Downstream Work).

### 2.1 Event Entity Additions

The existing Event entity has fields including `name`, `status`, `format`, `dateStart`, `dateEnd`, `duration`, `description`, `timezone`, `virtualMeetingUrl`, `registrationUrl`, and `recordingUrl`. The integration uses these existing fields and adds the following:

| Field | Type | Purpose |
|---|---|---|
| `zoomWebinarId` | varchar (read-only) | The Zoom-side Webinar ID, populated by the bridge after successful provisioning. Empty until the Webinar is created |
| `zoomHostEmail` | varchar (read-only) | The Zoom user under whose account the Webinar was created. Populated by the bridge from connector configuration |
| `attendanceCapturedAt` | dateTime (read-only) | Timestamp set by the bridge when the inbound attendance flow completes successfully. Acts as the idempotency key — a non-null value means the attendance pull is done; subsequent inbound triggers (webhook OR polling) are no-ops |
| `zoomLastSyncedAt` | dateTime (read-only) | Timestamp updated after every successful outbound update sync (Section 5.2). Lets operators see when the Webinar was last reconciled with the CRM record |

**Existing fields populated by the integration:**

| Field | When populated |
|---|---|
| `virtualMeetingUrl` | At Webinar creation (Draft → Scheduled). Set to the Webinar's join URL returned by Zoom |
| `registrationUrl` | At Webinar creation. Set to the Webinar's public registration URL returned by Zoom |

These two fields exist in the current Event Entity PRD as system-populated. The Zoom integration is the system that populates them.

### 2.2 EventRegistration Entity Additions

The existing EventRegistration entity has fields including `event` (link), `contact` (link), `attendanceStatus` (Registered | Attended | No-Show | Cancelled), `registrationSource` (Online | Walk-In), `registrationDate`, and `cancellationDate`. The integration adds:

| Field | Type | Purpose |
|---|---|---|
| `zoomRegistrantId` | varchar (read-only) | The Zoom-side registrant ID, populated by the bridge after successful registrant push. Empty until the registration is pushed |

**Existing fields written by the integration:**

| Field | When written |
|---|---|
| `attendanceStatus` | Set to `Attended` if the contact joined the Webinar at all (any join time recorded), `No-Show` if not. Written once, after the inbound attendance flow runs. Never overwritten |
| `registrationSource` | For walk-in records auto-created by the integration (Section 5.7), set to `Walk-In` |

### 2.3 ZoomIntegrationLog Entity (new)

A new entity that records bridge ↔ Zoom interactions where something went wrong. **Successful operations are not recorded in this entity** — they live in the structured logs (Section 9). This entity exists for operational visibility into failures.

#### Fields

| Field | Type | Description |
|---|---|---|
| `name` | varchar | Auto-generated title (e.g., "Push Registrant — John Smith — Q2 Workshop — 2026-04-30 14:30") |
| `operation` | enum | `createWebinar`, `updateWebinar`, `deleteWebinar`, `addRegistrant`, `cancelRegistrant`, `updateRegistrant`, `getAttendanceReport` |
| `status` | enum | `failedTransient`, `failedPermanent`. (Records are never created with status `pending` or `success`) |
| `parentType` | varchar | Entity type of the linked record (`Event` or `EventRegistration`) |
| `parentId` | varchar | Record ID of the linked record |
| `attemptCount` | int | Number of attempts made before this record was written. Set to the final attempt count when status escalates to `failedPermanent`; updated as retries occur for `failedTransient` |
| `lastAttemptAt` | dateTime | Timestamp of the most recent attempt |
| `failureReason` | text | Human-readable failure message. Sensitive data (tokens, emails, full registrant details) redacted by the bridge's log filter (Section 9) |
| `zoomRequestId` | varchar | Zoom's `x-zm-trackingid` response header value when available — useful for correlating with Zoom support tickets |
| `assignedUser` | link | Defaults to the CRM user who created the parent record |
| `teams` | linkMultiple | Teams with access |

#### Relationships

| Relationship | Type | Target Entity |
|---|---|---|
| `parent` | belongsToParent (polymorphic) | Event or EventRegistration |

#### Notes

- One log record per operation that transitioned to a failure state. A single registrant push that retries three times produces one log record (status `failedTransient`, `attemptCount = 3`); if that record later escalates to permanent, the existing record updates to `failedPermanent` rather than creating a new one
- A standard saved view "Zoom — failed in last 7 days" is provisioned during deployment (Section 7.4)

---

## 3. YAML Configuration Schema

Zoom integration is configured in YAML as part of CRM Builder's deployment configuration. Three blocks: integration behavior, platform connector settings, bridge service additions.

### 3.1 Integration Behavior

```yaml
zoomConfig:
  # Which entity types are integrated
  webinarEntities:
    - Event

  # Filter: which Events get a Zoom Webinar
  eventFilter:
    field: format
    valueIn: [Virtual, Hybrid]

  # When the Webinar gets created
  webinarCreationTrigger:
    statusField: status
    statusFrom: Draft
    statusTo: Scheduled

  # When the Webinar gets deleted
  webinarCancellationTrigger:
    statusField: status
    statusTo: Cancelled

  # When a registrant gets pushed
  registrantPushTrigger:
    onCreate: true                        # Push when EventRegistration is created

  # When a registrant gets cancelled in Zoom
  registrantCancellationTrigger:
    statusField: attendanceStatus
    statusTo: Cancelled

  # Webinar default settings (applied to every Webinar)
  webinarDefaults:
    registrationRequired: true
    approvalType: automatic
    autoRecording: cloud
    practiceSession: true
    hdVideo: true

  # Field sync map: Event field → Zoom Webinar field
  syncableFields:
    - eventField: name
      zoomField: topic
    - eventField: dateStart
      zoomField: start_time
    - eventField: duration
      zoomField: duration
    - eventField: description
      zoomField: agenda
    - eventField: timezone
      zoomField: timezone

  # Contact field sync map (registrant updates)
  registrantSyncableFields:
    - contactField: emailAddress
      zoomField: email
    - contactField: firstName
      zoomField: first_name
    - contactField: lastName
      zoomField: last_name
    - contactField: phoneNumber
      zoomField: phone
```

#### Field reference

- **`webinarEntities`** — declares which entity types this connector handles. Always `Event` in v1.0
- **`eventFilter`** — predicate evaluated against each Event. Only Events matching the filter are integrated. CBM's filter restricts to virtual or hybrid formats
- **`webinarCreationTrigger`** — declares the status transition that fires Webinar creation
- **`webinarCancellationTrigger`** — declares the status transition that fires Webinar deletion. Note: only the Cancelled transition fires deletion. Postponed leaves the Webinar in place (Section 5.6)
- **`registrantPushTrigger.onCreate: true`** — every newly-created EventRegistration is pushed to Zoom
- **`registrantCancellationTrigger`** — declares the EventRegistration field transition that fires Zoom registrant cancellation
- **`webinarDefaults`** — settings passed to Zoom on every Webinar creation. Reflects Issue 21 decisions
- **`syncableFields`** — the five Event fields that auto-sync to the Webinar after creation
- **`registrantSyncableFields`** — the four Contact fields that auto-sync to Zoom registrants when the Contact is updated

All status-trigger blocks use the v1.1 condition-expression syntax (`condition_expression.py`), allowing additional predicates beyond the simple field/value match shown.

### 3.2 Platform Connector Configuration

```yaml
zoomPlatform:
  type: zoom
  authType: oauth_server_to_server
  accountIdEnvVar: ZOOM_ACCOUNT_ID
  clientIdEnvVar: ZOOM_CLIENT_ID
  clientSecretEnvVar: ZOOM_CLIENT_SECRET
  webhookSecretTokenEnvVar: ZOOM_WEBHOOK_SECRET_TOKEN
  defaultHostEmail: ed@cbm.org
  apiBaseUrl: https://api.zoom.us/v2
```

#### Field reference

- **`type`** — always `zoom`. The bridge uses this to load the Zoom connector implementation
- **`authType`** — only `oauth_server_to_server` is supported in v1.0
- **`*EnvVar`** — names of environment variables read at bridge startup. Actual secret values never appear in YAML or any committed file
- **`defaultHostEmail`** — the Zoom user under whose account every Webinar is created. Must be a valid licensed Zoom user in the configured account, holding a Webinar license
- **`apiBaseUrl`** — Zoom's public API URL. Override only for sandbox testing

### 3.3 Bridge Service Additions

The existing `bridgeService` block from the survey integration is extended with Zoom-specific fields:

```yaml
bridgeService:
  # Existing fields from survey integration — unchanged
  host: 0.0.0.0
  port: 8100
  espocrmBaseUrl: https://crm.example.com
  espocrmApiKeyEnvVar: ESPOCRM_API_KEY
  espocrmWebhookSecretEnvVar: ESPOCRM_WEBHOOK_SECRET

  # New Zoom-integration fields
  zoomAttendancePollMinutes: 60
  zoomAttendancePollLookbackHours: 24

  # Failure alerting (covers all connectors)
  alertEmail: events-admin@cbm.org
  alertOnFailureClass: [failedPermanent]
```

#### Field reference

- **`zoomAttendancePollMinutes`** — how often the polling safety-net job runs. Default 60
- **`zoomAttendancePollLookbackHours`** — how far back the polling job looks for Webinars whose `dateEnd` has passed but `attendanceCapturedAt` is null. Default 24
- **`alertEmail`** — destination for failure-class email alerts (covers both Zoom and survey connectors)
- **`alertOnFailureClass`** — list of failure statuses that generate an email alert. `[failedPermanent]` is the recommended default; `failedTransient` is excluded to avoid noise from transient failures that resolve via retry

---

## 4. Bridge Service Architecture

The Bridge Service is the Python middleware that orchestrates all integration flows. Its core architecture (HTTP framework, webhook router, scheduled-task runner, EspoCRM API client, retry logic, secrets loader, structured logging, integration log writer, alerting) is defined in `survey-integration-architecture.md` Section 4 and is shared with that integration.

This document specifies only the **delta** the Zoom integration adds.

### 4.1 Reference to Survey Integration Doc

For shared infrastructure, see `survey-integration-architecture.md`:

- **§4.1 Component Structure** — overall layout of the bridge process, including the connector registry pattern
- **§4.3 API Endpoints** — base webhook endpoint structure and signature-verification middleware
- **§4.4 Scheduled Tasks** — base scheduled-task runner

### 4.2 MeetingConnector Interface

The survey integration defines a `SurveyConnector` abstract interface. Zoom requires a structurally different interface because the underlying flows differ — surveys are "send invitation, capture single response" while webinars are "create session, manage roster, capture per-participant attendance."

A new abstract `MeetingConnector` interface is added to the bridge:

```python
class MeetingConnector(ABC):
    """Abstract interface for video conferencing platform connectors."""

    @abstractmethod
    def create_webinar(self, spec: WebinarSpec) -> WebinarResult:
        """Create a Webinar. Returns Webinar ID, join URL, and registration URL."""

    @abstractmethod
    def update_webinar(self, webinar_id: str, spec: WebinarSpec) -> None:
        """Update an existing Webinar's syncable fields."""

    @abstractmethod
    def delete_webinar(self, webinar_id: str) -> None:
        """Delete a Webinar. Triggers cancellation emails to registrants."""

    @abstractmethod
    def add_registrant(self, webinar_id: str, registrant: RegistrantSpec) -> RegistrantResult:
        """Add a registrant. Returns the platform registrant ID."""

    @abstractmethod
    def update_registrant(self, webinar_id: str, registrant_id: str, registrant: RegistrantSpec) -> None:
        """Update an existing registrant's contact information."""

    @abstractmethod
    def cancel_registrant(self, webinar_id: str, registrant_id: str) -> None:
        """Cancel a registrant. Triggers cancellation email."""

    @abstractmethod
    def get_attendance_report(self, webinar_id: str) -> AttendanceReport:
        """Fetch the post-webinar attendance report."""

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, headers: dict) -> bool:
        """Verify an inbound webhook payload's HMAC signature."""
```

The Zoom connector (`ZoomConnector`) implements this interface. Future connectors (Google Meet for Sessions, etc.) will implement the same interface, allowing bridge-level logic to remain platform-agnostic.

The bridge's connector registry holds connectors of either shape (`SurveyConnector` or `MeetingConnector`), discriminated by interface type.

### 4.3 New Webhook Routes

| Route | Method | Purpose |
|---|---|---|
| `/webhook/zoom-events` | POST | Receives Zoom-side webhook events (`webinar.ended`, etc.). Verifies HMAC signature, persists payload, returns 200, processes asynchronously |
| `/webhook/espocrm/event` | POST | Receives EspoCRM `Event.afterSave` webhooks. Used by Sections 5.1, 5.2, 5.5, 5.6 |
| `/webhook/espocrm/event-registration` | POST | Receives EspoCRM `EventRegistration.afterSave` webhooks. Used by Sections 5.3, 5.4 |
| `/webhook/espocrm/contact` | POST | Receives EspoCRM `Contact.afterSave` webhooks for registrant-info sync. Used by Section 5.4 |

All four routes share the same signature-verification middleware from the survey integration.

### 4.4 Scheduled Task: Attendance Polling Safety Net

A new scheduled task is added to the bridge's task runner:

- **Task name:** `zoom_attendance_poll`
- **Cadence:** every `zoomAttendancePollMinutes` (default 60) minutes
- **Logic:**
  1. Query EspoCRM for Events where `zoomWebinarId IS NOT NULL` AND `dateEnd < now` AND `dateEnd >= now - zoomAttendancePollLookbackHours` AND `attendanceCapturedAt IS NULL`
  2. For each match, invoke the inbound attendance flow (Section 5.7)
  3. Log every poll cycle's match count to structured logs; write a `ZoomIntegrationLog` entry only when an action fails (avoids log spam on idle cycles)

This task is idempotent with the `webinar.ended` webhook flow: the first to set `attendanceCapturedAt` wins; the second invocation finds it already set and exits as a logged no-op.

### 4.5 Local Persistent Queues

The bridge maintains two SQLite queues in its data directory:

**`pending_inbound.db`** — already used by the survey integration. Zoom integration uses the same database. Schema: `(id, payload_json, source, received_at, attempt_count, last_attempt_at, last_error)`. On any inbound webhook, the bridge persists the raw payload, returns 200 to the sender, and a background worker drains the queue with exponential backoff.

**`registrant_backlog.db`** — new for Zoom integration. Schema: `(id, event_registration_id, event_id, queued_at)`. Holds EventRegistration records created against Events that don't yet have a Zoom Webinar (Section 5.5). Drained automatically when the parent Event's Webinar is created.

Both databases live in `/var/lib/bridge/data/` and persist across bridge restarts.

---

## 5. Integration Flows

This section describes each flow end to end. Seven flows total: Webinar creation, Event update sync, registrant push, Contact update sync, registration cancellation, Event cancellation, and inbound attendance capture.

### 5.1 Webinar Creation (Draft → Scheduled)

**Trigger:** EspoCRM fires `Event.afterSave`. Bridge detects a status transition from Draft to Scheduled on an Event matching the `eventFilter`.

**Sequence:**

1. CRM user transitions an Event from Draft to Scheduled and saves
2. EspoCRM fires `Event.afterSave` webhook to `/webhook/espocrm/event`
3. Bridge verifies the webhook signature; rejects on failure
4. Bridge fetches the full Event record from the EspoCRM REST API
5. Bridge evaluates the `eventFilter`. If `format` is not `Virtual` or `Hybrid`, exits silently
6. Bridge evaluates the `webinarCreationTrigger`. If the status transition is not Draft → Scheduled, exits
7. If `event.zoomWebinarId IS NOT NULL`, exits (already provisioned — defensive guard against duplicate webhooks)
8. Bridge calls `ZoomConnector.create_webinar(spec)` with the resolved settings (host email from `defaultHostEmail`, settings from `webinarDefaults`, name/dateStart/duration/description/timezone from the Event)
9. Connector hits Zoom API: `POST /users/{defaultHostEmail}/webinars`
10. On success, connector returns `(webinar_id, join_url, registration_url)`
11. Bridge PATCHes the Event record in EspoCRM with `zoomWebinarId`, `zoomHostEmail`, `virtualMeetingUrl`, `registrationUrl`, `zoomLastSyncedAt`
12. Bridge invokes the registrant backlog flush (Section 5.5)

**Failure handling:** Per Section 6 — transient retried with exponential backoff; permanent escalates to `ZoomIntegrationLog` entry and email alert.

### 5.2 Event Update Sync

**Trigger:** EspoCRM fires `Event.afterSave` for an UPDATE on an Event with non-null `zoomWebinarId`.

**Always-on, no opt-in.** Once an Event has a Zoom Webinar, the integration takes ownership of keeping Zoom synchronized.

**Synced fields (per `syncableFields` in YAML):**

| CRM Event field | Zoom Webinar field |
|---|---|
| `name` | `topic` |
| `dateStart` | `start_time` |
| `duration` | `duration` |
| `description` | `agenda` |
| `timezone` | `timezone` |

**Sequence:**

1. Bridge receives `Event.afterSave` webhook for an UPDATE
2. Bridge fetches the Event. Skips if `zoomWebinarId IS NULL`
3. Bridge compares the syncable-field values against `zoomLastSyncedAt`-era state (cached locally or read via Zoom GET if no cache)
4. If any syncable field has changed, bridge calls `ZoomConnector.update_webinar(webinar_id, spec)`
5. Connector hits `PATCH /webinars/{id}` with only the changed fields
6. On success, bridge updates `zoomLastSyncedAt` on the Event

**Not synced:** all fields not in the `syncableFields` map. In particular: `format` (CRM-only concept), `topic` (CBM-side classification, not the Zoom topic), `assignedUser` (CRM-internal), and `zoomHostEmail` (connector-level setting, not per-record).

### 5.3 Registrant Push

**Trigger:** EspoCRM fires `EventRegistration.afterSave` for a CREATE.

**Sequence:**

1. CRM user creates an EventRegistration record
2. EspoCRM fires `EventRegistration.afterSave` to `/webhook/espocrm/event-registration`
3. Bridge fetches the EventRegistration and its parent Event and Contact
4. Bridge evaluates whether the parent Event matches `eventFilter`. If not, exits
5. **If parent Event has non-null `zoomWebinarId`:** proceed to step 6
6. **If parent Event has null `zoomWebinarId`:** persist this EventRegistration in `registrant_backlog.db` keyed by `event_id`, and exit. Will be flushed by Section 5.1 when the Webinar is created
7. Bridge calls `ZoomConnector.add_registrant(webinar_id, registrant)` with the Contact's email, first_name, last_name, phone
8. Connector hits `POST /webinars/{id}/registrants`
9. On success, connector returns `(registrant_id, join_url)`
10. Bridge PATCHes the EventRegistration with `zoomRegistrantId`
11. Zoom sends the registrant a confirmation email with their unique join URL

**Backlog flush logic:** When a Webinar is successfully created (Section 5.1 step 12), the bridge queries `registrant_backlog.db` for all entries with the matching `event_id`, processes each through steps 7–10, and deletes the backlog entries on success. Failed entries remain queued for the next retry cycle.

### 5.4 Contact Update Sync (registrant info)

**Trigger:** EspoCRM fires `Contact.afterSave` for an UPDATE that changed `emailAddress`, `firstName`, `lastName`, or `phoneNumber`.

**Sequence:**

1. Bridge receives `Contact.afterSave` webhook for an UPDATE
2. Bridge checks whether any of the four registrant-syncable fields changed; exits if not
3. Bridge queries EspoCRM for all EventRegistration records where:
   - `contact = thisContact` AND
   - `zoomRegistrantId IS NOT NULL` AND
   - parent Event's `dateEnd >= now` (only upcoming Webinars matter)
   - parent Event's `status NOT IN [Cancelled, Completed]`
4. For each matching EventRegistration, bridge calls `ZoomConnector.update_registrant(webinar_id, zoomRegistrantId, registrant)`
5. Connector hits Zoom's update-registrant endpoint with the changed fields

**Important:** A single Contact change can fan out to multiple `update_registrant` calls if the Contact is registered for multiple upcoming Webinars. Each call is retried independently per Section 6.

### 5.5 Registration Cancellation

**Trigger:** EspoCRM fires `EventRegistration.afterSave` and bridge detects `attendanceStatus` transitioned to `Cancelled` on a record with non-null `zoomRegistrantId`.

**Sequence:**

1. Bridge receives the webhook
2. Bridge evaluates the `registrantCancellationTrigger`. If the transition is not to `Cancelled`, exits
3. If `eventRegistration.zoomRegistrantId IS NULL`, exits (registrant was never pushed to Zoom)
4. Bridge calls `ZoomConnector.cancel_registrant(webinar_id, registrant_id)`
5. Connector hits `PUT /webinars/{id}/registrants/status` with `action: cancel`
6. Zoom sends the registrant a cancellation email and removes them from the Webinar roster

**Note:** EventRegistration records are never deleted in CBM (per the entity PRD). The integration handles only the cancellation transition, not record deletion.

### 5.6 Event Cancellation

**Trigger:** EspoCRM fires `Event.afterSave` and bridge detects `status` transitioned to `Cancelled` on an Event with non-null `zoomWebinarId`.

**Sequence:**

1. Bridge evaluates the `webinarCancellationTrigger`. If the transition is not to `Cancelled`, exits
2. If `event.zoomWebinarId IS NULL`, exits (Webinar was never created)
3. If `event.dateEnd < now`, exits (Webinar already past — deleting is meaningless and may delete preserved attendance data on Zoom's side)
4. Bridge calls `ZoomConnector.delete_webinar(webinar_id)`
5. Connector hits `DELETE /webinars/{id}`
6. Zoom sends cancellation emails to all registrants automatically
7. Bridge does NOT clear `zoomWebinarId`, `virtualMeetingUrl`, or `registrationUrl` on the Event — they remain for audit/historical reference

**Postponed status:** The integration does NOT delete the Webinar on Postponed status. The Webinar stays in place. When the Event later transitions back to Scheduled with a new date, the auto-sync flow (Section 5.2) updates the Webinar's `start_time` and Zoom resends calendar invites with the new time.

### 5.7 Inbound Attendance Capture

**Trigger (primary):** Zoom fires `webinar.ended` to `/webhook/zoom-events`.
**Trigger (safety net):** Polling job (Section 4.4) identifies an Event whose attendance has not been captured.

**Sequence:**

1. Bridge receives the trigger
2. **(Webhook path)** Bridge verifies HMAC signature; rejects on failure. Persists payload to `pending_inbound.db`. Returns 200 to Zoom
3. Background worker picks up the payload
4. Bridge looks up the Event by `zoomWebinarId`. If `attendanceCapturedAt IS NOT NULL`, exits as no-op (idempotency)
5. Bridge calls `ZoomConnector.get_attendance_report(webinar_id)`
6. Connector hits `GET /report/webinars/{id}/participants`, handles pagination (Zoom returns up to 300 per page), returns combined `AttendanceReport`
7. For each participant in the report:
   - Bridge looks up an EventRegistration matching this Event by participant email (case-insensitive comparison against `Contact.emailAddress` via the `contact` link)
   - **Match found:** Bridge sets the EventRegistration's `attendanceStatus = Attended` (write-once: skips if already populated)
   - **No match:** Bridge searches Contacts by email (case-insensitive)
     - **Contact found:** Bridge creates a new EventRegistration linking the Event and the Contact, with `registrationSource = Walk-In` and `attendanceStatus = Attended`
     - **No Contact found:** Bridge ignores this attendance entry (Issue 10 decision — walk-ins from non-Contacts are noise)
8. For every EventRegistration linked to this Event with `attendanceStatus IN [Registered]` (i.e., still pending and not in the attendance report), bridge sets `attendanceStatus = No-Show`
9. Bridge sets `attendanceCapturedAt = now` on the Event
10. Bridge marks the inbound queue entry as processed

**Idempotency:** `attendanceCapturedAt` is the single source of truth for "this Event's attendance has been captured." Steps 4 and 9 together ensure that webhook + polling never produce duplicate writes. EventRegistration writes are also write-once on `attendanceStatus`.

**Pagination handling:** Zoom's report endpoints return up to 300 participants per page. The connector accumulates all pages before returning. If pagination fails partway through, the entire operation is treated as a transient failure and retried from the first page (Zoom's reports are stable post-Webinar, so re-fetching is safe).

---

## 6. Failure Handling and Retry Policy

### 6.1 Outbound API Call Failures (bridge → Zoom)

**Transient failures** (network timeout, 502/503/504, 429 rate limit):

- Retry with exponential backoff at 0s, 30s, 2 min, 10 min (4 attempts total)
- After the 4th failure, escalate to `failedPermanent`

**Permanent failures** (400 bad request, 404 not found):

- No retry. Log immediately as `failedPermanent`

**Auth failures** (401 with "invalid token" or "expired token"):

- Connector clears its cached access token, fetches a new one via S2S OAuth, retries the original call exactly once
- If the second attempt also returns 401, escalate to `failedPermanent` (likely credential rotation or revocation)
- This refresh-and-retry counts as one attempt within the transient retry budget, not an additional retry

### 6.2 Inbound Webhook Failures (Zoom → bridge)

**Bridge unavailable:** Zoom retries on its own per Zoom's documented retry schedule. Once the bridge is healthy, Zoom's retry will deliver. The polling safety net (Section 4.4) catches anything Zoom permanently gives up on.

**Signature verification failure:** Bridge returns 401 and logs the rejected payload metadata (no body content). Zoom retries; if signatures continue failing, this is a credential mismatch and an operator must investigate via the alert pipeline.

**Bridge accepts but processing fails:** Bridge persists the raw payload to `pending_inbound.db`, returns 200 (so Zoom doesn't retry), and a background worker drains the queue with exponential backoff against EspoCRM. After 7 days of failed drain attempts, the entry is escalated to `failedPermanent`.

### 6.3 Failure Visibility (three layers)

**Layer 1 — Structured logs.** Every API attempt, retry, and final outcome written to JSON logs in `/var/log/bridge/`. Searchable by `eventId`, `webinarId`, `failureClass`, etc. Always on.

**Layer 2 — `ZoomIntegrationLog` entity in the CRM.** Records failures only (Issue 18 decision). One log record per failed operation. Updated on each retry; status escalates to `failedPermanent` after retry budget exhausted. Visible via the standard saved view.

**Layer 3 — Email alerts on permanent failures.** When an operation enters `failedPermanent` state, the bridge sends an email to `bridgeService.alertEmail` with the operation, parent record, failure reason, and link to the `ZoomIntegrationLog` record in the CRM.

---

## 7. EspoCRM Configuration

### 7.1 Webhook Registration

CRM Builder registers the following EspoCRM webhooks during deployment:

| Webhook | Entity | Event | Bridge Endpoint |
|---|---|---|---|
| Event-Save | Event | afterSave | `/webhook/espocrm/event` |
| EventRegistration-Save | EventRegistration | afterSave | `/webhook/espocrm/event-registration` |
| Contact-Save | Contact | afterSave | `/webhook/espocrm/contact` |

All webhooks use HMAC signing with `ESPOCRM_WEBHOOK_SECRET`. The bridge rejects webhooks with invalid signatures.

There are no `beforeRemove` or `afterRemove` webhook registrations — the integration relies on the entity-level "never delete" policy.

### 7.2 API User for Bridge Service

CRM Builder provisions a dedicated API user in EspoCRM:

- **Username:** `zoom-bridge`
- **Auth:** API key, stored in `ESPOCRM_API_KEY` env var
- **Permissions:**
  - Read on Event, Contact, EventRegistration
  - Edit on Event (for Zoom-managed fields only — enforced via field-level ACL)
  - Edit on EventRegistration (for `zoomRegistrantId`, `attendanceStatus`)
  - Create on EventRegistration (for walk-in records from Section 5.7)
  - Create + Edit on `ZoomIntegrationLog`

### 7.3 Custom Buttons and UI Elements

**None in v1.0.** Every flow is automatic and triggered by status transitions or record creation. There is no manual-trigger button on Event or EventRegistration.

### 7.4 Saved Views

CRM Builder provisions these saved views:

| Entity | View Name | Filter |
|---|---|---|
| ZoomIntegrationLog | Zoom — failures in last 7 days | `lastAttemptAt >= today-7d` (entity contains failures only) |
| ZoomIntegrationLog | Zoom — permanent failures (open) | `status = failedPermanent` |
| EventRegistration | Walk-Ins from Zoom (last 30 days) | `registrationSource = Walk-In AND createdAt >= today-30d` |

---

## 8. Deployment Architecture

### 8.1 Component Deployment

The Bridge Service runs as a single Docker container, shared across all integrations (survey + Zoom + future):

- **Container image:** `crmbuilder-bridge:{version}`
- **Connector activation:** Per-deployment YAML controls which connectors load. A deployment with only `zoomConfig` set loads only the Zoom connector; with both `surveyConfig` and `zoomConfig`, both load

**Persistent volumes:**

- `/var/lib/bridge/data/` — `pending_inbound.db` (shared), `registrant_backlog.db` (Zoom-specific)
- `/var/log/bridge/` — structured log output

### 8.2 Network Requirements

| Source | Destination | Protocol | Purpose |
|---|---|---|---|
| EspoCRM | Bridge:8100 | HTTPS | Outbound entity webhooks |
| Zoom | Bridge:8100 | HTTPS | Inbound `webinar.ended` webhook |
| Bridge | api.zoom.us:443 | HTTPS | Zoom API calls |
| Bridge | zoom.us:443 | HTTPS | OAuth token endpoint |
| Bridge | EspoCRM | HTTPS | EspoCRM REST API |

The bridge MUST be deployed at a publicly reachable hostname with TLS for Zoom webhook delivery. If EspoCRM and the bridge are co-located, EspoCRM-to-bridge traffic can use loopback, but Zoom-to-bridge still requires a public DNS entry and TLS termination.

### 8.3 Environment Variables

Complete env-var list for a deployment with Zoom integration enabled:

| Variable | Purpose |
|---|---|
| `ESPOCRM_API_KEY` | Bridge's API key for EspoCRM |
| `ESPOCRM_WEBHOOK_SECRET` | HMAC shared secret for EspoCRM webhooks |
| `ZOOM_ACCOUNT_ID` | Zoom S2S account ID |
| `ZOOM_CLIENT_ID` | Zoom S2S client ID |
| `ZOOM_CLIENT_SECRET` | Zoom S2S client secret |
| `ZOOM_WEBHOOK_SECRET_TOKEN` | Zoom webhook HMAC secret |

### 8.4 CRM Builder Provisioning Sequence

When a deployment includes `zoomConfig`, CRM Builder executes the following after standard entity/field/relationship provisioning:

1. Provision the new Zoom-related fields on Event (Section 2.1)
2. Provision the new Zoom-related fields on EventRegistration (Section 2.2)
3. Provision the `ZoomIntegrationLog` entity, fields, relationships, and saved views
4. Provision the Walk-Ins saved view on EventRegistration
5. Provision the API user `zoom-bridge` with field-level ACLs
6. Register the three EspoCRM webhooks (Section 7.1)
7. Health-check: bridge reachable, responds to `/health`
8. Validate the Zoom connector: `GET /users/{defaultHostEmail}` succeeds — fails the deployment otherwise

---

## 9. Security Considerations

### 9.1 Server-to-Server OAuth Credentials

S2S credentials (`accountId`, `clientId`, `clientSecret`) grant API access to the entire Zoom account, including the ability to create, modify, and delete any Webinar, manage registrants, and read user information.

- Credentials are stored only in environment variables on the bridge service host. Never in YAML, never in source control, never in logs
- Bridge process must run under a user account whose process environment is not readable by other users
- Rotation requires environment update plus bridge restart (~10s downtime). Webhook deliveries during downtime are retried automatically by Zoom

### 9.2 Token Lifecycle

- On each API call, the bridge checks its cached S2S access token's expiry timestamp
- If within 50 seconds of expiry (or null), bridge POSTs to `https://zoom.us/oauth/token` with `grant_type=account_credentials&account_id={accountId}` and HTTP Basic auth
- Zoom returns an access token with `expires_in: 3600`
- Token cached in memory only; never persisted

### 9.3 Webhook Authentication

All inbound webhooks (EspoCRM and Zoom) authenticated via HMAC-SHA256:

- **EspoCRM webhooks:** signed with `ESPOCRM_WEBHOOK_SECRET`
- **Zoom webhooks:** signed with `ZOOM_WEBHOOK_SECRET_TOKEN` per Zoom's documented HMAC scheme. Verified by `ZoomConnector.verify_webhook_signature` before payload parsing

Bridge rejects unsigned or invalidly-signed payloads with HTTP 401.

### 9.4 Credential Rotation

Recommended cadence: every 90 days. The bridge does not enforce rotation — operators are responsible per organizational policy.

### 9.5 Credential and PII Masking in Logs

The bridge's structured logger applies a redaction filter:

- Substring matches against `ZOOM_CLIENT_SECRET`, `ZOOM_WEBHOOK_SECRET_TOKEN`, `ESPOCRM_API_KEY`, `ESPOCRM_WEBHOOK_SECRET` values replaced with `[REDACTED]`
- 32-byte hex tokens (heuristic for Zoom access tokens) replaced with `[REDACTED]`
- `Authorization` headers in logged HTTP transactions replaced with `Authorization: [REDACTED]`
- Registrant emails and names redacted from `failureReason` strings written to `ZoomIntegrationLog`

### 9.6 Registrant PII Handling

Attendance reports and registrant payloads contain PII (email, name, phone). The bridge handles this with the following constraints:

- Registrant data is never persisted by the bridge except in transit through `pending_inbound.db` (local disk, not network-accessible)
- Attendance reports fetched from Zoom are processed in memory and written directly to EspoCRM; raw payloads not retained
- Walk-in EventRegistrations created by the bridge inherit standard EventRegistration ACLs
- `ZoomIntegrationLog.failureReason` redacts emails and names

---

## 10. Future Considerations and Downstream Work

### 10.1 Downstream Work — Required Before This Integration Can Be Deployed

This PRD assumes new fields exist on Event, EventRegistration, and a new `ZoomIntegrationLog` entity. The following CBM-repo entity PRD revisions are required:

- **`PRDs/entities/Event-Entity-PRD.docx`** revised to add `zoomWebinarId`, `zoomHostEmail`, `attendanceCapturedAt`, `zoomLastSyncedAt`. Existing `virtualMeetingUrl` and `registrationUrl` fields' "system-populated" notes updated to specify the Zoom integration as the populating system
- **`PRDs/entities/EventRegistration-Entity-PRD.docx`** revised to add `zoomRegistrantId` and to specify that the integration writes `attendanceStatus` (`Attended` | `No-Show`) and creates Walk-In records with `registrationSource = Walk-In`
- **New entity PRD: `PRDs/entities/ZoomIntegrationLog-Entity-PRD.docx`** drafted per Section 2.3

These revisions should land in a separate session before this Zoom PRD is built.

### 10.2 Bridge Service Architecture Extraction

The Bridge Service is now shared between two integration architectures (survey and Zoom). Currently the shared infrastructure documentation lives in `survey-integration-architecture.md` Section 4. A future refactor would extract this content into `bridge-service-architecture.md`, with both integration documents referencing it. Deferred until a third integration joins.

### 10.3 Recording Retrieval

Zoom's auto-recording (`autoRecording: cloud`) is enabled in v1.0 but the integration does not retrieve recording links. A future revision could:

- Listen for `recording.completed` webhook
- Populate the Event's existing `recordingUrl` field with the Zoom Cloud Recording URL

Storage costs and retention policy should be decided before this is implemented.

### 10.4 Webinar Q&A and Poll Capture

Zoom Webinar reports include Q&A transcripts and poll responses. v1.0 ignores both. Useful for after-action reporting; out of scope here.

### 10.5 Granular Attendance Fields

Issue 9 chose coarse-grained attendance (`Attended` | `No-Show`). If CBM later wants engagement-quality reporting (minutes attended, attendance percent for "must attend ≥80%" policies), these fields can be added to EventRegistration in a future revision without changing the integration architecture.

### 10.6 Zoom Meetings for Sessions (MN domain)

The `MeetingConnector` interface (Section 4.2) already supports the operations needed for Zoom Meetings. A future PRD will extend this architecture to cover mentoring Sessions, including the Google Meet alternative for Sessions.

### 10.7 Generalized Integration Log

`ZoomIntegrationLog` could be merged with a survey-side equivalent into a single `IntegrationLog` entity discriminated by `connectorType`. Same factoring concern as 10.2 — deferred to a coordinated refactor when the third integration arrives.
