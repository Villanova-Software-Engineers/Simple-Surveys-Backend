# Simple Surveys Backend

A high-performance, asynchronous persistent backend service built with Python and FastAPI for experience sampling surveys (ESM), notification scheduling, and anonymous response ingestion with optional photo attachments.

## Core Features

- **Anonymous Submissions**: Zero participant tracking or profiling. Every submission is an independent event.
- **Persistent Server Architecture**: Runs on a dedicated server process with in-process background scheduling (`APScheduler`).
- **Separation of Concerns**: Surveys and sampling schedules are completely decoupled. Surveys define questions, weights, and notification copy; schedule configurations define windows and dispatch timing.
- **Fixed & Randomized Notification Dispatching**:
  - Fixed surveys (`first`, `last`) randomize within dedicated morning/night windows (e.g. 08:00–09:30, 20:30–22:00) or adhere to explicit times.
  - Intraday prompts are stratified and randomized with configurable minimum intervals.
  - Survey selection uses dynamic weights declared in each survey's definition.
- **Expiration Window ("Time to Complete")**:
  - Global `time_to_complete_minutes` window (e.g., 5 minutes) validates completion latency against notification dispatch time.
  - Expired submissions are still persisted for audit, but answers are autofilled empty (`[]`) with an audit reason message.
- **Paired Response & Image Storage**:
  - JSON submission: `data/responses/{survey_id}/data/{timestamp}_resp_{id}.json`
  - Image photo: `data/responses/{survey_id}/images/{timestamp}_img_{id}.jpg`
- **Pluggable Storage Repositories**:
  - Local server filesystem persistence (`FileStorageRepository`).
  - Drop-in scaffold prepared for Microsoft Graph API OneDrive/SharePoint integration (`MSGraphStorageRepository`).

---

## Directory Structure

```text
Simple-Surveys-Backend/
├── app/
│   ├── api/                     # API routers (health, surveys, responses, notifications)
│   ├── crud/                    # Repositories (FileStorageRepository, MSGraphStorageRepository)
│   ├── schemas/                 # Pydantic DTO models
│   ├── services/                # Business logic (SchedulerService, SurveySelector, Dispatchers)
│   ├── config.py                # Pydantic BaseSettings
│   ├── dependencies.py          # FastAPI dependency injection
│   └── main.py                  # FastAPI application entrypoint & lifecycle
├── data/
│   ├── surveys/                 # Survey definition JSON files
│   ├── schedule_config/         # Notification & sampling rules JSON
│   ├── responses/               # Organized JSON submissions and paired images
│   └── devices/                 # Registered push notification device tokens
├── docs/
│   └── BACKEND_IMPLEMENTATION_PLAN.md
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup & Running

### 1. Prerequisites
- Python 3.15+

### 2. Installation
```bash
# Clone the repository
git clone <repo-url>
cd Simple-Surveys-Backend

# Create and activate virtual environment
python -m venv env
# On Windows:
.\env\Scripts\activate
# On Linux/macOS:
source env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Configuration variables:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Host address to bind |
| `PORT` | `8000` | Port to listen on |
| `DEBUG` | `false` | Enable debug logging |
| `ALLOWED_ORIGINS` | `["*"]` | Allowed CORS origins |
| `STORAGE_BACKEND` | `file_storage` | Storage engine (`file_storage` or `ms_graph`) |
| `DATA_DIR` | `data` | Base directory for file storage |
| `TIME_TO_COMPLETE_MINUTES` | `5` | Expiration window in minutes |
| `SCHEDULER_TIMEZONE` | `America/New_York` | Timezone for dispatch windows |

### 4. Running the Server
```bash
python -m app.main
```

Once running:
- **API Base**: `http://localhost:8000/api`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## API Endpoints

### System Health
- `GET /api/health`: System health and active survey count.

### Survey Definitions
- `GET /api/surveys`: Retrieve all active surveys (`?active_only=true|false`).
- `GET /api/surveys/{survey_id}`: Retrieve a specific survey definition.
- `POST /api/surveys`: Create and persist a new survey definition (`201 Created`).
- `PATCH /api/surveys/{survey_id}`: Update an existing survey definition (`200 OK`).
- `DELETE /api/surveys/{survey_id}`: Delete a survey definition (`200 OK`). Supports optional `delete_responses=true|false` and `clean_schedule_references=true|false`.

### Response Ingestion
- `POST /api/responses`: Submit survey answers and optional camera photo.
  - Supports both `multipart/form-data` (form fields `data` and `image`) and `application/json`.
  - Returns `201 Created` for completed submissions.
  - Returns `200 OK` with status `"EXPIRED"` and empty answers if submitted beyond `time_to_complete_minutes`.
- `GET /api/responses`: Retrieve persisted response records (`?survey_id={id}`).
- `GET /api/responses/{survey_id}/{response_id}`: Retrieve a specific response.
- `DELETE /api/responses/{survey_id}/{response_id}`: Delete a response record and optionally its associated photo (`?delete_image=true|false`).
- `GET /api/responses/{survey_id}/images/{filename}`: Download an uploaded response image.

### Notification Scheduling & Devices
- `GET /api/notifications/schedule`: Retrieve active sampling rules (`sampling_rules.json`).
- `POST /api/notifications/schedule`: Create or update (upsert) daily sampling rules and refresh daily schedule.
- `POST /api/notifications/devices`: Register an anonymous device push notification token.
- `GET /api/notifications/devices`: List registered devices.
- `DELETE /api/notifications/devices/{device_token}`: Unregister and delete a device token, stopping future notifications.
