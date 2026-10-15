# CampusShift

CampusShift helps university departments coordinate student employees, class commitments, and work availability. Phase 3 adds work locations, explicit employee eligibility, recurring staffing requirements, and automatic weekly draft scheduling. Accounts, profiles, class/availability management, the landing page, and the health endpoint remain available.

## Technology and prerequisites

- React 19, Vite 7, JavaScript, Tailwind CSS 4, React Router 7.
- Python 3.10+, FastAPI, Uvicorn, SQLAlchemy 2, SQLite, and Alembic.
- Argon2id password hashes and signed, short-lived JWT bearer tokens.
- Node.js 22.13+ and npm (22.22.0 used for verification); Git; Windows PowerShell examples below.

No AWS credentials or services are required. Run commands from the repository root unless a different directory is shown.

## Backend setup and database initialization

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e ..
# Only copy this on first setup; keep an existing .env.
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated value into `JWT_SECRET=` in `backend/.env`. Do not commit that file or share the secret. The example intentionally has no usable signing secret; authentication returns 503 until a secret of at least 32 bytes is configured. The app reads this file automatically without overriding environment variables.

Initialize the database and create the local demo department and accounts explicitly:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed --demo
```

The seed command prompts privately for a password of 12–128 characters. It creates **Campus Library**, `supervisor@example.com`, and `student@example.com`, using that password for both local demo accounts. It never prints the password, resets existing passwords, or runs at server startup. It requires `--demo` and a SQLite database URL; use it only with a disposable local development database. Repeating it skips existing users without changing their roles or passwords.

To initialize only the department and register your own student in the UI instead:

```powershell
.\.venv\Scripts\python.exe -m app.seed --demo --department-only
```

Public registration always creates students. Supervisor provisioning is deliberately restricted to the explicit developer seed command in this phase. Students choose an existing department at registration; authenticated users cannot change their role or department through the API. Department enrollment approval is future work.

## Run locally

Backend terminal, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal, starting from the repository root:

```powershell
cd frontend
npm ci
# Optional on first setup only:
Copy-Item .env.example .env
npm run dev
```

Open <http://127.0.0.1:5173>. Keep both terminals running. Use `npm.cmd` if PowerShell blocks `npm.ps1`. Calling the virtual environment's Python directly avoids activation policy problems; optional activation is `.\.venv\Scripts\Activate.ps1`.

API docs: <http://127.0.0.1:8000/docs>. `GET /` returns the existing welcome message. `GET /api/health` returns `{"status":"healthy","application":"CampusShift"}`; this is API liveness, not a database readiness check.

## Try the workflows

1. Open **Join CampusShift**, choose Campus Library, and register a student with a unique email and a 12–128 character password. Registration signs you in immediately on success. You can also sign in with a seeded account.
2. Edit your profile and weekly maximum hours. Add, edit, and delete classes and availability windows. Entries recur weekly, use local campus time, and support Monday through Sunday (`0` through `6`). The default hour limit is 20; permitted limits are 0–40. Students can edit their own limit and supervisors can edit department students' limits in this phase.
3. Try overlapping entries of the same type: the API rejects them with 409. Back-to-back windows are allowed. Start must precede end; overnight windows must be split at day boundaries. Time inputs use minute precision.
4. Create availability intersecting a class: both entries remain saved, with a visible conflict warning and calendar highlights. Edit either entry to resolve it.
5. Sign out and log in as `supervisor@example.com` using your chosen seed password. Open the employee directory, view a student's classes and availability, and update their hour limit. Only students in that supervisor's department appear.
6. Refreshing the browser or signing out discards the in-memory token. Sign in again. Tokens default to 30 minutes, with no refresh tokens or persistent browser storage.

For the landing-page connection indicator, stop the backend and click **Check again**, then restart and retry. The landing page remains usable while the backend is offline.

## Configuration

| Variable | Location | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | backend environment | Defaults to `sqlite:///./campusshift.db`, resolved against `backend/`. Migrations, seeding, and the API use the same setting. |
| `JWT_SECRET` | backend environment | Random signing secret, at least 32 bytes. Never use a public or example value. |
| `JWT_EXPIRE_MINUTES` | backend environment | Token lifetime, 1–60 minutes; default 30. |
| `CORS_ORIGINS` | backend environment | Comma-separated browser origins; defaults allow localhost and 127.0.0.1 on port 5173. |
| `API_PROXY_TARGET` | frontend environment | Vite development proxy target; default `http://127.0.0.1:8000`. |
| `VITE_API_BASE_URL` | frontend environment | Optional browser API origin. Empty means same-origin `/api` requests. All `VITE_` values are public. |

Restart processes after changing environment variables. Never put secrets in frontend variables. Vite's proxy applies to development only. For separate hosting, build with the API origin in `VITE_API_BASE_URL` and allow the exact frontend origin in backend CORS. A built SPA host must serve `index.html` for client routes. No hosting is configured here.

## Build, migrations, and tests

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -c "from main import app; print(app.title)"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

Tests use isolated databases and cover authentication, password verification, JWT expiry, roles, department isolation, ownership, profile validation, class/availability CRUD, overlaps, conflicts, CORS, schema migration round trips, and repeatable seeding. They do not seed your development database. See `docs/verification.md` for executed results and limits.

After future model changes, generate and review a migration, then apply it:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "Describe schema change"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

The server never uses `create_all` or seeds data automatically. Back up any useful local data before migrations. Downgrading the initial migration drops application tables and their data.

From `frontend/`:

```powershell
npm run build
npm run lint
npm run preview
```

ESLint checks frontend source for undefined and unused variables and recommended JavaScript issues. Preview runs on port 4173: to connect directly to the local API, build with `VITE_API_BASE_URL=http://127.0.0.1:8000` and add `http://localhost:4173` or `http://127.0.0.1:4173` to backend CORS as appropriate.

## Structure

```text
frontend/src/
  App.jsx             Existing landing page and health indicator
  Router.jsx          Protected student and supervisor routes
  auth/               In-memory session state and expiration
  services/           Central API client, errors and bearer headers
  components/         Sidebar, forms, weekly calendars and shared states
  pages/              Login, registration, student and supervisor views
backend/
  main.py             App factory, CORS, health and safe database errors
  app/api/            Routes and authentication/role dependencies
  app/core/           Environment settings, hashing and JWTs
  app/db/             SQLAlchemy engine and session lifecycle
  app/models/         Department, User, ClassSchedule, Availability
  app/schemas/        Request validation and safe response contracts
  app/services/       Account persistence, ownership, overlap/conflict rules
  app/seed.py         Explicit local demo initialization
  alembic/            Versioned database migrations
  tests/              API, authorization, migration and seed tests
scheduler/            Pure scheduling engine, typed inputs, and independent tests
infrastructure/       Reserved for reproducible infrastructure
scripts/              Shared automation space
docs/                 Architecture and verification notes
```

## Local-development boundaries and AWS constraints

This phase uses bearer access tokens in memory; sign-out clears the client token, and any previously copied token remains valid until expiration. There is no token revocation, refresh flow, password reset, email verification, or deployment hardening such as login rate limiting. This is a local development implementation. All authorization is enforced in the backend even if frontend route protection is bypassed.

AWS Academy Cloud Architecting 3 Sandbox supports the listed Lambda, DynamoDB, S3, CloudFront, EC2, CloudFormation, CloudWatch, and RDS services, subject to sandbox permissions. API Gateway and Cognito are unavailable; IAM is read-only. Resources and data may disappear between sessions, so future infrastructure must be reproducible from code. This phase uses no AWS services and creates no cloud resources. DynamoDB, time-off, supervisor shift editing, shift swaps/publishing, notifications, payroll, and analytics remain out of scope.

Next: Phase 4 supervisor review and formal publication, including how input changes invalidate a draft, before selecting a permitted sandbox deployment design.

## Phase 3 weekly scheduling demo

For an existing Phase 2 checkout, update the environment and apply the additive migration (from the repository root):

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
backend\.venv\Scripts\python.exe -m pip install -e .
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed_scheduling --demo
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

The explicit seed command privately asks for a password for new demo accounts. It creates its own **Scheduling Demo** department, two locations, five students (including zero-hour and inactive examples), location eligibility, availability, class conflicts, and ten staffing requirements totaling 44 employee-hours. It does not modify the original Campus Library department or existing account passwords. Fresh setups use deterministic insertion order and identical weekly inputs; repeating the command avoids duplicates and preserves user edits. Use a fresh disposable local database if you need to reproduce the untouched baseline after editing demo records. The command never runs at startup.

In another terminal from the root:

```powershell
cd frontend
npm ci
npm run dev
```

1. Open <http://127.0.0.1:5173/login> and sign in as `scheduling.supervisor@example.com` with the password you chose.
2. Inspect **Work locations**, including eligible employees and active status. New locations have nobody eligible until selected explicitly. Inactive employees are excluded from generation, but can still log in and inspect previews.
3. Inspect **Staffing needs**. Add, edit, deactivate, or delete recurring requirements. Active requirements at one location must not overlap. Requirements referenced by saved drafts cannot be deleted; deactivate them to preserve history. Deactivated locations suppress their staffing requirements in new generations.
4. Open **Schedule generator**, select Monday **2026-10-19**, and generate. Review employee-minute coverage, assigned hours, amber understaffed periods, explanations, and employee totals. Filter the calendar by location or student. Metrics always describe the whole draft; location gaps remain visible while filtering by employee.
5. Generate again to create another draft version. Earlier versions remain selectable and unchanged. Repeated generations do not add together or consume hours from other versions.
6. Sign out, then sign in as `avery.schedule@example.com`, `jordan.schedule@example.com`, or `sam.schedule@example.com` using the same chosen password. The dashboard and **Draft schedule** page show only that student's assignments from the latest draft. Students cannot edit shifts. Every preview is explicitly draft/unpublished, never a finalized assignment.

All recurring windows are campus-local wall-clock time. Departments default to `America/Chicago`, stored on the department and copied into each draft. The engine uses calendar dates and integer minutes, never converts these windows to UTC, and counts local wall-clock minutes even across daylight saving transitions. `created_at` is a separate UTC audit timestamp. Week start must be Monday. Overnight windows are rejected. Staffing times use :00/:30 boundaries; class and availability entries retain minute precision. A complete 30-minute staffing slot must fit submitted availability without any class conflict. Partial slots remain uncovered; zero-hour students receive no shifts.

The algorithm is deterministic greedy, not globally optimal. It processes chronological 30-minute slots, favors locations with fewer eligible candidates relative to demand, then ranks students by one-hour bands of hours already assigned this week, previous-week assigned minutes, continuity, exact current minutes, and a stable week-rotated ID tie-breaker. Adjacent assignments for the same employee, location, and requirement merge into longer shifts. Previous-week history uses only the newest draft of the latest earlier scheduled week, never drafts from the target week; this history is part of the saved input snapshot. This balances hours and reduces fragmentation without relaxing constraints. See [scheduling design](docs/scheduling.md) for details and limitations.

Run independent engine tests from the root, then backend integration tests:

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s scheduler/tests -v
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic check
```

## Scheduling API

All supervisor endpoints use the authenticated supervisor's department. A client-provided department ID is rejected. All requests use the same short-lived bearer tokens as Phase 2; JSON input examples are available in `/docs`.

| Method | Endpoint | Capability |
| --- | --- | --- |
| GET, POST | `/api/supervisor/locations` | List/create locations and explicit eligible-student IDs |
| GET, PUT | `/api/supervisor/locations/{id}` | Read/update location, description, eligibility, and active status |
| PATCH | `/api/supervisor/employees/{id}/scheduling` | Set `is_active` for scheduling |
| GET, POST | `/api/supervisor/requirements` | List/create recurring staffing demand |
| GET, PUT, DELETE | `/api/supervisor/requirements/{id}` | Read/edit/delete unused requirements; `is_active=false` deactivates |
| GET, POST | `/api/supervisor/schedules` | List runs/create a new version with `{"week_start":"2026-10-19"}` |
| GET | `/api/supervisor/schedules/{id}` | Read saved draft, assignments, gaps, and input snapshot |
| GET | `/api/supervisor/schedules/{id}/unfilled` | Read uncovered time windows, missing counts, and reasons |
| GET | `/api/supervisor/schedules/{id}/coverage` | Read coverage and employee-minute totals |
| GET | `/api/supervisor/schedules/{id}/employee-hours` | Read employee assigned-hour totals |
| GET | `/api/students/me/locations` | View own eligible active department locations |
| GET | `/api/students/me/schedule` | Own shifts in most recently generated draft; optional Monday `week_start` filter |

`duration_minutes` is the stored duration unit. Gaps include explicit start/end times so partial requirements can be identified. Coverage is assigned staff-minutes divided by required staff-minutes; zero demand reports 100% with an explicit no-demand message. The UI's unfilled-position count refers to 30-minute employee slots, not unique employees or whole requirements.
