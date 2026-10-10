# Backend Implementation Plan: Simple Surveys

## 1. System Overview & Architectural Objectives
This document defines the production backend architecture for **Simple Surveys**, a lightweight Experience Sampling Method (ESM) system designed for real-time, high-frequency psychological research data collection (mood, stress, activity).

### Core Goals & Constraints
- **Backend Only**: Focus strictly on the Firebase Functions backend, Firestore database schemas, push notification engine, and Microsoft OneDrive export pipeline.
- **Data Sovereignty & University Compliance**: Data is directly written to the lab's Microsoft OneDrive via Microsoft Graph API (OAuth 2.0 Client Credentials Grant). Data is stored natively as structured JSON.
- **Participant Privacy & IRB Compliance**: Zero hardware identifier collection (no IDFA, MAC, IMEI, phone numbers). Participants are assigned anonymous researcher tokens (`P01`–`P30`), strictly capped at 30 participants.
- **High-Precision ESM Latency**: All temporal markers (notification dispatched, survey opened, survey completed) are validated and tracked with millisecond resolution to determine response latency and enforce survey expiration windows.
- **Brand Neutrality**: Repository, configuration, and storage paths do not reference the university name.

---

## 2. Technology Stack

| Layer | Component | Description / Rationale |
|---|---|---|
| **Runtime** | Node.js 20 LTS + TypeScript | Strict typing, robust async handling, modern ES modules |
| **Serverless Engine** | Firebase Functions v2 (`firebase-functions/v2`) | Cloud Run-backed, low cold starts, native secret management |
| **Database** | Cloud Firestore | Low-latency state buffer, schedule configs, and audit logs |
| **File Storage Buffer** | Cloud Storage for Firebase | Short-lived secure staging bucket for captured survey photos |
| **Permanent Archival** | Microsoft Graph API (`@microsoft/microsoft-graph-client`, `@azure/msal-node`) | Automated client credentials synchronization to OneDrive |
| **Push Notifications** | Firebase Cloud Messaging (FCM) + APNs | High-priority background and alert pushes for iOS devices |
| **Validation** | Zod (`zod`) | Runtime schema validation for all ingress payloads |
| **Task Scheduling** | Cloud Scheduler (`onSchedule`) | 15-minute cron for deterministic and randomized ESM prompts |
| **Secrets Management** | Google Cloud Secret Manager (`defineSecret`) | Encrypted storage for Azure tenant/client credentials |

---

## 3. Recommended Repository File Structure

A clean, modular architecture separating controllers, services, database models, schemas, and scheduled tasks:

```
Simple-Surveys-Backend/
├── .env.example                               # Local environment variable template
├── .gitignore                                 # Git ignore (node_modules, lib, secrets)
├── firebase.json                              # Firebase project configuration (functions, firestore, storage)
├── firestore.rules                            # Firestore security rules (least-privilege access)
├── firestore.indexes.json                     # Query indexes (schedule evaluation queries)
├── storage.rules                              # Staging bucket security rules
├── package.json                               # Workspace / root metadata
├── docs/
│   └── BACKEND_IMPLEMENTATION_PLAN.md         # This architectural specification
└── functions/
    ├── package.json                           # Backend dependencies & build scripts
    ├── tsconfig.json                          # Strict TypeScript compiler options
    ├── .eslintrc.js                           # Linting rules
    ├── src/
    │   ├── index.ts                           # Cloud Functions registration and export index
    │   │
    │   ├── config/                            # Environment and operational configuration
    │   │   ├── env.ts                         # Validated env vars and Firebase secrets definitions
    │   │   └── constants.ts                   # Study constraints (MAX_PARTICIPANTS = 30, expiration rules)
    │   │
    │   ├── core/                              # Infrastructure initializers
    │   │   ├── firebase.ts                    # Firebase Admin SDK initialization
    │   │   └── errors.ts                      # Custom HTTP/Domain error classes & global handler
    │   │
    │   ├── types/                             # Pure TypeScript models & interfaces
    │   │   ├── participant.types.ts           # Participant entity, enrollment, device tokens
    │   │   ├── survey.types.ts                # Survey templates, question types, expiration
    │   │   ├── schedule.types.ts              # Sampling windows, random intervals, dispatches
    │   │   ├── response.types.ts              # Survey response, latency, location, health
    │   │   └── onedrive.types.ts              # MS Graph sync status, payload schemas
    │   │
    │   ├── schemas/                           # Zod schemas for runtime request validation
    │   │   ├── participant.schema.ts          # Registration & token update validation
    │   │   ├── survey.schema.ts               # Survey definition and config validation
    │   │   └── response.schema.ts             # Inbound survey response and metadata validation
    │   │
    │   ├── services/                          # Core business logic layer
    │   │   ├── participant.service.ts         # Enforce 30-user quota, anonymous ID mapping, token tracking
    │   │   ├── scheduler.service.ts           # Window calculations (morning/night/random ESM sampling)
    │   │   ├── fcm.service.ts                 # High-priority APNs push packaging & dispatch
    │   │   ├── response.service.ts            # Latency math, expiration enforcement, Firestore storage
    │   │   └── onedrive.service.ts            # Azure MSAL auth & Microsoft Graph API sync worker
    │   │
    │   ├── controllers/                       # HTTP / Callable function endpoints
    │   │   ├── participant.controller.ts      # POST /registerParticipant, POST /updateToken
    │   │   ├── survey.controller.ts           # GET /activeSurveys, POST /submitResponse
    │   │   └── admin.controller.ts            # GET /studyStatus, POST /configureStudy
    │   │
    │   ├── scheduled/                         # Cron triggers (Cloud Scheduler)
    │   │   ├── esm-notifier.cron.ts           # Runs every 15 minutes to evaluate due prompts
    │   │   └── onedrive-retry.cron.ts         # Retries failed OneDrive uploads from sync queue
    │   │
    │   ├── triggers/                          # Event-driven Firestore triggers
    │   │   ├── on-response-created.ts         # Automatically triggers OneDrive upload upon submission
    │   │   └── on-image-uploaded.ts           # Streams staged photo from Cloud Storage to OneDrive
    │   │
    │   └── utils/                             # Shared utility functions
    │       ├── logger.ts                      # Cloud Logging wrapper with structured metadata
    │       ├── date.ts                        # Timezone math, UTC conversions, ISO formatting
    │       └── geo.ts                         # GPS validation and bounding sanitization
    │
    └── tests/                                 # Automated test suite
        ├── unit/                              # Scheduler logic, latency calculation, Zod validations
        └── integration/                       # Graph API mock, Firestore emulator tests
```

---

## 4. Core Features & Technical Specification

### 4.1. Anonymous Participant & Quota Management
- **Anonymous Identifier**: Participants enroll with a researcher-provided Subject ID (`P01`–`P30`) or an anonymous opaque UUID. No personal identifiers (email, name, phone number, IMEI, IDFA) are ever accepted or stored.
- **Strict Quota Limit**: `MAX_PARTICIPANTS = 30`. A database transaction on `/study_configs/default` checks active enrolled count. Once 30 is reached, registration attempts are rejected with `RESOURCE_EXHAUSTED` (HTTP 429 / 400).
- **Device Token Registry**: iOS client sends its FCM token upon APNs permission grant, along with its IANA timezone (e.g., `America/New_York`). Token updates are idempotent.

### 4.2. Configurable Notification & Sampling Engine (ESM)
- **Survey Types**:
  1. **Morning Survey**: Fixed daily window (e.g., 08:00–10:00 local time).
  2. **Night Survey**: Fixed daily evening window (e.g., 20:30–22:30 local time).
  3. **Random Daytime ESM Prompts**: Configurable number of prompts per day (e.g., 4 to 6). Randomized within designated active hours (e.g., 10:00–20:00), enforcing a minimum spacing interval (e.g., at least 90 minutes between prompts) to prevent prompt clustering.
- **15-Minute Scheduler Execution (`esm-notifier.cron.ts`)**:
  - Cloud Scheduler triggers the function every 15 minutes (`*/15 * * * *`).
  - Iterates active participants and computes their current local time based on their stored timezone.
  - Generates or reads the participant's daily randomized sampling slots.
  - If a slot falls within the current 15-minute window and hasn't yet been dispatched:
    1. Generates a unique `notificationId`.
    2. Writes a record to `/notification_dispatches` with status `DISPATCHED`, `scheduledFor`, `sentAt`, and `expiresAt` (e.g., sentAt + 20 minutes).
    3. Dispatches FCM notification with high-priority APNs payload:
       ```json
       {
         "aps": {
           "alert": {
             "title": "Quick Survey Check-in",
             "body": "Please take a moment to record your current surroundings and state."
           },
           "sound": "default",
           "badge": 1,
           "content-available": 1,
           "headers": { "apns-priority": "10" }
         },
         "data": {
           "notificationId": "notif_abc123",
           "surveyId": "random_esm_v1",
           "sentAt": "2026-10-07T14:15:00.000Z",
           "expiresAt": "2026-10-07T14:35:00.000Z",
           "expirationWindowMinutes": "20"
         }
       }
       ```

### 4.3. Response Ingestion, Expiration & Latency Calculation
- **Payload Schema (`response.schema.ts`)**:
  - `participantId`: string (e.g., `P07`)
  - `notificationId`: string (corresponds to sent dispatch)
  - `surveyId`: string
  - `notificationSentAt`: ISO 8601 string (from push payload)
  - `surveyStartedAt`: ISO 8601 string (when user tapped into survey)
  - `surveyCompletedAt`: ISO 8601 string (when user pressed submit)
  - `location`: object containing `latitude`, `longitude`, `horizontalAccuracy`, `altitude`, `timestamp` (or `null` if permission denied / unavailable)
  - `healthMetrics`: optional object (allows sparse/null fields for steps, heart rate, activity type per user-selected permissions)
  - `answers`: dictionary of question-answer pairs (mood, stress, activity ratings)
  - `photoMetadata`: optional uploaded image identifier / URL
- **Server-Side Latency & Expiration Validation**:
  - `latencyMs = Date.parse(surveyCompletedAt) - Date.parse(notificationSentAt)`
  - `durationMs = Date.parse(surveyCompletedAt) - Date.parse(surveyStartedAt)`
  - Verification against `notification_dispatches`:
    - If `surveyCompletedAt > expiresAt`: status marked as `EXPIRED` (researcher can choose whether to keep with expired flag or reject).
    - If within window: status marked as `COMPLETED`.

### 4.4. Image Upload & Surroundings Capture Pipeline
- **Flow**:
  1. Client requests a pre-signed Cloud Storage upload URL via `POST /getPhotoUploadUrl` or directly uploads to an HTTP endpoint with streaming multipart form data.
  2. Temporary stage in Cloud Storage: `gs://simple-surveys-staging/{participantId}/{notificationId}.jpg`.
  3. Cloud Function trigger (`on-image-uploaded.ts`) or direct response submission streams the binary buffer directly to Microsoft OneDrive.
  4. Deletes the temporary buffer from Cloud Storage to maintain zero unnecessary intermediate data retention.

### 4.5. Microsoft OneDrive Integration via Microsoft Graph API
- **Authentication**:
  - Azure App Registration in the lab's Microsoft 365 tenant.
  - Configured with Application Permissions (Client Credentials Grant): `Files.ReadWrite.All` scoped to the lab drive, requiring no user-facing interactive login.
  - Credentials stored in Google Cloud Secret Manager:
    - `AZURE_TENANT_ID`
    - `AZURE_CLIENT_ID`
    - `AZURE_CLIENT_SECRET`
    - `ONEDRIVE_TARGET_DRIVE_ID` (or User Principal Name)
    - `ONEDRIVE_BASE_FOLDER` (e.g., `/Research_Studies/SimpleSurveys/`)
- **Directory & File Hierarchy in OneDrive**:
  ```
  OneDrive Lab Root/
  └── SimpleSurveys_Data/
      ├── Participant_P01/
      │   ├── responses/
      │   │   ├── 2026-10-07_14-22_random_esm.json
      │   │   └── 2026-10-07_21-05_night.json
      │   └── photos/
      │       └── 2026-10-07_14-22_random_esm.jpg
      ├── Participant_P02/
      │   └── ...
      └── aggregates/
          └── study_master_export.csv  (Updated periodically)
  ```
- **JSON Storage Schema**:
  Every response is stored as an individual, self-contained JSON file:
  ```json
  {
    "submissionId": "resp_xyz789",
    "participantId": "P01",
    "surveyId": "random_esm_v1",
    "notificationId": "notif_abc123",
    "timestamps": {
      "notificationSentAt": "2026-10-07T14:15:00.000Z",
      "surveyStartedAt": "2026-10-07T14:20:12.000Z",
      "surveyCompletedAt": "2026-10-07T14:22:05.000Z",
      "serverReceivedAt": "2026-10-07T14:22:06.120Z",
      "latencyMs": 425000,
      "durationMs": 113000
    },
    "status": "COMPLETED",
    "location": {
      "latitude": 40.0368,
      "longitude": -75.3431,
      "horizontalAccuracyMeters": 4.5,
      "altitudeMeters": 125.0
    },
    "healthMetrics": {
      "stepCountLastHour": 320,
      "heartRateBpm": 74,
      "userAuthorized": ["steps", "heartRate"]
    },
    "responses": {
      "mood_scale": 7,
      "stress_scale": 3,
      "current_activity": "working"
    },
    "photoAttached": true,
    "photoPath": "photos/2026-10-07_14-22_random_esm.jpg"
  }
  ```
- **Resilience & Offline Buffer**:
  - Responses are written first to Firestore `/responses` with `onedriveSyncStatus: "PENDING"`.
  - Background trigger / service immediately uploads to OneDrive.
  - Upon successful upload, marked `SYNCED` with Graph API Drive Item ID.
  - If Microsoft Graph API is throttled or temporarily unavailable, exponential backoff retries via `onedrive-retry.cron.ts` ensure zero data loss.

---

## 5. Security, IRB & Compliance Guardrails
1. **Zero Device Hardware Fingerprinting**: The backend API rejects any payload containing UDID, IDFA, or device serial numbers. Only anonymous `participantId` and rotating APNs push tokens are handled.
2. **Selective HealthKit Data Privacy**: Health data fields are strictly marked optional/nullable in the Zod schema, ensuring the backend respects participants choosing not to share specific health metrics.
3. **Firestore Least-Privilege Rules**: Direct client writes to sensitive study configs or other participants' responses are blocked via `firestore.rules`.
4. **Secret Isolation**: Azure client secrets and Firebase private keys are accessed only at runtime through Google Cloud Secret Manager.

---

## 6. Phased Implementation Roadmap

### Phase 1: Environment & Project Foundation
- Initialize TypeScript Firebase Functions v2 project structure in `Simple-Surveys-Backend`.
- Set up `package.json`, `tsconfig.json`, `.eslintrc.js`, and `.env.example`.
- Configure `firebase.json` and basic `firestore.rules`.

### Phase 2: Domain Schemas, Quota & Participant Management
- Implement Zod validation schemas (`participant.schema.ts`, `response.schema.ts`, `survey.schema.ts`).
- Create `participant.service.ts` with 30-participant maximum quota enforcement and token registration endpoints (`POST /registerParticipant`, `POST /updateToken`).

### Phase 3: ESM Notification & Sampling Engine
- Implement `scheduler.service.ts` for morning/night windows and randomized daytime slots with minimum inter-prompt intervals.
- Integrate `fcm.service.ts` to dispatch high-priority APNs payloads.
- Deploy 15-minute cron trigger `esm-notifier.cron.ts`.

### Phase 4: Response Processing & Latency/Expiration Validation
- Implement `POST /submitResponse` in `response.controller.ts`.
- Calculate server-side response latency (`latencyMs`) and evaluate expiration criteria.
- Handle image staging buffer via Cloud Storage.

### Phase 5: Microsoft OneDrive & Graph API Sync Engine
- Configure MSAL Node client credentials authentication in `onedrive.service.ts`.
- Implement automated JSON upload and image streaming to participant folders in OneDrive.
- Build retry queue (`onedrive-retry.cron.ts`) for resilient sync.

### Phase 6: Testing & End-to-End Verification
- Unit test random scheduling algorithms and Zod schemas.
- Test Graph API upload with simulated payloads.
- Verify quota lock when reaching 30 participants.
