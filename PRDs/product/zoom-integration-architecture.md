# Zoom Integration Architecture

**CRM Builder — Zoom Meeting and Webinar Platform Integration**

Last Updated: 04-30-26 14:30

---

## Revision Control

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0 | 04-30-26 14:30 | Doug Bower | Initial draft. Defines bidirectional Zoom integration covering meeting/webinar creation, registrant sync, and attendance capture, on the shared Bridge Service from `survey-integration-architecture.md`. |

### Change Log

- **1.0 (04-30-26):** Initial draft. Establishes ten-section architecture covering both Zoom Meetings and Zoom Webinars (declared per event type), Server-to-Server OAuth authentication against a shared Zoom account, declarative trigger rules in YAML (`onCreate`, `statusChange`, `manual`) for meeting creation and registrant push, always-on update sync between Event records and Zoom sessions, webhook-plus-polling-safety-net inbound attendance capture, walk-in reconciliation, opt-in cancellation behavior, and three-layer failure visibility. Connector pattern extends the existing Bridge Service from the survey integration via a new `MeetingConnector` interface — no second bridge service.

---

## 1. Overview

This document defines the architecture for integrating Zoom (Meetings and Webinars) with EspoCRM deployments managed by CRM Builder. The design provides a reusable, YAML-driven pattern that automates three flows:

1. Creating Zoom sessions when Events are created or transition to a published state in the CRM
2. Pushing registered Contacts from the CRM to the Zoom session as registrants
3. Capturing attendance back from Zoom into the CRM after the session ends

The integration runs on the same **Bridge Service** introduced in `survey-integration-architecture.md` (Section 4) — the Zoom integration adds a new connector type rather than a parallel deployment.

### 1.1 Goals

- Enable any CRM event coordinator to create an Event record and have the corresponding Zoom Meeting or Webinar provisioned automatically, without that coordinator needing a Zoom account of their own
- Automatically register contacts in Zoom when they register for an Event in the CRM, including handling registrations created before the Zoom session is provisioned
- Automatically capture attendance data (joined, left, total minutes, attendance percent) back to EventRegistration records once the Zoom session ends
- Reconcile walk-in attendees (people who joined via Zoom without a pre-existing CRM registration) against existing Contact records, creating placeholder Contacts where no match is found
- Keep the CRM data model meeting-platform-agnostic so the Zoom connector could be replaced or supplemented by Google Meet, Microsoft Teams, or another provider through the same `MeetingConnector` interface
- Make the entire configuration declarable in YAML for CRM Builder deployments, with no Zoom-specific code or credentials in client-implementation YAML files
- Reuse the Bridge Service infrastructure (HTTP listener, scheduled tasks, retry logic, EspoCRM client, alerting, integration logging) defined for the survey integration

### 1.2 System Components

| Component | Role |
|---|---|
| **EspoCRM** | Core CRM. Hosts the Event, EventRegistration, and ZoomIntegrationLog entities; fires webhooks on entity create/update/delete events; provides the REST API used by the bridge for record CRUD |
| **Zoom** | External meeting and webinar platform. Hosts meeting/webinar sessions, manages registrants, generates attendance reports, fires session-lifecycle webhooks. Single shared Zoom account for all events |
| **Bridge Service** | Python middleware (shared with survey integration). Listens for triggers from EspoCRM and Zoom, orchestrates provisioning, registrant sync, and attendance capture between the two systems |
| **CRM Builder** | Deployment tool. Provisions the Event/EventRegistration/ZoomIntegrationLog entities, registers EspoCRM webhooks, configures the Zoom connector in the bridge service from YAML |

### 1.3 Reference Implementation

The first deployment of this architecture is for Cleveland Business Mentors (CBM), a nonprofit mentoring organization. CBM's event use cases under the Community Relations (CR) domain include:

- **Workshops** — interactive Zoom Meetings, registration required, auto-provisioned on Event creation, capacity ~100
- **Networking Events** — interactive Zoom Meetings, registration required, auto-provisioned on Event status transition to "Published" (allows draft/edit window)
- **Annual Gala** — Zoom Webinar (large-audience broadcast), manual approval of registrants, auto-provisioned on status transition to "Published"
- **Internal Staff Meetings** — Zoom Meeting, no registration, manual provisioning only

A single shared Zoom account (`events@cbm.org`) hosts all sessions. The Zoom Webinar license attaches to a separate Zoom user (`ed@cbm.org`); webinar-class events override the default host at the event-type level.

---

## 2. Data Model

### 2.1 Event Entity Extensions

The Event entity is owned by the Community Relations domain (or whichever domain the implementation places event management under) and is documented in that domain's Entity PRD. This integration adds the following Zoom-specific fields:

#### Zoom-Integration Fields

| Field | Type | Description |
|---|---|---|
| `eventType` | enum | References the event type key from YAML config (e.g., `workshop`, `gala`, `networking`, `internal_meeting`). Drives all per-type Zoom behavior |
| `zoomMeetingId` | varchar | The Zoom meeting or webinar ID, populated by the bridge after successful provisioning. Empty until the create-trigger fires |
| `zoomMeetingType` | enum | `meeting` or `webinar`. Populated by the bridge from the resolved `zoomProductType` of the event type. Read-only in the CRM UI |
| `zoomJoinUrl` | url | The single join URL for the session. For webinars and meetings with registration enabled, this is the host's join URL — registrants receive their own per-registrant URLs from Zoom directly |
| `zoomRegistrationUrl` | url | Public registration URL. Populated when `registrationRequired: true` for the event type. Can be linked from CRM emails or marketing pages |
| `zoomHostEmail` | varchar | The Zoom user under whose account the session was created. Populated by the bridge from connector config; allows attendance reports to be matched back to the correct Zoom user |
| `attendanceCapturedAt` | dateTime | Set by the bridge when the inbound attendance flow completes successfully. Acts as the idempotency key for inbound webhook + polling deduplication |
| `zoomLastSyncedAt` | dateTime | Set by the bridge after every successful outbound update sync (Section 5.2). Allows operators to see when the Zoom session was last reconciled with the CRM record |

#### Notes

- `zoomMeetingId` and `attendanceCapturedAt` are managed exclusively by the bridge. CRM users have read-only access to these fields in the UI.
- `eventType` must be set before the create-trigger evaluates; an Event with `eventType` null is ignored by the integration.
- Existing Event-entity fields (`name`, `dateStart`, `dateEnd`, `description`, `timezone`) are read by the bridge but never written. They are the source of truth for the syncable-fields list in Section 5.2.

### 2.2 EventRegistration Entity Extensions

The EventRegistration entity links a Contact to an Event and is owned by the same domain as Event. This integration adds the following attendance fields:

#### Attendance Fields

| Field | Type | Description |
|---|---|---|
| `registrationStatus` | enum | Pre-existing field on EventRegistration. Values include `Pending`, `Approved`, `Cancelled`. The bridge reads this field to evaluate registrant-push trigger rules |
| `registrationSource` | enum | `Direct` (created via CRM by a user), `WalkIn` (created by the bridge from a Zoom attendance report for a participant with no pre-existing EventRegistration). Populated on creation, never updated |
| `zoomRegistrantId` | varchar | The Zoom-side registrant ID, populated by the bridge after successful registrant push. Empty until the registrant-trigger fires |
| `attended` | bool | True if the bridge captured any join time for this registrant in the post-meeting attendance report |
| `attendanceMinutes` | int | Total minutes attended, summed across all join/leave sessions. Zero if `attended` is false |
| `firstJoinedAt` | dateTime | First join timestamp from Zoom's attendance report |
| `lastLeftAt` | dateTime | Last leave timestamp from Zoom's attendance report |
| `attendancePercent` | decimal | `attendanceMinutes / meetingDurationMinutes * 100`, rounded to one decimal place. Useful for "must attend ≥80% to count" reporting policies |

#### Notes

- All attendance fields are write-once. The bridge never overwrites them. If `attendanceCapturedAt` is already set on the parent Event, repeated inbound triggers are no-ops.
- `registrationSource = WalkIn` records are flagged in saved views for manual de-duplication review by the CRM admin (see Section 6.7 for walk-in reconciliation logic).
- `attendancePercent` can exceed 100 in edge cases where a participant rejoins after the host has extended the meeting; the bridge caps the value at 100.

### 2.3 ZoomIntegrationLog Entity

A new entity that records every bridge ↔ Zoom interaction for operational visibility. Used by the failure-handling architecture (Section 6 of this doc, originally Q6c).

#### Fields

| Field | Type | Description |
|---|---|---|
| `name` | varchar | Auto-generated descriptive title (e.g., "Create Zoom Meeting — Workshop on Q2 Marketing — 2026-04-30 14:30") |
| `operation` | enum | `createSession`, `updateSession`, `deleteSession`, `addRegistrant`, `cancelRegistrant`, `getAttendanceReport` |
| `status` | enum | `pending`, `success`, `failedTransient`, `failedPermanent` |
| `parentType` | varchar | Entity type of the linked record (`Event` or `EventRegistration`) |
| `parentId` | varchar | Record ID of the linked record |
| `attemptCount` | int | Number of attempts made for this operation. Increments on each retry |
| `lastAttemptAt` | dateTime | Timestamp of the most recent attempt |
| `failureReason` | text | Human-readable failure message. Populated when `status` is `failedTransient` or `failedPermanent`. Sensitive data (tokens, registrant emails) redacted |
| `zoomRequestId` | varchar | Zoom's `x-zm-trackingid` response header, when available — useful for correlating with Zoom support tickets |
| `assignedUser` | link | Defaults to the CRM user who created the parent record, for assignment of follow-up |
| `teams` | linkMultiple | Teams with access to this log entry |

#### Relationships

| Relationship | Type | Target Entity | Description |
|---|---|---|---|
| `parent` | belongsToParent | (polymorphic) | The Event or EventRegistration this log entry pertains to |

#### Notes

- One log record per operation attempt. A single registrant push that retries three times produces three log entries, all linked to the same EventRegistration parent.
- A saved view "Zoom — failed in last 7 days" (filtered on `status IN [failedTransient, failedPermanent]` and `lastAttemptAt >= today-7d`) is part of the standard CRM Builder configuration for any deployment with Zoom enabled (see Section 7.4).
- This entity could be generalized in a future revision to a single `IntegrationLog` shared with the survey integration. Flagged in Section 10.

---

## 3. YAML Configuration Schema

Zoom integration is configured in YAML as part of CRM Builder's deployment configuration. The configuration has three sections: event type definitions, platform connector settings, and bridge service additions.

### 3.1 Event Type Configuration

```yaml
zoomConfig:
  # Which entity types can have Zoom sessions attached
  zoomableEntities:
    - Event

  # Event type definitions — one entry per category of event
  eventTypes:
    workshop:
      name: "Workshop"
      zoomProductType: meeting           # meeting | webinar
      capacity: 100
      settings:
        registrationRequired: true
        approvalType: automatic          # automatic | manual
        waitingRoom: false
        muteOnEntry: true
        autoRecording: cloud             # none | local | cloud

      # When to create the Zoom session
      triggerRules:
        - parentType: Event
          trigger: onCreate              # onCreate | statusChange | manual
          condition:
            field: eventType
            value: workshop

      # When to push a registrant to Zoom
      registrantTriggerRules:
        - trigger: onCreate              # onCreate | statusChange | manual

      # When (if ever) to delete the Zoom session
      cancellationRules:
        - trigger: statusChange
          statusField: status
          statusValue: Cancelled
          action: deleteZoomSession

    networking:
      name: "Networking Event"
      zoomProductType: meeting
      capacity: 250
      settings:
        registrationRequired: true
        approvalType: automatic
      triggerRules:
        - parentType: Event
          trigger: statusChange
          statusField: status
          statusValue: Published
          condition:
            field: eventType
            value: networking
      registrantTriggerRules:
        - trigger: onCreate
      cancellationRules:
        - trigger: statusChange
          statusField: status
          statusValue: Cancelled
          action: deleteZoomSession

    gala:
      name: "Annual Gala"
      zoomProductType: webinar
      capacity: 1000
      hostEmail: "ed@cbm.org"            # Override default host (webinar license)
      settings:
        registrationRequired: true
        approvalType: manual             # Registrants must be approved before push
      triggerRules:
        - parentType: Event
          trigger: statusChange
          statusField: status
          statusValue: Published
          condition:
            field: eventType
            value: gala
      registrantTriggerRules:
        - trigger: statusChange
          statusField: registrationStatus
          statusValue: Approved
      cancellationRules:
        - trigger: statusChange
          statusField: status
          statusValue: Cancelled
          action: deleteZoomSession

    internal_meeting:
      name: "Internal Staff Meeting"
      zoomProductType: meeting
      capacity: 50
      settings:
        registrationRequired: false
      triggerRules:
        - parentType: Event
          trigger: manual                # Only fires on explicit button click
          condition:
            field: eventType
            value: internal_meeting
      # registrantTriggerRules omitted — no registration
      # cancellationRules omitted — manual deletion only
```

#### Field reference

- **`zoomProductType`** — `meeting` or `webinar`. Determines which Zoom API surface the connector uses (`/meetings/*` vs `/webinars/*`).
- **`capacity`** — informational only; enforced by the Zoom plan, not by the bridge.
- **`hostEmail`** — optional. When set, overrides `zoomPlatform.defaultHostEmail` for this event type. Required when the event type uses a feature only licensed to a specific Zoom user (typically Webinar).
- **`settings`** — passed through to Zoom's create-meeting/create-webinar API. See Section 6.5 for the full list of settings the connector supports.
- **`triggerRules[*].trigger`** — `onCreate`, `statusChange`, or `manual`. Determines when the Zoom session is created.
- **`registrantTriggerRules[*].trigger`** — `onCreate`, `statusChange`, or `manual`. Determines when an EventRegistration triggers a registrant push to Zoom. Can be omitted if `registrationRequired: false`.
- **`cancellationRules`** — opt-in. If omitted, no automatic Zoom deletion happens when the Event is cancelled; operator must delete manually in Zoom. Only `action: deleteZoomSession` is supported in v1.0.

All `condition` and `statusValue` blocks use the v1.1 condition-expression syntax (`condition_expression.py`), allowing complex predicates beyond simple equality where needed.

### 3.2 Platform Connector Configuration

```yaml
zoomPlatform:
  type: zoom
  authType: oauth_server_to_server
  accountIdEnvVar: "ZOOM_ACCOUNT_ID"
  clientIdEnvVar: "ZOOM_CLIENT_ID"
  clientSecretEnvVar: "ZOOM_CLIENT_SECRET"
  webhookSecretTokenEnvVar: "ZOOM_WEBHOOK_SECRET_TOKEN"
  defaultHostEmail: "events@cbm.org"
  apiBaseUrl: "https://api.zoom.us/v2"     # Override only for testing
```

#### Field reference

- **`type`** — always `zoom` in this document. The bridge uses this to load the Zoom connector implementation.
- **`authType`** — only `oauth_server_to_server` is supported in v1.0.
- **`*EnvVar`** — names of environment variables read at bridge startup. The actual secret values never appear in YAML or any committed file.
- **`defaultHostEmail`** — the Zoom user under whose account meetings/webinars are created when the event type does not override `hostEmail`. Must be a valid licensed Zoom user in the configured account.
- **`apiBaseUrl`** — defaults to Zoom's public API; override only for sandbox testing.

### 3.3 Bridge Service Configuration

The bridge service configuration extends the existing `bridgeService` block from the survey integration with Zoom-specific fields:

```yaml
bridgeService:
  host: "0.0.0.0"
  port: 8100
  espocrmBaseUrl: "https://crm.example.com"
  espocrmApiKeyEnvVar: "ESPOCRM_API_KEY"

  # Existing survey-integration field — unchanged
  pollIntervalMinutes: 15

  # New Zoom-integration fields
  zoomAttendancePollMinutes: 60
  zoomAttendancePollLookbackHours: 24

  # Failure alerting (covers all connectors, not just Zoom)
  alertEmail: "events-admin@cbm.org"
  alertOnFailureClass: ["failedPermanent"]
```

#### Field reference

- **`zoomAttendancePollMinutes`** — interval at which the bridge runs the attendance polling safety net (Section 5.6). Default 60.
- **`zoomAttendancePollLookbackHours`** — how far back the polling job looks for events whose `dateEnd` has passed but `attendanceCapturedAt` is null. Default 24. Events older than this are not retried by polling — they require manual intervention.
- **`alertEmail`** — destination for failure-class email alerts. Single address only in v1.0; multi-recipient distribution lists are an org-side mailbox concern.
- **`alertOnFailureClass`** — list of failure statuses that generate an email alert. `["failedPermanent"]` is the recommended default to avoid alert noise from transient failures that resolve via retry.

---

## 4. Bridge Service Architecture

The Bridge Service is the Python middleware that orchestrates all integration flows. Its core architecture (HTTP framework, webhook router, scheduled-task runner, EspoCRM API client, retry logic, secrets loader, structured logging, integration log writer, alerting) is defined in `survey-integration-architecture.md` Section 4 and is shared with that integration.

This section documents only the **delta** the Zoom integration adds to that shared architecture.

### 4.1 Reference to Survey Integration Doc

For shared infrastructure, see `survey-integration-architecture.md`:

- **§4.1 Component Structure** — overall layout of the bridge service process, including the connector registry pattern
- **§4.3 API Endpoints** — base webhook endpoint structure and signature-verification middleware
- **§4.4 Scheduled Tasks** — base scheduled-task runner

This document extends that architecture with a new connector type, new webhook routes, a new scheduled task, and a new persistent queue.

### 4.2 MeetingConnector Interface

The survey integration defines a `SurveyConnector` abstract interface (survey doc §4.2). Zoom requires a structurally different interface because the underlying flows differ — surveys are "send invitation, capture single response" while meetings are "create session, manage roster, capture per-participant attendance."

A new abstract `MeetingConnector` interface is added to the bridge:

```python
class MeetingConnector(ABC):
    """Abstract interface for any meeting platform connector."""

    @abstractmethod
    def create_session(self, spec: SessionSpec) -> SessionResult:
        """Create a meeting or webinar. Returns session ID and join URLs."""

    @abstractmethod
    def update_session(self, session_id: str, spec: SessionSpec) -> None:
        """Update an existing session's syncable fields."""

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete a session. Triggers cancellation emails to registrants."""

    @abstractmethod
    def add_registrant(self, session_id: str, registrant: RegistrantSpec) -> RegistrantResult:
        """Add a registrant to a session. Returns the platform registrant ID."""

    @abstractmethod
    def cancel_registrant(self, session_id: str, registrant_id: str) -> None:
        """Cancel a registrant's registration. Triggers cancellation email."""

    @abstractmethod
    def get_attendance_report(self, session_id: str) -> AttendanceReport:
        """Fetch the post-meeting attendance report."""

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, headers: dict) -> bool:
        """Verify an inbound webhook payload's signature."""
```

The Zoom connector (`ZoomConnector`) implements this interface. A future Google Meet or Teams connector would implement the same interface, allowing the bridge logic to be platform-agnostic above the connector layer.

The bridge's connector registry is extended to hold connectors of either shape (`SurveyConnector` or `MeetingConnector`), discriminated by interface type — there is no single "universal connector" interface, because the operation sets genuinely differ.

### 4.3 Zoom-Specific Webhook Routes

Two new HTTP endpoints are added to the bridge:

| Route | Method | Purpose |
|---|---|---|
| `/webhook/zoom-events` | POST | Receives all Zoom-side webhook events (`meeting.ended`, `webinar.ended`, `meeting.participant_joined`, etc.). Verifies HMAC signature, enqueues for processing |
| `/webhook/espocrm/event` | POST | Receives EspoCRM webhook events for the Event entity (afterSave, afterRemove). Already exists in shape from survey integration; Zoom integration adds Event-entity routing |
| `/webhook/espocrm/event-registration` | POST | Receives EspoCRM webhook events for the EventRegistration entity (afterSave, afterRemove). New |

All three routes share the same signature-verification middleware from the survey integration. Zoom's HMAC-SHA256 signature scheme (verified via `verify_webhook_signature` on the connector) is checked before any payload parsing.

### 4.4 Scheduled Task: Attendance Polling Safety Net

A new scheduled task is added to the bridge's task runner:

**Task name:** `zoom_attendance_poll`
**Cadence:** Every `zoomAttendancePollMinutes` (default 60) minutes
**Logic:**

1. Query EspoCRM for Events where `zoomMeetingId IS NOT NULL` AND `dateEnd < now` AND `dateEnd >= now - zoomAttendancePollLookbackHours` AND `attendanceCapturedAt IS NULL`
2. For each match, invoke the inbound attendance flow (Section 5.6)
3. Log every poll cycle's match count to the structured log; write a `ZoomIntegrationLog` entry only when an action is actually taken (avoids log spam on idle cycles)

This task is idempotent with the `meeting.ended` webhook flow: the first to set `attendanceCapturedAt` wins, and the second is a logged no-op.

### 4.5 Pending Inbound Queue

To handle the case where Zoom successfully delivers a webhook to the bridge, but the bridge cannot complete the EspoCRM write (CRM down, network issue, etc.), the bridge maintains a persistent local queue:

- **Storage:** SQLite database file in the bridge's data directory (`{bridge_data_dir}/pending_inbound.db`)
- **Schema:** `(id, payload_json, source, received_at, attempt_count, last_attempt_at, last_error)`
- **Behavior:** On webhook receipt, the bridge persists the raw payload, returns 200 to Zoom (so Zoom does not retry), and a background worker drains the queue with exponential backoff against EspoCRM
- **Drain cadence:** 30s, 2min, 10min, 1hr, 6hr, then daily until `max_age_days` (default 7), after which the entry is escalated to `failedPermanent` and surfaced via the standard alerting pipeline

This pattern is also used for the survey integration's response-capture flow (per survey doc §5.2). The Zoom integration shares the same `pending_inbound.db` file and worker; only the dispatcher differs.

---

## 5. Integration Flows

This section describes each integration flow end to end. Six flows total: meeting creation, update sync, registrant push, registration update/cancellation, event cancellation, and attendance capture.

### 5.1 Outbound Flow: Meeting/Webinar Creation

**Trigger:** EspoCRM webhook fires on Event create or update; bridge evaluates `triggerRules` for the Event's `eventType`.

**Sequence:**

1. CRM user creates or updates an Event record with `eventType` set, and saves
2. EspoCRM fires `Event.afterSave` webhook to `/webhook/espocrm/event`
3. Bridge verifies webhook signature; rejects on failure
4. Bridge fetches the Event record from the EspoCRM REST API (the webhook payload may be partial)
5. Bridge looks up `zoomConfig.eventTypes[event.eventType]`. If no entry exists, logs and exits
6. Bridge evaluates the matching `triggerRules` against the Event using `condition_expression.py`:
   - For `onCreate`: rule fires if this is a create event AND `condition` evaluates true
   - For `statusChange`: rule fires if `statusField` transitioned to `statusValue` in this save AND `condition` evaluates true
   - For `manual`: rule never fires automatically (handled by the custom button — Section 7.3)
7. If a rule fires AND `event.zoomMeetingId IS NULL`, bridge proceeds. Otherwise exits (already provisioned).
8. Bridge writes a `ZoomIntegrationLog` entry with `operation: createSession`, `status: pending`
9. Bridge resolves the host email: event-type-level `hostEmail` if set, else `zoomPlatform.defaultHostEmail`
10. Bridge calls `ZoomConnector.create_session(spec)` with the resolved settings. Connector hits Zoom API:
    - `POST /users/{hostEmail}/meetings` for meetings
    - `POST /users/{hostEmail}/webinars` for webinars
11. On success, connector returns `(session_id, join_url, registration_url)`
12. Bridge PATCHes the Event record in EspoCRM with `zoomMeetingId`, `zoomMeetingType`, `zoomJoinUrl`, `zoomRegistrationUrl`, `zoomHostEmail`, `zoomLastSyncedAt`
13. Bridge updates the `ZoomIntegrationLog` entry: `status: success`
14. Bridge checks for any pending registrant pushes for this Event in the registrant backlog (Section 5.3) and flushes them

**Failure handling:** Per Section 6 of this doc — transient failures retry with exponential backoff (up to 4 attempts); permanent failures terminate immediately and surface via alert.

### 5.2 Outbound Flow: Event Update Sync

**Trigger:** EspoCRM webhook fires on Event update; bridge detects a change to a syncable field on an Event with non-null `zoomMeetingId`.

**Always-on, no opt-in.** Once an Event has a Zoom session, the integration takes ownership of keeping Zoom in sync with the CRM record.

**Syncable fields:**

| CRM Field (Event) | Zoom Field |
|---|---|
| `name` | `topic` |
| `dateStart` | `start_time` |
| `dateEnd` (or `duration` derived from `dateEnd - dateStart`) | `duration` |
| `description` | `agenda` |
| `timezone` | `timezone` |

**Sequence:**

1. EspoCRM fires `Event.afterSave` for an UPDATE on an Event with non-null `zoomMeetingId`
2. Bridge fetches the Event record. Compares the syncable-fields list against `zoomLastSyncedAt`-era state (cached in the integration log) to detect changes
3. If any syncable field has changed, bridge writes a `ZoomIntegrationLog` entry with `operation: updateSession`, `status: pending`
4. Bridge calls `ZoomConnector.update_session(session_id, spec)` with the new values. Connector hits:
   - `PATCH /meetings/{id}` for meetings
   - `PATCH /webinars/{id}` for webinars
5. On success, bridge updates `zoomLastSyncedAt` on the Event and sets the log entry to `status: success`

**What is NOT synced:** `assignedUser` (CRM-internal concept), `zoomHostEmail` (connector-level setting, not a per-record CRM field), `eventType` (changing this mid-flight is a configuration error — bridge logs a warning but takes no action). Host changes to live Zoom sessions are not supported — see Section 10.

### 5.3 Outbound Flow: Registrant Push

**Trigger:** EspoCRM webhook fires on EventRegistration create or update; bridge evaluates `registrantTriggerRules` for the parent Event's `eventType`.

**Sequence:**

1. CRM user creates or updates an EventRegistration record, and saves
2. EspoCRM fires `EventRegistration.afterSave` webhook to `/webhook/espocrm/event-registration`
3. Bridge fetches the EventRegistration and its parent Event
4. Bridge looks up `zoomConfig.eventTypes[parentEvent.eventType].registrantTriggerRules`. If the event type does not require registration (no rules block), bridge exits
5. Bridge evaluates the matching rule against the EventRegistration:
   - For `onCreate`: fires if this is a create event
   - For `statusChange`: fires if `statusField` transitioned to `statusValue`
   - For `manual`: never fires automatically
6. If the rule fires AND `eventRegistration.zoomRegistrantId IS NULL`:
   - **If parent Event has non-null `zoomMeetingId`:** proceed to step 7
   - **If parent Event has null `zoomMeetingId`:** queue this registrant in the bridge's local backlog (`{bridge_data_dir}/registrant_backlog.db`, schema `(eventRegistrationId, eventId, queuedAt)`) and exit. Will be flushed by Section 5.1 step 14 when the Event's Zoom session is created
7. Bridge writes a `ZoomIntegrationLog` entry with `operation: addRegistrant`, `status: pending`
8. Bridge calls `ZoomConnector.add_registrant(session_id, registrant)`. Connector hits:
   - `POST /meetings/{id}/registrants` for meetings
   - `POST /webinars/{id}/registrants` for webinars
9. On success, connector returns `(registrant_id, join_url)`
10. Bridge PATCHes the EventRegistration with `zoomRegistrantId`
11. Bridge updates the log entry: `status: success`
12. Zoom sends the registrant a confirmation email with their unique join URL — no action required from the bridge

**Backlog flush logic (Section 5.1 step 14):** When an Event's Zoom session is successfully created, the bridge queries `registrant_backlog.db` for all entries with that `eventId`, processes each through steps 7–11, then deletes the backlog entries. If any backlog entry fails its push, it remains in the backlog for the next retry cycle.

### 5.4 Outbound Flow: Registration Update / Cancellation

**Trigger:** EspoCRM webhook fires on EventRegistration update (Contact field change) or delete; bridge detects an EventRegistration with non-null `zoomRegistrantId`.

**Sub-flows:**

- **Contact field change** (registrant's email, name, phone updated on the linked Contact) → bridge calls `ZoomConnector.update_registrant()` (extension to the connector interface — added to Zoom-specific implementation, generalized to the abstract interface only if a second meeting platform requires it)
- **Registration cancelled** (`registrationStatus → Cancelled` or record deleted) → bridge calls `ZoomConnector.cancel_registrant(session_id, registrant_id)`. Connector hits `PUT /meetings/{id}/registrants/status` with `action: cancel`. Zoom sends the registrant a cancellation email
- **Registration created after meeting has ended** → bridge logs a `failedPermanent` entry with reason "meeting already ended" and exits. No useful action

### 5.5 Outbound Flow: Event Cancellation

**Trigger:** EspoCRM webhook fires on Event update; bridge detects status transition matching a `cancellationRules` entry.

**Sequence:**

1. Bridge evaluates `cancellationRules` against the Event's status change
2. If a rule fires AND `event.zoomMeetingId IS NOT NULL` AND `event.dateEnd >= now` (i.e., not a past event):
   - Bridge writes a `ZoomIntegrationLog` entry with `operation: deleteSession`, `status: pending`
   - Bridge calls `ZoomConnector.delete_session(session_id)`
   - Zoom sends cancellation emails to all registrants automatically
3. Bridge does NOT clear `zoomMeetingId` or other Zoom fields on the Event — they remain for audit/historical reference
4. Bridge updates the log entry: `status: success`

**Event record deletion (separate from cancellation):**

- **Default behavior:** Bridge does nothing when an Event with a Zoom session is deleted from the CRM. The Zoom session persists; registrants still receive reminders and can join. This is a deliberate failsafe against accidental deletion
- **Strict mode:** If `bridgeService.blockEventDeletionWithZoomSession: true`, bridge registers a `beforeRemove` webhook handler that returns an error response, blocking the delete in EspoCRM. User must transition the Event to Cancelled first (which fires Section 5.5 above), then delete. *This requires EspoCRM beforeRemove webhook support, which is enabled in the configuration declared in Section 7.1.*

### 5.6 Inbound Flow: Attendance Capture

**Trigger:** Either Zoom's `meeting.ended` (or `webinar.ended`) webhook to `/webhook/zoom-events`, OR the polling safety net (Section 4.4).

**Sequence:**

1. Bridge receives `meeting.ended` webhook (or polling job identifies a candidate Event)
2. Bridge verifies webhook signature (webhook path) or skips signature check (polling path)
3. Bridge persists the raw payload to `pending_inbound.db` (Section 4.5) and returns 200 to Zoom (webhook path only)
4. Background worker picks up the payload:
   a. Bridge writes a `ZoomIntegrationLog` entry with `operation: getAttendanceReport`, `status: pending`
   b. Bridge looks up the Event by `zoomMeetingId`. If `attendanceCapturedAt IS NOT NULL`, this is a duplicate — log `status: success` (no-op) and exit
   c. Bridge calls `ZoomConnector.get_attendance_report(session_id)`. Connector hits:
      - `GET /report/meetings/{id}/participants` for meetings
      - `GET /report/webinars/{id}/participants` for webinars
   d. Connector handles pagination (Zoom returns up to 300 participants per page; large webinars require multiple calls)
5. Bridge reconciles each participant in the report against existing EventRegistration records by matching on email (case-insensitive):
   - **Match found:** Bridge PATCHes the EventRegistration with `attended`, `attendanceMinutes`, `firstJoinedAt`, `lastLeftAt`, `attendancePercent`
   - **No match (walk-in):** See Section 6.7 below
6. After all participants are processed, bridge sets `attendanceCapturedAt` on the Event and updates the log entry to `status: success`

**Idempotency:** `attendanceCapturedAt` is the single source of truth for "this Event's attendance has been captured." Steps 4b and 6 together ensure that webhook + polling never produce duplicate writes.

**Pagination handling:** Zoom's report endpoints return up to 300 participants per page. The connector handles pagination internally, accumulating all participants into a single `AttendanceReport` before returning to the bridge. If pagination fails partway through, the entire operation is treated as a transient failure and retried from the first page (Zoom's reports are stable post-meeting, so re-fetching is safe).

---

## 6. Zoom Connector Details

### 6.1 Server-to-Server OAuth Token Lifecycle

The connector uses Zoom's Server-to-Server OAuth (S2S) authentication, which replaces the deprecated JWT app type.

**Token acquisition:**

1. Connector reads `accountId`, `clientId`, `clientSecret` from environment variables at bridge startup
2. On first API call (or when cached token is expired), connector POSTs to `https://zoom.us/oauth/token` with `grant_type=account_credentials&account_id={accountId}` and HTTP Basic auth using `clientId:clientSecret`
3. Zoom returns an access token with `expires_in: 3600` (1 hour)
4. Connector caches the token in memory with an expiry timestamp set to `now + 3500` (50-second safety margin)
5. All subsequent API calls include `Authorization: Bearer {token}` until expiry

**Token refresh:** Lazy — token is only re-fetched when an API call is about to be made and the cached token is within 50 seconds of expiry. No background refresh thread.

**Auth failure handling:** If a 401 is received during an API call, the connector clears its cached token, fetches a new one, and retries the original call exactly once. If the second attempt also returns 401, the operation is escalated to `failedPermanent` (likely a credential rotation or revocation).

### 6.2 Meetings vs Webinars: API Divergence

The Zoom connector abstracts over the two product types so the bridge sees a uniform interface, but the underlying API calls differ:

| Operation | Meeting Endpoint | Webinar Endpoint |
|---|---|---|
| Create | `POST /users/{userId}/meetings` | `POST /users/{userId}/webinars` |
| Update | `PATCH /meetings/{id}` | `PATCH /webinars/{id}` |
| Delete | `DELETE /meetings/{id}` | `DELETE /webinars/{id}` |
| Add Registrant | `POST /meetings/{id}/registrants` | `POST /webinars/{id}/registrants` |
| Cancel Registrant | `PUT /meetings/{id}/registrants/status` | `PUT /webinars/{id}/registrants/status` |
| Attendance Report | `GET /report/meetings/{id}/participants` | `GET /report/webinars/{id}/participants` |

**Payload shape differences:**

- The `type` field on create: meetings use `2` (scheduled meeting), webinars use `5` (webinar). `8` (recurring with fixed time) is not supported in v1.0.
- Webinar registrant fields include `org`, `job_title`, `industry` — meetings do not. The connector populates these only for webinars when the source data is available.
- Webinar attendance reports include `attentiveness_score` (deprecated by Zoom but still returned for some plans) — the connector ignores this field.
- Webinar reports include Q&A and poll responses; the connector ignores both in v1.0 (flagged in Section 10).

### 6.3 Key API Endpoints Used

In addition to the create/update/delete/registrant/report endpoints above:

| Endpoint | Purpose |
|---|---|
| `POST /oauth/token` | Acquire S2S access token (Section 6.1) |
| `GET /users/{userId}` | Validate that `defaultHostEmail` and per-event `hostEmail` resolve to actual Zoom users at startup; cached |
| `GET /accounts/{accountId}` | Validate account ID at startup |

Connector startup performs the user/account validation calls and aborts bridge startup if either fails — fail-fast on misconfiguration.

### 6.4 Host Resolution

For each `create_session` call:

1. Connector reads the event-type-level `hostEmail` if set
2. Otherwise, falls back to `zoomPlatform.defaultHostEmail`
3. Validates the resolved email against the cached user list (refreshed every 24 hours)
4. If validation fails, raises `ConfigurationError` and the operation is logged as `failedPermanent`

The `hostEmail` is passed to Zoom as the `{userId}` path parameter on the create endpoint.

### 6.5 Registrant Payload Shape

When `add_registrant` is called, the connector builds the payload from the EventRegistration and its linked Contact:

| Zoom Field | Source |
|---|---|
| `email` | `Contact.emailAddress` (required; bridge logs and skips if null) |
| `first_name` | `Contact.firstName` |
| `last_name` | `Contact.lastName` |
| `phone` | `Contact.phoneNumber` (E.164 format, already cleaned by CRM) |
| `org` | `Contact.accountName` (webinars only) |
| `job_title` | `Contact.title` (webinars only) |
| `address` | `Contact.addressStreet` (webinars only, when present) |
| `city` | `Contact.addressCity` (webinars only, when present) |
| `state` | `Contact.addressState` (webinars only, when present) |
| `zip` | `Contact.addressPostalCode` (webinars only, when present) |
| `country` | `Contact.addressCountry` (webinars only, when present) |
| `custom_questions` | Empty in v1.0 (custom registration questions are a future feature) |

Auto-approval: when `eventType.settings.approvalType` is `automatic`, the connector includes `auto_approve: true` in the create payload (or doesn't, depending on the meeting's pre-configured approval type — Zoom's API behavior here is asymmetric across meetings vs webinars; the connector handles both).

### 6.6 Attendance Report Shape

Zoom's attendance report response format:

```json
{
  "page_count": 1,
  "page_size": 300,
  "total_records": 42,
  "next_page_token": "",
  "participants": [
    {
      "id": "abc123",
      "user_id": "...",
      "name": "John Smith",
      "user_email": "john@example.com",
      "join_time": "2026-04-30T14:00:00Z",
      "leave_time": "2026-04-30T15:30:00Z",
      "duration": 5400,
      "registrant_id": "xyz789",
      "status": "in_meeting"
    }
  ]
}
```

Connector accumulates all pages, then for each unique `user_email` builds an attendance summary:

- `attended = true` (any participant entry exists)
- `attendanceMinutes` = sum of `duration` across all entries with this email (handles rejoins)
- `firstJoinedAt` = MIN of `join_time` across entries
- `lastLeftAt` = MAX of `leave_time` across entries
- `attendancePercent` = `attendanceMinutes / meetingDurationMinutes * 100`, capped at 100

The `meetingDurationMinutes` denominator is `(actualEndTime - actualStartTime)` from the meeting metadata, NOT the scheduled duration — handles meetings that ran long or short.

### 6.7 Walk-in Reconciliation

For each participant in the attendance report whose email does not match any existing EventRegistration:

1. Connector searches for a Contact record with that email (case-insensitive)
   - **Found:** Bridge creates a new EventRegistration record linked to the Event and the matched Contact, with `registrationSource: WalkIn`, `registrationStatus: Attended`, and the populated attendance fields
   - **Not found:** Bridge creates a placeholder Contact with email, name (parsed from Zoom's `name` field — `firstName`, `lastName` split on first space), and `description: "Auto-created from Zoom walk-in for Event {eventName}"`. Then creates an EventRegistration as above

2. New WalkIn EventRegistration records are surfaced in a saved view "EventRegistration — WalkIns needing review" (Section 7.4) for the CRM admin to manually de-duplicate or merge if a duplicate Contact exists under a different email

This logic is cautious: rather than risk false-positive Contact merges, the bridge always creates a placeholder and lets a human reconcile.

---

## 7. EspoCRM Configuration

### 7.1 Webhook Registration

CRM Builder registers the following EspoCRM webhooks during deployment:

| Webhook | Entity | Event | Bridge Endpoint |
|---|---|---|---|
| Event-Save | Event | afterSave | `https://{bridge_host}/webhook/espocrm/event` |
| Event-Remove | Event | afterRemove | `https://{bridge_host}/webhook/espocrm/event` |
| Event-BeforeRemove | Event | beforeRemove | `https://{bridge_host}/webhook/espocrm/event` (only when `blockEventDeletionWithZoomSession: true`) |
| EventRegistration-Save | EventRegistration | afterSave | `https://{bridge_host}/webhook/espocrm/event-registration` |
| EventRegistration-Remove | EventRegistration | afterRemove | `https://{bridge_host}/webhook/espocrm/event-registration` |

Each webhook registration uses HMAC signing with a shared secret (read from `ESPOCRM_WEBHOOK_SECRET` env var by both EspoCRM and the bridge). The bridge rejects webhooks with invalid signatures.

### 7.2 API User for Bridge Service

CRM Builder provisions a dedicated API user in EspoCRM for the bridge service:

- **Username:** `zoom-bridge` (and `survey-bridge` if survey integration is also deployed — the bridge uses different API users per integration for blast-radius control)
- **Auth:** API key, stored in `ESPOCRM_API_KEY` env var on the bridge
- **Permissions:** Read on Event, Contact, Account, EventRegistration; Read+Edit on EventRegistration; Read+Edit on Event (for Zoom-managed fields only — enforced via field-level ACL); Read+Create+Edit on ZoomIntegrationLog; Read+Create on Contact (for walk-in placeholder creation)

### 7.3 Custom Button for Manual Trigger

For event types with `trigger: manual`, CRM Builder configures a custom action button on the Event detail layout:

- **Label:** "Create Zoom Session"
- **Visibility:** Only when `eventType` resolves to a manual-trigger event type AND `zoomMeetingId IS NULL`
- **Action:** Sends a webhook to `https://{bridge_host}/api/manual-trigger` with the Event ID. Bridge processes as if a regular `triggerRules` rule had fired

A second button, "Push Registrants to Zoom," is configured for the EventRegistration detail layout for event types with `registrantTriggerRules.trigger: manual`.

### 7.4 ZoomIntegrationLog Saved Views

CRM Builder provisions the following saved views on the ZoomIntegrationLog entity:

| View Name | Filter |
|---|---|
| Zoom — failed in last 7 days | `status IN [failedTransient, failedPermanent] AND lastAttemptAt >= today-7d` |
| Zoom — pending operations | `status = pending` |
| Zoom — operations by Event (parent grouping) | grouped by `parent` |

And on EventRegistration:

| View Name | Filter |
|---|---|
| EventRegistration — WalkIns needing review | `registrationSource = WalkIn AND createdAt >= today-30d` |

---

## 8. Deployment Architecture

### 8.1 Component Deployment

The bridge service runs as a single Docker container, shared across all integrations (survey + Zoom + future integrations):

- **Container image:** `crmbuilder-bridge:{version}` — includes both survey and Zoom connector code
- **Connector activation:** Per-deployment YAML controls which connectors are loaded. A deployment with only `surveyConfig` set loads only the survey connector; a deployment with only `zoomConfig` loads only the Zoom connector; a deployment with both loads both.

**Persistent volumes:**

- `/var/lib/bridge/data/` — holds `pending_inbound.db` (shared), `registrant_backlog.db` (Zoom-specific)
- `/var/log/bridge/` — structured log output

**Networking:**

- Inbound 8100 (or configured port) — must be reachable from EspoCRM and Zoom
- Outbound HTTPS — must reach `api.zoom.us`, `zoom.us` (for OAuth), and the EspoCRM base URL

### 8.2 Network Requirements

| Source | Destination | Protocol | Purpose |
|---|---|---|---|
| EspoCRM | Bridge:8100 | HTTPS | Outbound entity webhooks |
| Zoom | Bridge:8100 | HTTPS | Inbound `meeting.ended` etc. webhooks |
| Bridge | api.zoom.us:443 | HTTPS | Zoom API calls |
| Bridge | zoom.us:443 | HTTPS | OAuth token endpoint |
| Bridge | EspoCRM | HTTPS | EspoCRM REST API calls |

The bridge MUST be deployed at a publicly reachable hostname (TLS required) so that Zoom's webhook delivery can reach it. If the EspoCRM instance and bridge are co-located on the same Droplet, EspoCRM-to-bridge traffic can use loopback, but Zoom-to-bridge still requires a public DNS entry and TLS termination.

### 8.3 Environment Variables

The complete env-var list for a deployment with Zoom integration enabled:

| Variable | Purpose |
|---|---|
| `ESPOCRM_API_KEY` | Bridge's API key for EspoCRM (Section 7.2) |
| `ESPOCRM_WEBHOOK_SECRET` | HMAC shared secret for EspoCRM-to-bridge webhooks |
| `ZOOM_ACCOUNT_ID` | Zoom S2S account ID |
| `ZOOM_CLIENT_ID` | Zoom S2S client ID |
| `ZOOM_CLIENT_SECRET` | Zoom S2S client secret |
| `ZOOM_WEBHOOK_SECRET_TOKEN` | Zoom-side webhook secret for HMAC verification |

If the survey integration is also deployed, additional `LIMESURVEY_*` variables join the list per `survey-integration-architecture.md` §8.

### 8.4 CRM Builder Provisioning Sequence

When a deployment includes `zoomConfig`, CRM Builder executes the following sequence after the standard entity/field/relationship provisioning:

1. Provision Zoom-specific fields on Event entity (Section 2.1)
2. Provision attendance fields on EventRegistration entity (Section 2.2)
3. Provision ZoomIntegrationLog entity, fields, relationships, and saved views (Sections 2.3, 7.4)
4. Provision the WalkIn saved view on EventRegistration (Section 7.4)
5. Provision the API user `zoom-bridge` with the field-level ACL from Section 7.2
6. Register the five EspoCRM webhooks from Section 7.1
7. Configure the custom buttons from Section 7.3
8. Validate the bridge service is reachable at the configured URL and responds to a health check
9. Validate the Zoom connector by calling `GET /users/{defaultHostEmail}` through the bridge — fails the deployment if the host email does not resolve

---

## 9. Security Considerations

### 9.1 S2S OAuth Credentials

Zoom Server-to-Server OAuth credentials (`accountId`, `clientId`, `clientSecret`) grant API access to the entire Zoom account, including the ability to create, modify, and delete any meeting or webinar, manage registrants, access recordings, and read user information.

- Credentials are stored only in environment variables on the bridge service host. Never in YAML, never in source control, never in logs.
- The bridge process must run under a user account whose process environment is not readable by other users.
- On rotation, both old and new credentials must be live for the rotation window — Zoom's S2S design supports a single active credential pair per app, so rotation requires a brief window where the bridge is restarted with new values.

### 9.2 Webhook Authentication

All inbound webhooks (from both EspoCRM and Zoom) are authenticated via HMAC-SHA256 signature verification:

- **EspoCRM webhooks:** Signed with `ESPOCRM_WEBHOOK_SECRET`. Bridge verifies in shared middleware (per survey doc §9.2)
- **Zoom webhooks:** Signed with `ZOOM_WEBHOOK_SECRET_TOKEN` per Zoom's documented HMAC scheme. Bridge verifies in the Zoom connector's `verify_webhook_signature` method before any payload parsing

Bridge rejects unsigned or invalidly-signed payloads with HTTP 401 and logs the rejection with payload metadata only (no body content).

### 9.3 Credential Rotation

Recommended cadence: at least every 90 days. The bridge does not enforce rotation — operators are responsible for periodic rotation per organizational policy.

Rotation mechanism: update environment variables and restart the bridge container. Brief downtime (~10 seconds) is expected during restart. Webhook deliveries from Zoom that arrive during downtime are retried automatically per Zoom's documented retry schedule.

The CRM Builder deployment tool includes a "Rotate Zoom Credentials" workflow that walks the operator through generating new S2S credentials in the Zoom App Marketplace and updating the bridge environment file.

### 9.4 Credential Masking in Logs

The bridge's structured logger applies a redaction filter to all log output:

- Substring matches against `ZOOM_CLIENT_SECRET`, `ZOOM_WEBHOOK_SECRET_TOKEN`, `ESPOCRM_API_KEY`, `ESPOCRM_WEBHOOK_SECRET` values are replaced with `[REDACTED]`
- Substring matches against any 32-byte hex token (heuristic for Zoom access tokens) are replaced with `[REDACTED]`
- Authorization headers in logged HTTP transactions are replaced with `Authorization: [REDACTED]`

This protects against accidental leaks via stack traces, request/response logging in debug mode, or third-party log aggregators.

### 9.5 Registrant PII

Attendance reports and registrant payloads contain Personally Identifiable Information (email, full name, phone, organization, address). The bridge handles this data with the following constraints:

- Registrant data is never persisted by the bridge except in transit through `pending_inbound.db` (which is on the bridge's local disk and not network-accessible)
- Attendance reports fetched from Zoom are processed in memory and written directly to EspoCRM; raw report payloads are not retained
- The `ZoomIntegrationLog` entity stores operation metadata only — no registrant PII appears in `failureReason` strings (the redaction filter from §9.4 catches accidental inclusions)
- Walk-in placeholder Contacts created by the bridge inherit the same access controls as regular Contacts; CRM admin must review and merge as part of the workflow described in §6.7

---

## 10. Future Considerations

### 10.1 Bridge Service Architecture Extraction

The Bridge Service is now shared between two integration architectures (survey and Zoom). The shared infrastructure (HTTP listener, scheduled-task runner, EspoCRM client, retry logic, integration log writer, alerting, secrets loader, pending inbound queue) is currently documented in `survey-integration-architecture.md` §4 and referenced from this document.

A cleaner long-term factoring would extract this shared content into a third document — `bridge-service-architecture.md` — with both integration documents referencing it. This would reduce drift risk and clarify that the bridge service is a generic platform, not a survey-specific one.

The refactor is deferred because it modifies an existing approved document. Sequencing: revisit after the third integration (whatever it ends up being) joins the platform, at which point the value of a unified spec exceeds the cost of the document refactor.

### 10.2 Webinar Q&A and Poll Capture

Zoom Webinar reports include question-and-answer transcripts and poll responses. v1.0 ignores both. A future revision could capture these as:

- Q&A → new `EventQA` child entity of Event, with question, answerer, and answer fields
- Polls → new `EventPoll` and `EventPollResponse` entities

Useful for after-action reporting and audience engagement analysis. Adds non-trivial schema and connector code.

### 10.3 Recording Handling

Zoom can record meetings and webinars (cloud or local). The `autoRecording` setting in `eventType.settings` is passed through to Zoom but the bridge does not currently fetch recordings or attach them to the Event record. A future revision could:

- Listen for `recording.completed` webhook
- Download the recording (and/or transcript) via Zoom's Cloud Recording API
- Attach as a file to the Event record, OR store a URL link

Storage costs and retention policy must be decided per deployment before this is implemented.

### 10.4 Double-Booking Detection

The current architecture trusts the organization's policy that no two events are scheduled at overlapping times. A future revision could:

- Before creating a new Zoom session, query existing Events with non-null `zoomMeetingId` for time overlap
- Warn (or block, configurable) on conflict

Useful as the integration scales beyond a single team.

### 10.5 Additional Meeting Platforms

The `MeetingConnector` interface (§4.2) is designed to support Google Meet, Microsoft Teams, or other platforms with minimal architectural change. Per-event-type YAML could specify which platform handles each type:

```yaml
eventTypes:
  workshop:
    platform: zoom
    zoomProductType: meeting
    ...
  customer_call:
    platform: google_meet
    ...
```

Each platform implements `MeetingConnector` independently. Bridge logic remains unchanged.

### 10.6 Recurring Meeting Series

Zoom supports recurring meetings (`type: 8`, fixed-time recurring). The current architecture creates one Zoom session per Event record; recurring series would either:

- Map a single Event to a recurring Zoom series (one-to-many at the series level)
- Or expand a recurring Event template into N child Events, each with its own Zoom session

Decision deferred until a concrete use case requires it.

### 10.7 Generalized IntegrationLog Entity

`ZoomIntegrationLog` could be merged with the survey integration's equivalent (or its absence) into a single `IntegrationLog` entity discriminated by `connectorType`. This would unify the operator's mental model of "one log to rule them all" and consolidate saved views and alerting.

Same factoring concern as §10.1 — deferred to a coordinated refactor when the third integration arrives.
