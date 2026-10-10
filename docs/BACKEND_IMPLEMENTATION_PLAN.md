# Backend Implementation Plan: Simple Surveys

## 1. System Overview & Core Objectives
This document establishes the architectural and implementation plan for the **Simple Surveys Backend**. This repository is strictly dedicated to hosting the backend service responsible for managing survey configurations, scheduling/dispatching survey notifications, and ingesting anonymous survey responses and associated media.

### Core Architecture & Boundaries
- **Backend Exclusivity**: Focuses purely on backend data storage, validation, scheduling, and API endpoints.
- **Anonymous Submissions (Zero Participant Tracking)**: The backend does not track, register, or profile participants. Each survey submission is treated as an independent, standalone anonymous event.
- **Dedicated Persistent Server**: The backend is hosted on a long-running server instance (no serverless functions or ephemeral runtimes).
- **Local Server Storage (Temporary Engine)**: In the absence of a database or active Microsoft Graph API access, survey responses, configurations, and uploaded images are saved directly to designated folders on the running server.
- **Future Microsoft Graph API Preparedness**: The persistence layer is abstracted via Object-Oriented repository interfaces to allow a drop-in migration to Microsoft Graph API (OneDrive/SharePoint) once credentials are provided.
- **Decoupled Survey Definitions**: Surveys are defined completely independently from sampling schedules. Survey JSON files define their own questions, weights, and notification prompt copy (`notification_prompt`). The sampling configuration simply references surveys by `survey_id`.
- **Configurable Surveys & Admin Creation Endpoint**: Survey structures (questions, validation rules, rating scales) are fully dynamic. An administrative `POST /api/surveys` endpoint is provided so a future admin GUI can create and update survey JSON definitions without manual file manipulation.
- **Flexible Notification Scheduling (Fixed & Randomized)**:
  - Admins can fix surveys to specific positions (`first`, `last`) or explicit times (`08:30`).
  - If a survey is fixed to `first` or `last` without an explicit scheduled time, its dispatch time is **randomized within the dedicated first/last window** (e.g., 08:00–09:30 or 20:30–22:00), rather than snapping to the boundary.
  - Option to randomize all survey prompts or run in a hybrid mode.
- **Configurable "Time to Complete" (Expiration Window)**:
  - A global `time_to_complete_minutes` setting (e.g., 5 minutes) enforces that surveys must be submitted within $N$ minutes of `notification_sent_at`.
  - Expired submissions are still persisted to record receipt, but their `answers` are autofilled as empty (`[]`) with an audit status message (`"User failed to complete survey within 5 minutes of notification dispatch"`).
- **Paired Response & Image Naming**: Uploaded images are stored separately in `images/` but inherit the **exact same ID and timestamp prefix** as their corresponding JSON response (e.g., `2026-10-10T14-18-22_resp_8f4a1c9e.json` matches `2026-10-10T14-18-22_img_8f4a1c9e.jpg`) for immediate readability and correlation.
- **Simplicity & Readability**: Follows clean Python/FastAPI conventions. Automated testing is explicitly deferred and omitted from this phase.

---

## 2. Python / FastAPI Architectural Conventions vs. C# & Go

For developers familiar with C# (.NET) and Go architectures, the naming conventions in FastAPI correspond directly to familiar enterprise patterns:

| C# / Go Convention | FastAPI / Python Idiomatic Convention | Project Directory | Purpose in this System |
|---|---|---|---|
| **Controllers / Handlers** | **API Routers / Endpoints** | `app/api/` | HTTP request routing, parameter parsing, status codes, and response generation. |
| **Services / Business Logic** | **Services** | `app/services/` | Business workflows, notification scheduling, randomized sampling math, and orchestration. |
| **Repositories / Data Access** | **CRUD / Repositories** | `app/crud/` | Data persistence abstractions, local filesystem read/write, and future Microsoft Graph calls. |
| **DTOs (Data Transfer Objects)** | **Schemas (Pydantic Models)** | `app/schemas/` | Type-safe data validation, serialization, and contract definitions for ingress/egress data. |

By adopting `api`, `services`, `crud`, and `schemas`, the project adheres to standard FastAPI architecture while preserving the clean separation expected in C# and Go.

---

## 3. Object-Oriented Programming (OOP) & Architecture Best Practices

The system applies the **Four Pillars of OOP** and **SOLID Design Principles** across all layers.

### 3.1. The Four Pillars of OOP

1. **Encapsulation**:
   - Disk file paths, directory traversal, async file writes, and image streaming are encapsulated inside `app/crud/`.
   - Business services and API controllers interact only with strongly typed DTOs (`schemas`), remaining unaware of file handling mechanics.
2. **Abstraction**:
   - `BaseStorageRepository` (`app/crud/base.py`) defines abstract persistence contracts (`save_response`, `save_image`, `get_survey`, `save_survey`).
   - `BaseNotificationDispatcher` (`app/services/dispatchers/base.py`) abstracts the notification delivery transport (e.g., APNs, FCM, WebPush, or webhook).
3. **Inheritance**:
   - Concrete repositories (`FileStorageRepository`, future `MSGraphStorageRepository`) inherit from `BaseStorageRepository`.
   - Pydantic DTOs inherit from shared base models (`app/schemas/common.py`).
4. **Polymorphism**:
   - **Storage Engines**: Local filesystem and Microsoft Graph API repositories share the exact same interface and can be swapped dynamically via FastAPI dependency injection.
   - **Survey Questions**: Dynamic question types (`RatingScaleQuestion`, `ChoiceQuestion`, `TextQuestion`) adhere to a common question interface with polymorphic validation behavior.

### 3.2. SOLID Principles in Practice

- **Single Responsibility Principle (SRP)**:
  - `app/schemas/`: Handles strictly data validation, serialization, and DTO contracts.
  - `app/crud/`: Handles strictly persistence (JSON files, image saving, folder organization).
  - `app/services/`: Handles scheduling math, survey randomization, and notification dispatch logic.
  - `app/api/`: Handles strictly HTTP transport and status codes.
- **Open/Closed Principle (OCP)**:
  - Adding a new storage backend (such as Microsoft Graph API) or notification transport requires implementing a new subclass without altering existing endpoints or schemas.
- **Liskov Substitution Principle (LSP)**:
  - Any implementation of `BaseStorageRepository` can be substituted at runtime without breaking API contracts.
- **Interface Segregation Principle (ISP)**:
  - Repositories and dispatchers define small, cohesive interfaces rather than bloated monoliths.
- **Dependency Inversion Principle (DIP)**:
  - Controllers and services depend on repository and dispatcher abstractions, provided at runtime using FastAPI's `Depends` injection container.

---

## 4. Technology Stack & Dependencies

| Library / Framework | Version Category | Purpose |
|---|---|---|
| **FastAPI** | `fastapi >= 0.110.0` | High-performance async web framework for API routing and OpenAPI documentation. |\
| **Pydantic** | `pydantic >= 2.6.0` | Strict DTO validation, data parsing, and settings management. |\
| **Pydantic-Settings** | `pydantic-settings >= 2.2.0` | Environment variable and configuration parsing. |\
| **Uvicorn** | `uvicorn[standard] >= 0.28.0` | ASGI production server for running on the persistent host. |\
| **aiofiles** | `aiofiles >= 23.2.0` | Asynchronous file I/O for non-blocking JSON and image writes. |\
| **APScheduler** | `apscheduler >= 3.10.4` | In-process background scheduler for evaluating notification windows and triggers. |\
| **python-multipart** | `python-multipart >= 0.0.9` | Streaming multipart/form-data support for image uploads. |\
| **python-dotenv** | `python-dotenv >= 1.0.0` | Loading `.env` environment variables. |\
| *Future: msgraph-core / httpx* | *Planned* | Future Microsoft Graph API integration for cloud storage. |\

---

## 5. Directory Structure

The directory structure is unversioned, clean, and modular:

```
Simple-Surveys-Backend/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app creation, lifecycle (scheduler start/stop), CORS
│   ├── config.py                        # Pydantic BaseSettings (file paths, sampling rules, server port)
│   ├── dependencies.py                  # Dependency injection providers (storage repository, notification service)
│   │
│   ├── api/                             # Controllers / Route Handlers
│   │   ├── __init__.py
│   │   ├── router.py                    # Root router registering surveys, responses, notifications, health
│   │   ├── health.py                    # GET /api/health
│   │   ├── surveys.py                   # GET, POST, PUT /api/surveys
│   │   ├── responses.py                 # POST, GET /api/responses (data + multipart image)
│   │   └── notifications.py             # GET, PUT /api/notifications/schedule, POST /api/notifications/devices
│   │
│   ├── services/                        # Business Logic & Orchestration
│   │   ├── __init__.py
│   │   ├── scheduler_service.py         # Evaluates active windows, computes fixed & randomized times, triggers dispatches
│   │   ├── survey_selector.py           # Selects fixed anchor surveys or random surveys based on rules
│   │   └── dispatchers/                 # Notification transports
│   │       ├── __init__.py
│   │       ├── base.py                  # BaseNotificationDispatcher interface
│   │       └── push_dispatcher.py       # Push notification dispatcher (APNs / FCM / WebPush)
│   │
│   ├── crud/                            # Repositories / Data Access Layer
│   │   ├── __init__.py
│   │   ├── base.py                      # BaseStorageRepository abstract base class
│   │   ├── file_storage.py              # Local server filesystem JSON & image persistence
│   │   └── ms_graph_storage.py          # Scaffold for future Microsoft Graph API integration
│   │
│   └── schemas/                         # DTOs (Pydantic Models)
│       ├── __init__.py
│       ├── common.py                    # Shared schemas (timestamps, location, pagination)
│       ├── survey_config.py             # Survey creation & retrieval DTOs
│       ├── survey_response.py           # Ingress survey responses, answers, and image associations
│       └── notification_config.py       # Notification window settings, daily quota, device registrations
│
├── data/                                # Designated server storage directory
│   ├── surveys/                         # Stored survey definition files (JSON)
│   │   ├── morning_checkin.json
│   │   ├── random_esm.json
│   │   └── night_survey.json
│   │
│   ├── schedule_config/                 # Notification and sampling configuration (JSON)
│   │   └── sampling_rules.json
│   │
│   └── responses/                       # Submissions organized by survey_id
│       └── {survey_id}/
│           ├── data/                    # JSON submission records
│           │   └── {timestamp}_resp_{id}.json
│           └── images/                  # Associated submission images (identically keyed)
│               └── {timestamp}_img_{id}.jpg
│
├── docs/
│   └── BACKEND_IMPLEMENTATION_PLAN.md    # This architectural specification
├── .env.example                         # Environment configuration template
├── .gitignore                           # Git ignore rules
├── requirements.txt                     # Python dependencies
└── README.md                            # Setup and run instructions
```

---

## 6. Configurable Survey System & Question Types

Surveys are created and maintained **completely separately** from the sampling schedule configuration. A survey owns its title, description, push notification prompt text, sampling weight, and list of questions.

### 6.1. Survey Definition DTO (`app/schemas/survey_config.py`)
- **Survey Attributes**:
  - `survey_id`: Unique identifier (e.g., `morning_checkin`).
  - `title`: Display title in the app.
  - `description`: Optional instructions or overview.
  - `notification_prompt`: The push notification copy displayed when this survey is triggered:
    - `title`: Notification title (e.g., `"Morning Check-in"`).
    - `body`: Notification body text (e.g., `"Good morning! Please log your start-of-day state."`).
  - `weight`: Numeric weight used if selected as part of a randomized pool (default: 1.0).
  - `is_active`: Boolean flag indicating if survey is open for sampling.
  - `questions`: List of question definitions.

### 6.2. Supported Question Types & Schemas
The system supports five polymorphic question types:
1. `rating_scale`: Numerical scale (e.g., 1–7 or 1–10).
2. `single_choice`: Select one option from a list.
3. `multiple_choice`: Select one or more options from a list.
4. `text`: Free-form text entry.
5. `numeric`: Raw numeric integer or float entry.

---

### 6.3. Example Survey Configuration JSON (`data/surveys/comprehensive_sample_survey.json`)

```json
{
  "survey_id": "comprehensive_sample_survey",
  "title": "Comprehensive Experience Sampling Survey",
  "description": "Daily sample prompt showcasing all available question types and validation rules.",
  "notification_prompt": {
    "title": "Quick Survey Check-in",
    "body": "Please take a moment to record your current state and snap a surroundings photo."
  },
  "weight": 1.5,
  "is_active": true,
  "questions": [
    {
      "question_id": "q_mood_scale",
      "prompt": "How are you feeling right now on a scale from 1 (very negative) to 10 (very positive)?",
      "type": "rating_scale",
      "is_required": true,
      "validation_rules": {
        "min_value": 1,
        "max_value": 10,
        "step": 1,
        "min_label": "Very Negative",
        "max_label": "Very Positive"
      }
    },
    {
      "question_id": "q_current_location_type",
      "prompt": "Where are you currently located?",
      "type": "single_choice",
      "is_required": true,
      "validation_rules": {
        "options": [
          "Home",
          "Workplace / Office",
          "School / University",
          "Transit / Commuting",
          "Outdoors / Nature",
          "Other"
        ]
      }
    },
    {
      "question_id": "q_social_context",
      "prompt": "Who is currently with you? (Select all that apply):",
      "type": "multiple_choice",
      "is_required": false,
      "validation_rules": {
        "options": [
          "Alone",
          "Colleagues / Classmates",
          "Friends",
          "Family / Partner",
          "Strangers"
        ],
        "min_selections": 1,
        "max_selections": 4
      }
    },
    {
      "question_id": "q_activity_notes",
      "prompt": "Briefly describe what you were doing immediately before this notification:",
      "type": "text",
      "is_required": false,
      "validation_rules": {
        "min_length": 0,
        "max_length": 300,
        "placeholder": "e.g., Reading research papers in the library."
      }
    },
    {
      "question_id": "q_hours_slept",
      "prompt": "How many hours of sleep did you get last night?",
      "type": "numeric",
      "is_required": true,
      "validation_rules": {
        "min_value": 0.0,
        "max_value": 24.0,
        "allow_decimals": true
      }
    }
  ]
}
```

---

## 7. Notification Scheduling & Survey Dispatch Logic

### 7.1. Decoupled Sampling Configuration
The sampling configuration in `data/schedule_config/sampling_rules.json` strictly defines **when** surveys are dispatched, referencing surveys exclusively by `survey_id`. It does not duplicate title, body, or weights:
- **Modes**:
  - `hybrid`: Dedicated anchor surveys + randomized daytime prompts.
  - `all_random`: All prompts of the day are chosen at random from the pool.
  - `all_fixed`: All prompts occur at predefined times.
- **Fixed Survey Randomization within Dedicated Windows**:
  - If a survey is set to `position: "first"` without an explicit `scheduled_time`, its dispatch time is **randomized within the `first_window`** (e.g., 08:00–09:30). It does not snap to the global `window_start`.
  - If a survey is set to `position: "last"` without an explicit `scheduled_time`, its dispatch time is **randomized within the `last_window`** (e.g., 20:30–22:00). It does not snap to the global `window_end`.
  - Intraday prompts are randomly placed between the calculated first and last dispatch times, enforcing `min_interval_minutes`.
- **Global "Time to Complete" Expiration Window**:
  - `time_to_complete_minutes` (e.g., `5`): Configures how long a participant has to submit a survey after `notification_sent_at`.

---

### 7.2. Example Sampling Configuration JSON (`data/schedule_config/sampling_rules.json`)

```json
{
  "mode": "hybrid",
  "time_to_complete_minutes": 5,
  "daily_schedule": {
    "overall_window": {
      "start_time": "08:00",
      "end_time": "22:00"
    },
    "first_window": {
      "start_time": "08:00",
      "end_time": "09:30"
    },
    "last_window": {
      "start_time": "20:30",
      "end_time": "22:00"
    }
  },
  "fixed_surveys": [
    {
      "survey_id": "morning_checkin",
      "position": "first"
    },
    {
      "survey_id": "night_survey",
      "position": "last"
    }
  ],
  "randomized_sampling": {
    "prompts_per_day": 4,
    "min_interval_minutes": 90,
    "eligible_survey_ids": [
      "comprehensive_sample_survey",
      "mood_pulse",
      "social_interaction_check"
    ]
  }
}
```

> **Note on Behavior**: In the above configuration, `morning_checkin` will be dispatched at a randomly selected minute between 08:00 and 09:30. `night_survey` will be dispatched at a randomly selected minute between 20:30 and 22:00. The 4 intraday prompts will be spaced throughout the remaining middle window, sampling randomly from `eligible_survey_ids` using the weights declared in their respective survey JSON files.

---

### 7.3. Dispatch Architecture (`app/services/scheduler_service.py`)
- **Engine**: Runs within the server process via `APScheduler` (started on FastAPI lifespan startup).
- **Daily Schedule Calculation**:
  1. For `position: "first"`, picks a uniform random time within `first_window` (unless an explicit `scheduled_time` is given).
  2. For `position: "last"`, picks a uniform random time within `last_window` (unless an explicit `scheduled_time` is given).
  3. Divides the interval between the first and last dispatch to place `prompts_per_day` randomized slots, enforcing `min_interval_minutes`.
  4. For each randomized slot, `survey_selector.py` selects a survey from `eligible_survey_ids`, looking up its `weight` from the loaded survey configuration.
- **Dispatcher Interface (`BaseNotificationDispatcher`)**:
  - Delivers notifications to registered devices using the copy found in `survey.notification_prompt`.

---

## 8. Anonymous Response Ingestion & Storage Architecture

### 8.1. Data Ingestion & Expiration Validation
Every submission is anonymous. No participant identifier is collected or tracked.

#### "Time to Complete" Expiration Rule
When a response is posted to `/api/responses`:
1. The server reads `notification_sent_at` from the submission payload and checks it against the current server time `received_at`.
2. $\Delta t = \text{Date}(\text{received\_at}) - \text{Date}(\text{notification\_sent\_at})$.
3. If $\Delta t > (\text{time\_to\_complete\_minutes} \times 60 \text{ seconds})$:
   - **The survey is expired**.
   - The server **still persists a record** to disk so researchers know the prompt reached the device.
   - The record's `status` is set to `"EXPIRED"`.
   - The `answers` list is **autofilled as empty (`[]`)**.
   - An explanatory note is recorded: `"User failed to complete survey within {time_to_complete_minutes} minutes of notification dispatch."`
   - Location, temporal markers, and photo (if any) are retained for audit and context.
4. If $\Delta t \le (\text{time\_to\_complete\_minutes} \times 60 \text{ seconds})$:
   - **The survey is valid**.
   - The record's `status` is set to `"COMPLETED"`.
   - The submitted `answers` are persisted in full.

#### Image & Response Identifier Parity
To guarantee immediate readability and seamless correlation across the server filesystem:
- The image identifier **strictly mirrors the response identifier**.
- For a response with ID `resp_8f4a1c9e`:
  - **JSON Data File**: `data/responses/{survey_id}/data/2026-10-10T14-18-22_resp_8f4a1c9e.json`
  - **Image File**: `data/responses/{survey_id}/images/2026-10-10T14-18-22_img_8f4a1c9e.jpg`
  - `image_id` in JSON: `img_8f4a1c9e`
  - `image_filename` in JSON: `2026-10-10T14-18-22_img_8f4a1c9e.jpg`

---

### 8.2. Example Valid Response Record (`data/responses/.../2026-10-10T14-18-22_resp_8f4a1c9e.json`)

```json
{
  "response_id": "resp_8f4a1c9e",
  "survey_id": "comprehensive_sample_survey",
  "status": "COMPLETED",
  "status_message": "Survey completed successfully within allowed window.",
  "temporal_markers": {
    "notification_sent_at": "2026-10-10T14:15:00.000Z",
    "started_at": "2026-10-10T14:16:10.000Z",
    "completed_at": "2026-10-10T14:18:22.000Z",
    "received_at": "2026-10-10T14:18:23.120Z",
    "latency_seconds": 203.12,
    "completion_duration_seconds": 132.0,
    "time_to_complete_limit_minutes": 5
  },
  "location": {
    "latitude": 40.036821,
    "longitude": -75.343118,
    "accuracy_meters": 4.2,
    "altitude_meters": 124.5
  },
  "image": {
    "has_image": true,
    "image_id": "img_8f4a1c9e",
    "image_filename": "2026-10-10T14-18-22_img_8f4a1c9e.jpg",
    "relative_path": "images/2026-10-10T14-18-22_img_8f4a1c9e.jpg"
  },
  "answers": [
    {
      "question_id": "q_mood_scale",
      "value": 8
    },
    {
      "question_id": "q_current_location_type",
      "value": "Workplace / Office"
    },
    {
      "question_id": "q_social_context",
      "value": ["Colleagues / Classmates"]
    },
    {
      "question_id": "q_activity_notes",
      "value": "Analyzing dataset results in the research lab."
    },
    {
      "question_id": "q_hours_slept",
      "value": 7.5
    }
  ]
}
```

---

### 8.3. Example Expired Response Record (`data/responses/.../2026-10-10T14-26-00_resp_3e2b9c7a.json`)

```json
{
  "response_id": "resp_3e2b9c7a",
  "survey_id": "comprehensive_sample_survey",
  "status": "EXPIRED",
  "status_message": "User failed to complete survey within 5 minutes of notification dispatch.",
  "temporal_markers": {
    "notification_sent_at": "2026-10-10T14:15:00.000Z",
    "started_at": "2026-10-10T14:24:10.000Z",
    "completed_at": "2026-10-10T14:26:00.000Z",
    "received_at": "2026-10-10T14:26:01.050Z",
    "latency_seconds": 661.05,
    "completion_duration_seconds": 110.0,
    "time_to_complete_limit_minutes": 5
  },
  "location": {
    "latitude": 40.036821,
    "longitude": -75.343118,
    "accuracy_meters": 5.0,
    "altitude_meters": 120.0
  },
  "image": {
    "has_image": false,
    "image_id": null,
    "image_filename": null,
    "relative_path": null
  },
  "answers": []
}
```

---

### 8.4. Separate Storage Layout on Server

Files are stored cleanly separated on the server filesystem, with matched filenames:
```
data/responses/{survey_id}/
├── data/
│   ├── 2026-10-10T14-18-22_resp_8f4a1c9e.json      # Completed submission
│   └── 2026-10-10T14-26-00_resp_3e2b9c7a.json      # Expired submission (answers autofilled empty)
└── images/
    └── 2026-10-10T14-18-22_img_8f4a1c9e.jpg       # Directly mirrors 2026-10-10T14-18-22_resp_8f4a1c9e.json
```
- **`data/`**: Pure JSON records containing all structured metadata, coordinates, timestamps, and answer arrays.
- **`images/`**: Binary image files (`.jpg` / `.png`) captured by the camera., with the ID mirroring the JSON file.

---

### 8.5. Future Microsoft Graph API Migration
`BaseStorageRepository` (`app/crud/base.py`) defines:
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.survey_config import SurveyConfig
from app.schemas.survey_response import SurveyResponseCreate, SurveyResponseRead

class BaseStorageRepository(ABC):
    @abstractmethod
    async def save_survey(self, survey: SurveyConfig) -> SurveyConfig:
        pass

    @abstractmethod
    async def get_survey(self, survey_id: str) -> Optional[SurveyConfig]:
        pass

    @abstractmethod
    async def list_surveys(self) -> List[SurveyConfig]:
        pass

    @abstractmethod
    async def save_response(self, response: SurveyResponseCreate) -> SurveyResponseRead:
        pass

    @abstractmethod
    async def save_image(self, survey_id: str, response_id: str, timestamp_str: str, image_bytes: bytes) -> str:
        """Saves image with filename {timestamp}_img_{id}.jpg mirroring the response record."""
        pass
```
- `FileStorageRepository` implements this for local disk.
- `MSGraphStorageRepository` will implement the same methods using Microsoft Graph API once credentials are provided, uploading JSON and JPG streams directly into corresponding OneDrive folders with identical paired naming.

---

## 9. API Specification & Request/Response Examples

All endpoints are organized cleanly under `/api` without version prefixes.

### 9.1. System Health (`GET /api/health`)
- **Description**: Verifies that the FastAPI server is running and the storage directory is accessible.
- **Response (200 OK)**:
  ```json
  {
    "status": "healthy",
    "storage_backend": "file_storage",
    "storage_path": "data/",
    "active_surveys_count": 3,
    "timestamp": "2026-10-10T00:15:00.000Z"
  }
  ```

---

### 9.2. Survey Management Endpoints

#### `GET /api/surveys`
- **Description**: Returns all active surveys.
- **Response (200 OK)**: List of `SurveyConfig` objects.

#### `GET /api/surveys/{survey_id}`
- **Description**: Returns a specific survey definition.
- **Response (200 OK)**: Single `SurveyConfig` object.

#### `POST /api/surveys` (Admin GUI Endpoint)
- **Description**: Creates and persists a new survey JSON file in `data/surveys/{survey_id}.json`.
- **Request Body (`SurveyConfigCreate`)**:
  ```json
  {
    "survey_id": "afternoon_stress_pulse",
    "title": "Afternoon Stress Pulse",
    "description": "Short 2-question afternoon prompt.",
    "notification_prompt": {
      "title": "Afternoon Check-in",
      "body": "Quick stress check-in for this afternoon."
    },
    "weight": 2.0,
    "is_active": true,
    "questions": [
      {
        "question_id": "q_stress_now",
        "prompt": "Current stress level from 1 (calm) to 5 (overwhelmed):",
        "type": "rating_scale",
        "is_required": true,
        "validation_rules": {
          "min_value": 1,
          "max_value": 5
        }
      },
      {
        "question_id": "q_quick_comment",
        "prompt": "What is the primary source of stress right now?",
        "type": "text",
        "is_required": false,
        "validation_rules": {
          "max_length": 150
        }
      }
    ]
  }
  ```
- **Response (201 Created)**: Returns the saved `SurveyConfig` object.

#### `PUT /api/surveys/{survey_id}` (Admin GUI Endpoint)
- **Description**: Updates an existing survey configuration file.
- **Response (200 OK)**: Returns the updated `SurveyConfig` object.

---

### 9.3. Response Submission Endpoint (`POST /api/responses`)
- **Description**: Ingests survey submission data and optional camera photo. Evaluates `time_to_complete_minutes` window.
- **Supported Formats**:
  - **Multipart Form-Data**: Supports sending the JSON payload as a string or form fields, plus the uploaded file in a single HTTP request:
    - Form field `data`: JSON string matching `SurveyResponseCreate`.
    - Form field `image`: Uploaded image file (e.g., JPEG/PNG).
  - **Pure JSON**: For submissions where photos are optional or uploaded via a distinct step.

#### Example Request Payload (`data` field):
```json
{
  "survey_id": "afternoon_stress_pulse",
  "notification_sent_at": "2026-10-10T15:00:00.000Z",
  "started_at": "2026-10-10T15:02:10.000Z",
  "completed_at": "2026-10-10T15:03:05.000Z",
  "location": {
    "latitude": 40.036821,
    "longitude": -75.343118,
    "accuracy_meters": 3.8,
    "altitude_meters": 120.0
  },
  "answers": [
    {
      "question_id": "q_stress_now",
      "value": 3
    },
    {
      "question_id": "q_quick_comment",
      "value": "Upcoming project deadline."
    }
  ]
}
```

#### Example Valid Response (201 Created):
```json
{
  "response_id": "resp_e7a1b3c5",
  "survey_id": "afternoon_stress_pulse",
  "status": "COMPLETED",
  "image_stored": true,
  "image_filename": "2026-10-10T15-03-05_img_e7a1b3c5.jpg",
  "received_at": "2026-10-10T15:03:06.014Z"
}
```

#### Example Expired Response (200 OK):
```json
{
  "response_id": "resp_3e2b9c7a",
  "survey_id": "afternoon_stress_pulse",
  "status": "EXPIRED",
  "message": "User failed to complete survey within 5 minutes of notification dispatch.",
  "image_stored": false,
  "received_at": "2026-10-10T15:08:12.100Z"
}
```

---

### 9.4. Notifications & Device Registration Endpoints

#### `GET /api/notifications/schedule`
- **Description**: Returns the active sampling rules and schedule configuration.
- **Response (200 OK)**: Full JSON content matching `sampling_rules.json`.

#### `PUT /api/notifications/schedule` (Admin GUI Endpoint)
- **Description**: Updates the daily sampling rules (e.g. changing fixed surveys, quota, or randomized windows).
- **Response (200 OK)**: Updated configuration object.

#### `POST /api/notifications/devices`
- **Description**: Registers an anonymous device push token for receiving scheduled prompts.
- **Request Body**:
  ```json
  {
    "device_token": "apns_7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a",
    "platform": "ios",
    "timezone": "America/New_York",
    "registered_at": "2026-10-10T00:15:00.000Z"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "status": "registered",
    "device_token": "apns_7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a"
  }
  ```

---

## 10. Implementation Roadmap

### Phase 1: Environment & Project Foundation
- Establish the folder structure (`app/api/`, `app/services/`, `app/crud/`, `app/schemas/`).
- Initialize storage folders: `data/surveys/`, `data/responses/`, and `data/schedule_config/`.
- Configure `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `aiofiles`, `apscheduler`, `python-multipart`, `python-dotenv`).
- Implement `app/config.py` for storage directories, server settings, and scheduling parameters.

### Phase 2: DTO Schemas (Pydantic Models)
- Implement `app/schemas/survey_config.py` (survey templates, notification prompt text, all 5 question types, validation rules).
- Implement `app/schemas/survey_response.py` (answers, location coordinates, temporal markers, image pointers, expiration status).
- Implement `app/schemas/notification_config.py` (fixed vs randomized rules, dedicated first/last windows, expiration limit, device registration).

### Phase 3: Persistence Layer (CRUD / Repositories)
- Define `BaseStorageRepository` in `app/crud/base.py`.
- Implement `FileStorageRepository` in `app/crud/file_storage.py` handling asynchronous JSON storage and separate image file writes using matched identifiers.
- Scaffold `MSGraphStorageRepository` in `app/crud/ms_graph_storage.py` as an interface stub for future Microsoft Graph API integration.
- Implement dependency injection provider in `app/dependencies.py`.

### Phase 4: Business Logic & Scheduling Services
- Implement `survey_selector.py` supporting survey lookup by ID and weighted randomized selection using the weight defined in each survey's JSON.
- Implement `scheduler_service.py` with `APScheduler` to manage daily windows, randomize times within `first_window` and `last_window`, randomize intraday slots, and trigger dispatches.
- Implement expiration validator checking `(received_at - notification_sent_at) > time_to_complete_minutes`.
- Implement `BaseNotificationDispatcher` and push transport in `app/services/dispatchers/`.

### Phase 5: API Endpoints & FastAPI Assembly
- Implement survey endpoints (including admin `POST /api/surveys` and `PUT /api/surveys/{survey_id}`) in `app/api/surveys.py`.
- Implement response ingestion with location, temporal markers, expiration autofill logic, and multipart image handling in `app/api/responses.py`.
- Implement notification endpoints in `app/api/notifications.py`.
- Implement health endpoint in `app/api/health.py`.
- Wire routers and lifespan events (scheduler startup/shutdown) in `app/main.py`.
