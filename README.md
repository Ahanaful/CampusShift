# CampusShift

CampusShift helps university departments coordinate student employees, class commitments, and work availability. Phase 2 adds local accounts, student profiles, class and availability management, and a department-scoped supervisor workspace. The Phase 1 landing page and health endpoint remain available.

## Technology and prerequisites

- React 19, Vite 7, JavaScript, Tailwind CSS 4, React Router 7.
- Python 3.10+, FastAPI, Uvicorn, SQLAlchemy 2, SQLite, and Alembic.
- Argon2id password hashes and signed, short-lived JWT bearer tokens.
- Node.js 22.12+ and npm; Git; Windows PowerShell examples below.

No AWS credentials or services are required. Run commands from the repository root unless a different directory is shown.

## Backend setup and database initialization

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
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
npm run preview
```

There is no lint script configured. Preview runs on port 4173: to connect directly to the local API, build with `VITE_API_BASE_URL=http://127.0.0.1:8000` and add `http://localhost:4173` or `http://127.0.0.1:4173` to backend CORS as appropriate.

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
scheduler/            Reserved for independently tested scheduling logic
infrastructure/       Reserved for reproducible infrastructure
scripts/              Shared automation space
docs/                 Architecture and verification notes
```

## Local-development boundaries and AWS constraints

This phase uses bearer access tokens in memory; sign-out clears the client token, and any previously copied token remains valid until expiration. There is no token revocation, refresh flow, password reset, email verification, or deployment hardening such as login rate limiting. This is a local development implementation. All authorization is enforced in the backend even if frontend route protection is bypassed.

AWS Academy Cloud Architecting 3 Sandbox supports the listed Lambda, DynamoDB, S3, CloudFront, EC2, CloudFormation, CloudWatch, and RDS services, subject to sandbox permissions. API Gateway and Cognito are unavailable; IAM is read-only. Resources and data may disappear between sessions, so future infrastructure must be reproducible from code. This phase uses no AWS services and creates no cloud resources. DynamoDB, automatic scheduling, time-off, shift publishing, notifications, payroll, and analytics remain out of scope.

Next: define scheduling inputs and staffing requirements, implement an independently tested scheduling engine respecting classes, availability, and hour limits, and later select a permitted sandbox deployment design.
