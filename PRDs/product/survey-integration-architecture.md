# Survey Integration Architecture

**CRM Builder — Survey Platform Integration**

Last Updated: 04-03-26 21:00

---

## 1. Overview

This document defines the architecture for integrating external survey platforms with EspoCRM deployments managed by CRM Builder. The design provides a reusable, YAML-driven pattern that supports any survey platform through a pluggable connector model, with LimeSurvey as the initial reference implementation.

### 1.1 Goals

- Enable CRM users to send surveys to contacts linked to any surveyable entity (Engagements, Workshops, etc.)
- Automatically capture full survey response data back into the CRM for analytics and reporting
- Support multiple trigger types: status-change, scheduled/recurring, and manual
- Keep the CRM data model survey-platform-agnostic so connectors can be swapped without schema changes
- Make the entire configuration declarable in YAML for CRM Builder deployments

### 1.2 System Components

| Component | Role |
|---|---|
| **EspoCRM** | Core CRM. Hosts the Survey and SurveyAnswer entities, fires webhooks on entity events, provides REST API for record CRUD |
| **LimeSurvey** | External survey platform. Hosts survey templates, manages participant tokens, collects responses. Self-hosted, GPL-licensed |
| **Bridge Service** | Python middleware. Listens for triggers, orchestrates provisioning and response capture between EspoCRM and LimeSurvey |
| **CRM Builder** | Deployment tool. Provisions the Survey/SurveyAnswer entities, survey type configurations, webhook registrations, and bridge service settings from YAML |

### 1.3 Reference Implementation

The first deployment of this architecture is for Cleveland Business Mentors (CBM), a nonprofit mentoring organization. CBM's survey use cases include:

- **Client Intake Assessment** — triggered when an Engagement status changes to "Active"
- **Mentoring Satisfaction Survey** — recurring every 90 days while an Engagement is active
- **Program Exit Survey** — triggered when an Engagement status changes to "Completed"
- **Workshop Feedback Survey** — triggered when a Workshop status changes to "Completed"

---

## 2. Data Model

### 2.1 Survey Entity

The Survey entity is the primary CRM record representing a single survey sent to a single contact. It uses a polymorphic parent relationship to support linking to any surveyable entity type.

#### Fields

| Field | Type | Description |
|---|---|---|
| `name` | varchar | Auto-generated descriptive title (e.g., "Q2 Satisfaction Survey — John Smith") |
| `status` | enum | Draft, Sent, Completed, Expired |
| `surveyType` | varchar | References the survey type key from YAML config (e.g., "satisfaction", "exit", "workshopFeedback") |
| `parentType` | varchar | Entity type of the linked parent (e.g., "Engagement", "Workshop") |
| `parentId` | varchar | Record ID of the linked parent |
| `contact` | link | Link to the Contact entity (the survey respondent) |
| `externalSurveyId` | varchar | The LimeSurvey survey ID (or equivalent in other platforms) |
| `externalResponseId` | varchar | The platform-specific response ID, populated on completion |
| `externalToken` | varchar | The unique participant token issued by the survey platform |
| `surveyUrl` | url | The unique URL sent to the respondent |
| `dateSent` | dateTime | When the survey invitation was sent |
| `dateCompleted` | dateTime | When the response was submitted |
| `overallRating` | int | Promoted field — overall satisfaction rating (1–5) |
| `npsScore` | int | Promoted field — Net Promoter Score (0–10) |
| `primaryConcern` | varchar | Promoted field — primary concern or feedback category |
| `recommendationLikelihood` | int | Promoted field — likelihood to recommend (1–10) |
| `openFeedbackSummary` | text | Promoted field — free-text feedback summary |
| `assignedUser` | link | CRM user responsible for follow-up |
| `teams` | linkMultiple | Teams with access to this record |

#### Relationships

| Relationship | Type | Target Entity | Description |
|---|---|---|---|
| `contact` | belongsTo | Contact | The survey respondent |
| `parent` | belongsToParent | (polymorphic) | The surveyable entity this survey is associated with |
| `surveyAnswers` | hasMany | SurveyAnswer | Individual question-answer records |

#### Notes

- The `parentType` / `parentId` fields follow EspoCRM's existing polymorphic relationship pattern (same approach used by Meetings, Calls, and Tasks)
- Promoted fields (`overallRating`, `npsScore`, etc.) are optional — not every survey type populates every field. The YAML configuration defines which survey questions map to which promoted fields
- The `status` field transitions: Draft → Sent → Completed (or Expired)

### 2.2 SurveyAnswer Entity

The SurveyAnswer entity stores individual question-answer pairs from completed surveys. Each submitted survey response creates multiple SurveyAnswer records, one per question.

#### Fields

| Field | Type | Description |
|---|---|---|
| `survey` | link | Link to the parent Survey entity |
| `questionCode` | varchar | The survey platform's question identifier (e.g., "Q001", "G01Q02") |
| `questionText` | text | The human-readable question text |
| `answerValue` | varchar | The raw answer value (e.g., "4", "A1", "Yes") |
| `answerText` | text | The display label for the answer, if different from answerValue |
| `questionGroup` | varchar | Optional grouping label (e.g., "Mentor Evaluation", "Program Feedback") |
| `sortOrder` | int | Integer to preserve the original question sequence |

#### Relationships

| Relationship | Type | Target Entity | Description |
|---|---|---|---|
| `survey` | belongsTo | Survey | The parent survey record |

#### Notes

- This entity is intentionally generic — the same structure handles all survey types regardless of the number or nature of questions
- Adding or changing survey questions requires no CRM schema changes
- For analytics on specific answers, query by `questionCode` (e.g., "find all SurveyAnswers where questionCode = 'Q003' and answerValue < 3")

---

## 3. YAML Configuration Schema

Survey integration is configured in YAML as part of CRM Builder's deployment configuration. The configuration has three sections: entity definitions, survey type definitions, and platform connector settings.

### 3.1 Survey Type Configuration

```yaml
surveyConfig:
  # Which entity types can have surveys attached
  surveyableEntities:
    - Engagement
    - Workshop

  # Survey type definitions
  surveyTypes:
    intake:
      name: "Client Intake Assessment"
      limesurveyTemplateId: 12345
      triggerRules:
        - parentType: Engagement
          trigger: statusChange
          statusField: status
          statusValue: Active
      promotedFields:
        primaryConcern: G01Q005

    satisfaction:
      name: "Mentoring Satisfaction Survey"
      limesurveyTemplateId: 12346
      triggerRules:
        - parentType: Engagement
          trigger: scheduled
          intervalDays: 90
          condition:
            statusField: status
            statusValue: Active
      promotedFields:
        overallRating: G02Q003
        npsScore: G02Q007
        openFeedbackSummary: G02Q012

    exit:
      name: "Program Exit Survey"
      limesurveyTemplateId: 12347
      triggerRules:
        - parentType: Engagement
          trigger: statusChange
          statusField: status
          statusValue: Completed
      promotedFields:
        overallRating: G01Q001
        primaryConcern: G01Q005
        recommendationLikelihood: G01Q008

    workshopFeedback:
      name: "Workshop Feedback Survey"
      limesurveyTemplateId: 12348
      triggerRules:
        - parentType: Workshop
          trigger: statusChange
          statusField: status
          statusValue: Completed
      promotedFields:
        overallRating: G01Q001
        openFeedbackSummary: G01Q006
```

### 3.2 Platform Connector Configuration

```yaml
surveyPlatform:
  type: limesurvey
  baseUrl: "https://surveys.example.com"
  apiUrl: "https://surveys.example.com/index.php/admin/remotecontrol"
  apiUser: "api_user"
  apiPasswordEnvVar: "LIMESURVEY_API_PASSWORD"  # Read from environment
  completionRedirectBase: "https://bridge.example.com/survey-complete"

bridgeService:
  host: "0.0.0.0"
  port: 8100
  espocrmBaseUrl: "https://crm.example.com"
  espocrmApiKeyEnvVar: "ESPOCRM_API_KEY"  # Read from environment
  pollIntervalMinutes: 15
```

### 3.3 Contact Resolution Rules

Different parent entity types may have different relationships to the survey respondent. This configuration tells the bridge service how to find the contact(s) to survey for each parent type.

```yaml
contactResolution:
  Engagement:
    type: singleContact
    linkField: contact  # Direct link field on Engagement
  Workshop:
    type: multipleContacts
    linkField: attendees  # Many-to-many relationship on Workshop
```

When `type` is `singleContact`, the bridge service creates one Survey record. When `type` is `multipleContacts`, it creates one Survey record per contact, all sharing the same parentType/parentId.

---

## 4. Bridge Service Architecture

The bridge service is a Python application that mediates all communication between EspoCRM and LimeSurvey. It exposes an HTTP API for receiving webhooks and manual triggers, and runs scheduled tasks for polling and recurring survey triggers.

### 4.1 Component Structure

```
bridge-service/
├── app.py                    # Flask/FastAPI application entry point
├── config.py                 # YAML configuration loader
├── connectors/
│   ├── base.py               # Abstract connector interface
│   └── limesurvey.py         # LimeSurvey-specific connector
├── services/
│   ├── survey_provisioner.py # Creates Survey records and platform tokens
│   ├── response_processor.py # Processes completed surveys and writes back
│   └── scheduler.py          # Scheduled trigger and polling logic
├── espocrm/
│   └── client.py             # EspoCRM REST API client
└── requirements.txt
```

### 4.2 Connector Interface

The bridge service uses a pluggable connector pattern. All platform-specific logic is encapsulated behind a common interface:

```python
class SurveyConnector(ABC):
    """Abstract base class for survey platform connectors."""

    @abstractmethod
    def create_participant(self, survey_id: str, email: str,
                           first_name: str, last_name: str,
                           attributes: dict) -> dict:
        """Add a participant to a survey. Returns token and survey URL."""
        pass

    @abstractmethod
    def get_response(self, survey_id: str, response_id: str) -> dict:
        """Retrieve a single completed response by ID."""
        pass

    @abstractmethod
    def get_completed_responses_since(self, survey_id: str,
                                       since: datetime) -> list[dict]:
        """Retrieve all completed responses since a given timestamp."""
        pass

    @abstractmethod
    def send_invitation(self, survey_id: str, token: str) -> bool:
        """Send the survey invitation email to the participant."""
        pass

    @abstractmethod
    def get_survey_structure(self, survey_id: str) -> dict:
        """Retrieve question metadata (codes, texts, groups) for a survey."""
        pass
```

The LimeSurvey connector implements this interface using the RemoteControl 2 JSON-RPC API.

### 4.3 API Endpoints

| Method | Endpoint | Trigger Type | Description |
|---|---|---|---|
| POST | `/webhook/entity-update` | Status change | Receives EspoCRM webhooks when surveyable entities are updated |
| POST | `/survey/send` | Manual | Called by CRM custom button; accepts parentType, parentId, surveyType |
| GET | `/survey-complete` | Completion redirect | Receives the LimeSurvey end-URL redirect with survey_id, token, response_id |
| GET | `/health` | — | Health check endpoint |

### 4.4 Scheduled Tasks

| Task | Frequency | Description |
|---|---|---|
| Recurring survey check | Configurable (default: daily) | Queries EspoCRM for parent entities matching scheduled trigger rules (e.g., active engagements with no satisfaction survey in the last 90 days). Creates and sends surveys for matches |
| Response polling | Configurable (default: every 15 minutes) | Queries LimeSurvey for completed responses since last poll. Updates any Survey records still in "Sent" status that have matching completed responses. Acts as a safety net for missed completion redirects |
| Expiration check | Configurable (default: daily) | Finds Survey records in "Sent" status older than a configurable threshold (e.g., 30 days) and marks them as "Expired" |

---

## 5. Integration Flows

### 5.1 Outbound Flow: Sending a Survey

This flow is the same regardless of trigger type — once the bridge service determines that a survey should be sent, the provisioning sequence is identical.

**Sequence:**

```
1. Bridge Service → EspoCRM API
   Create Survey record:
     - status: "Draft"
     - surveyType: (from trigger rule)
     - parentType: (entity type)
     - parentId: (record ID)
     - contact: (resolved via contactResolution rules)
     - externalSurveyId: (from surveyType config)

2. Bridge Service → LimeSurvey API
   Call add_participants:
     - survey_id: (from surveyType limesurveyTemplateId)
     - email: (contact's email)
     - firstname: (contact's first name)
     - lastname: (contact's last name)
     - attributes: {crmSurveyId: <Survey record ID>, crmParentType: <parentType>, crmParentId: <parentId>}
   Returns: token, survey URL

3. Bridge Service → EspoCRM API
   Update Survey record:
     - externalToken: (token from step 2)
     - surveyUrl: (constructed URL)
     - status: "Sent"
     - dateSent: (current timestamp)

4. Bridge Service → LimeSurvey API (or EspoCRM email)
   Send invitation email to contact with the survey URL
```

**Trigger-Specific Entry Points:**

| Trigger Type | How the Bridge Service Gets parentType, parentId, and Contact |
|---|---|
| Status change webhook | Extracted from the EspoCRM webhook payload (entity ID and type are included). Contact resolved via contactResolution rules and a follow-up API call if needed |
| Scheduled/recurring | Queried from EspoCRM API based on trigger rule conditions. The query returns entity records; contact resolved via contactResolution rules |
| Manual button | Passed directly in the POST request body from the CRM custom button action |

### 5.2 Inbound Flow: Capturing a Completed Response

Two mechanisms work together to ensure all completed responses are captured.

#### 5.2.1 Completion Redirect (Near-Real-Time)

```
1. Respondent completes survey in browser

2. LimeSurvey redirects browser to:
   https://bridge.example.com/survey-complete?sid={SID}&token={TOKEN}&savedid={SAVEDID}

3. Bridge Service receives GET request
   Extracts: survey_id, token, response_id

4. Bridge Service → LimeSurvey API
   Call export_responses for the specific response_id
   Returns: full response data (all question-answer pairs)

5. Bridge Service → LimeSurvey API
   Call get_survey_structure (cached after first call per survey type)
   Returns: question metadata (codes, texts, groups, sort order)

6. Bridge Service → EspoCRM API
   Look up Survey record by externalToken
   Update Survey record:
     - status: "Completed"
     - dateCompleted: (current timestamp)
     - externalResponseId: (response_id)
     - Promoted fields populated per YAML mapping

7. Bridge Service → EspoCRM API
   Create SurveyAnswer records (one per question):
     - survey: (Survey record ID)
     - questionCode: (from survey structure)
     - questionText: (from survey structure)
     - answerValue: (from response data)
     - answerText: (display label if applicable)
     - questionGroup: (from survey structure)
     - sortOrder: (from survey structure)

8. Bridge Service → Browser
   Return "Thank You" page or redirect to branded confirmation page
```

#### 5.2.2 Scheduled Polling (Safety Net)

```
1. Cron job runs every 15 minutes (configurable)

2. Bridge Service → EspoCRM API
   Query Survey records where status = "Sent"
   Groups results by externalSurveyId

3. For each unique survey template:
   Bridge Service → LimeSurvey API
   Call export_responses with completion_status = "complete"
   and from_response_id = (last known response ID for this template)

4. For each completed response:
   Match response token to a Survey record via externalToken
   If Survey status is still "Sent":
     Execute steps 6-7 from the completion redirect flow above
   If Survey status is already "Completed":
     Skip (already processed by completion redirect)
```

### 5.3 Promoted Field Population

When the bridge service processes a completed response, it reads the YAML-defined `promotedFields` mapping for the survey type to determine which response values to write directly onto the Survey entity.

**Example processing for a completed Satisfaction Survey:**

Given this YAML configuration:
```yaml
promotedFields:
  overallRating: G02Q003
  npsScore: G02Q007
  openFeedbackSummary: G02Q012
```

The bridge service:
1. Finds the response value for question code `G02Q003` → writes it to `Survey.overallRating`
2. Finds the response value for question code `G02Q007` → writes it to `Survey.npsScore`
3. Finds the response value for question code `G02Q012` → writes it to `Survey.openFeedbackSummary`

These promoted fields enable direct CRM reporting without querying the SurveyAnswer child records.

---

## 6. LimeSurvey Connector Details

### 6.1 API Protocol

LimeSurvey uses the RemoteControl 2 API, which is a JSON-RPC based web service. All calls are made via HTTP POST to a single endpoint. Each request requires a session key obtained via `get_session_key`.

### 6.2 Session Management

```python
# Obtain session key
session_key = api.get_session_key(username, password)

# Make API calls using session key
result = api.add_participants(session_key, survey_id, participant_data)

# Release session key when done
api.release_session_key(session_key)
```

The bridge service should manage session keys efficiently — obtaining one per batch of operations rather than per individual call.

### 6.3 Key API Methods Used

| Method | Purpose | When Called |
|---|---|---|
| `get_session_key` | Authenticate and obtain session | Before any API batch |
| `release_session_key` | End session | After API batch completes |
| `add_participants` | Add a respondent with token and custom attributes | Outbound flow step 2 |
| `invite_participants` | Send email invitation to token holders | Outbound flow step 4 (if using LimeSurvey email) |
| `export_responses` | Retrieve completed response data | Inbound flow steps 4 and 3 (polling) |
| `list_questions` | Get question metadata for a survey | Inbound flow step 5 (cached) |
| `get_survey_properties` | Get survey-level metadata | Template provisioning |
| `import_survey` | Import an LSS template file | Initial deployment setup |
| `activate_survey` | Activate a survey for token-based collection | Initial deployment setup |

### 6.4 Token-Based Participant Management

LimeSurvey's token system is the mechanism for linking survey responses back to CRM records:

- Each survey template is activated with **token-based access control** — only participants with a valid token can access the survey
- When a survey is provisioned, the bridge service calls `add_participants` with the contact's email and custom attributes containing the CRM Survey record ID
- The token is stored on the CRM Survey entity in `externalToken`
- The survey URL is constructed as: `{baseUrl}/index.php/{surveyId}?token={token}`
- When a response is submitted, the token is included in the completion redirect URL, enabling the bridge service to correlate the response back to the correct CRM record

### 6.5 Custom Participant Attributes

LimeSurvey supports custom attributes on participant tokens (attribute_1, attribute_2, etc.). The bridge service uses these to embed CRM identifiers:

| Attribute | Value | Purpose |
|---|---|---|
| `attribute_1` | CRM Survey record ID | Primary correlation key for response matching |
| `attribute_2` | CRM parentType | Stored for reference/debugging |
| `attribute_3` | CRM parentId | Stored for reference/debugging |

### 6.6 End URL Configuration

Each survey template in LimeSurvey must have its End URL configured to redirect to the bridge service:

```
{bridgeService.completionRedirectBase}?sid={SID}&token={TOKEN}&savedid={SAVEDID}
```

The `{SID}`, `{TOKEN}`, and `{SAVEDID}` placeholders are LimeSurvey expression variables that are automatically replaced with the actual values at redirect time.

---

## 7. EspoCRM Configuration

### 7.1 Webhook Registration

CRM Builder provisions the following webhooks in EspoCRM to enable status-change triggers:

| Event | Entity Type | Target URL | Purpose |
|---|---|---|---|
| `Engagement.update` | Engagement | `{bridgeService}/webhook/entity-update` | Detect status changes that trigger surveys |
| `Workshop.update` | Workshop | `{bridgeService}/webhook/entity-update` | Detect status changes that trigger surveys |

Additional webhooks are registered for each entity type listed in `surveyConfig.surveyableEntities`.

Webhook configuration requirements per EspoCRM documentation:
- An API User must be created with the Webhooks scope enabled in its Role
- The API User must have read access to all surveyable entity types
- The webhook processing scheduled job ("Process Webhook Queue") runs every 5 minutes by default

### 7.2 API User for Bridge Service

The bridge service requires an API User in EspoCRM with the following permissions:

| Scope | Access Level |
|---|---|
| Survey | Create, Read, Edit |
| SurveyAnswer | Create, Read |
| Engagement | Read |
| Workshop | Read |
| Contact | Read |
| Webhooks | Enabled |

Authentication uses the API Key method for simplicity.

### 7.3 Custom Button for Manual Trigger

A custom action button is added to the detail view of each surveyable entity type. The button label is "Send Survey" and it calls the bridge service's `/survey/send` endpoint with the current record's entity type and ID.

Implementation approach: EspoCRM supports custom detail view buttons through metadata configuration. The button action makes an AJAX call to the bridge service endpoint. Survey type selection can be handled via a simple modal dialog if the entity has multiple applicable survey types.

---

## 8. Deployment Architecture

### 8.1 Component Deployment

All three components run on the same server or within the same network:

```
┌─────────────────────────────────────────────────┐
│  Server / VM / Container Host                   │
│                                                 │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │  EspoCRM     │  │  LimeSurvey              │ │
│  │  (PHP/MySQL) │  │  (PHP/MySQL)             │ │
│  │  Port 443    │  │  Port 443 (subdomain)    │ │
│  └──────┬───────┘  └──────────┬───────────────┘ │
│         │    REST API          │  JSON-RPC API   │
│         │                      │                 │
│  ┌──────▼──────────────────────▼───────────────┐ │
│  │  Bridge Service (Python)                    │ │
│  │  Port 8100                                  │ │
│  │  - Webhook listener                         │ │
│  │  - Scheduled tasks (cron / internal)        │ │
│  │  - Completion redirect handler              │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 8.2 Network Requirements

- The bridge service must be reachable from EspoCRM (for webhooks)
- The bridge service must be reachable from the public internet (for completion redirects from respondent browsers)
- The bridge service must be able to reach both EspoCRM and LimeSurvey APIs
- LimeSurvey must be reachable from the public internet (for respondents to fill out surveys)

### 8.3 CRM Builder Provisioning Sequence

When CRM Builder deploys a new instance with survey integration enabled:

1. Deploy EspoCRM with Survey and SurveyAnswer entity definitions
2. Deploy LimeSurvey instance
3. Import survey templates (LSS files) into LimeSurvey via API
4. Activate surveys with token-based access control
5. Configure End URLs on each survey template
6. Deploy and configure the bridge service with YAML config
7. Register webhooks in EspoCRM for all surveyable entity types
8. Create the EspoCRM API User with required permissions
9. Add custom "Send Survey" buttons to surveyable entity detail views

---

## 9. Security Considerations

### 9.1 API Credentials

- All API credentials (LimeSurvey password, EspoCRM API key) are stored as environment variables, never in YAML files or source code
- The bridge service reads credentials from environment variables at startup

### 9.2 Webhook Authentication

- EspoCRM webhooks include an X-Signature header for request authenticity verification
- The bridge service validates this signature using the webhook's secret key before processing any webhook payload

### 9.3 Completion Redirect Validation

- The completion redirect endpoint validates that the token exists in the CRM before processing
- The bridge service fetches response data directly from LimeSurvey's API rather than trusting any data passed in URL parameters (URL parameters are used only for correlation, not for response content)

### 9.4 Survey Access Control

- LimeSurvey surveys are configured with token-based access — only participants with a valid, unused token can access and submit a survey
- Each token is single-use, preventing duplicate submissions
- Tokens can be configured with an expiration date aligned with the CRM's survey expiration rules

### 9.5 Data Privacy

- Survey response data is stored in the CRM database, which is under the organization's control
- LimeSurvey is self-hosted, so no survey data leaves the organization's infrastructure
- The bridge service does not persist any data — it acts as a stateless intermediary

---

## 10. Future Considerations

### 10.1 Additional Survey Platforms

The pluggable connector pattern allows adding support for other survey platforms (e.g., Typeform, SurveyJS) by implementing the `SurveyConnector` interface. The CRM data model and YAML configuration structure remain unchanged.

### 10.2 Survey Reminders

The bridge service could support automated reminder emails for surveys in "Sent" status that have not been completed within a configurable number of days. LimeSurvey's `remind_participants` API method supports this natively.

### 10.3 Survey Versioning

If survey templates are updated over time, the system should track which version of a template was used for each survey instance. This could be handled by adding a `templateVersion` field to the Survey entity and tagging LimeSurvey survey groups by version.

### 10.4 Dashboard and Reporting

With promoted fields on the Survey entity, EspoCRM's built-in reporting tools (or the Advanced Pack's Report functionality) can be used to build dashboards showing:

- Average satisfaction ratings by time period
- NPS trends across engagements
- Survey completion rates by type
- Engagement health indicators based on survey responses

### 10.5 Mentor Engagement Application Integration

The planned Mentor Engagement Application (React web app) could include survey-related views — for example, showing survey status and key metrics alongside engagement details in the cross-entity views that the application is designed to support.
