# CampusShift

**Deployment: the existing EC2 application in Ohio (`us-east-2`).** CampusShift runs at http://3.133.115.154 on `CampusShift-Server` (`t3.micro`, 20 GiB gp3). The frontend and `/api/health` return HTTP 200. The abandoned serverless attempt has been torn down; its Lambda-only code, dependency, commands and templates were removed. Use profile **campusshift** and the existing AWS-managed login. See [current status and cleanup evidence](docs/aws-current-deployment.md) and [EC2 operations](docs/aws-deployment.md).

CampusShift helps university departments coordinate student employees, class commitments, and work availability. Phase 5 adds published-shift clock-in/out, actual attendance hours, supervisor monitoring, audited correction approvals, and CSV export. Scheduling, time off, editing, publishing, authentication, profiles and the landing page remain available.

**EC2 support includes:** source-only release packaging, PostgreSQL compatibility, connection/transaction safety, production configuration validation, readiness checks, structured logging and backup/recovery tools. Local development still defaults to SQLite. Prepared Amazon Linux/RDS and S3/CloudFront templates are optional references, not the existing host's configuration. SNS delivery remains unimplemented.

**Cost review:** approximately **$12.84/month** for the existing EC2 compute, 20 GiB gp3 and public IPv4 at 730 running hours, before credits, taxes, traffic, backups and surplus CPU-credit charges. The three unused attempt secrets are marked for deletion and are not charged. Lambda plus regular RDS modeled at $17.16/month with more deployment work, so EC2 remains selected. Check AWS Settings > Billing for actual credits/spend.

The [project-region investigation](docs/aws-project-free-plan-decision.md) explains the original access correction. [Stage A](docs/aws-stage-a.md), [EC2 deployment](docs/aws-deployment.md), [troubleshooting](docs/aws-troubleshooting.md) and [recovery](docs/sandbox-recovery.md) preserve prior investigation/fallback context; use the current EC2 runbook above for this deployment.

## Technology and prerequisites

- React 19, Vite 7, JavaScript, Tailwind CSS 4, React Router 7.
- Python 3.10+ locally (3.11 on the new Amazon Linux server), FastAPI, Uvicorn, SQLAlchemy 2, SQLite/PostgreSQL with psycopg, and Alembic.
- Argon2id password hashes and signed, short-lived JWT bearer tokens.
- Node.js 22.13+ and npm (22.22.0 used for verification); Git; Windows PowerShell examples below.

No AWS credentials or services are required for local development. Run commands from the repository root unless a different directory is shown.

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

Restart processes after changing environment variables. Never put secrets in frontend variables. Vite's proxy applies to development only. For separate hosting, build with the API origin in `VITE_API_BASE_URL` and allow the exact frontend origin in backend CORS. A built SPA host must serve `index.html` for client routes. The manually configured AWS deployment is documented below. New Phase 6 templates/runtime configuration are tracked under `infrastructure/`; they are a separate proposed deployment, not copies of the legacy server files.

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
infrastructure/       CloudFormation, runtime TLS/systemd/logging configuration
scripts/              AWS discovery/deployment, packaging, verification and backup tools
docs/                 Architecture and verification notes
```

## Local-development boundaries and AWS constraints

This phase uses bearer access tokens in memory; sign-out clears the client token, and any previously copied token remains valid until expiration. There is no token revocation, refresh flow, password reset, email verification, or deployment hardening such as login rate limiting. The current EC2 deployment is verified; see the deployment status linked above. Production hardening remains pending. All authorization is enforced in the backend even if frontend route protection is bypassed.

The project uses the active AWS Free Plan and AWS-managed project login. Preserve managed policies and the plan. All Regional resources belong in Ohio (`us-east-2`); the earlier SCP denials came from using the wrong Region. Credits and time limits can close project access. DynamoDB migration, SNS/email delivery, shift swaps, payroll and advanced analytics remain separate work.

## Phase 6: PostgreSQL and reproducible AWS deployment

The existing EC2 application is the selected deployment. Lambda/Aurora and Lambda/RDS were abandoned and their attempt resources removed. Current host facts, costs and cleanup are recorded in [current deployment](docs/aws-current-deployment.md); future changes follow [EC2 operations](docs/aws-deployment.md). No CDK bootstrap is required.

The repository supports PostgreSQL and production validation, but the current host's database/configuration have not been inspected. `/api/health` is liveness; repository `/api/ready` additionally checks migration readiness. Prepared Amazon Linux TLS/systemd scripts must not be run on the existing Ubuntu host as an in-place updater. See the runbook for source packaging and data-preserving update prerequisites. Local-only seed commands remain explicit; never seed a populated cloud database automatically.

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
6. Sign out, then sign in as `avery.schedule@example.com`, `jordan.schedule@example.com`, or `sam.schedule@example.com` using the same chosen password. **My schedule** and the dashboard show only published assignments. The separate **testing draft preview (unpublished)** link preserves Phase 3 previews without representing them as official work. Students cannot edit shifts.

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
| GET | `/api/students/me/schedule` | Own current published shifts; optional Monday `week_start` filter; empty defaults to newest published week |
| GET | `/api/students/me/draft-schedule` | Explicit unpublished testing preview; optional Monday `week_start` filter |

`duration_minutes` is the stored duration unit. Gaps include explicit start/end times so partial requirements can be identified. Coverage is assigned staff-minutes divided by required staff-minutes; zero demand reports 100% with an explicit no-demand message. The UI's unfilled-position count refers to 30-minute employee slots, not unique employees or whole requirements.

## Phase 4: leave, manual review and publication

The local SQLite migration preserves existing Phase 3 drafts and assignments, adds leave/audit tables, permits draft/published/archived statuses, adds optimistic revision numbers and publishing audit fields, and enforces one current published run per department/week with a partial unique index. Keep useful local database backups before applying migrations. Downgrade is deliberately refused if published/archived history exists; migration rollback must not silently turn official assignments back into drafts.

Upgrade an existing checkout and start the backend from the repository root:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
backend\.venv\Scripts\python.exe -m pip install -e .
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a separate terminal from the root:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Use the existing accounts or initialize the deterministic scheduling demo from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.seed_scheduling --demo
```

The seed prompts for passwords and never runs automatically. Existing `.env` and account passwords remain unchanged.

Demonstration workflow:

1. As `avery.schedule@example.com`, open **My time off** and submit November 16, 2026 through November 16, 2026, optionally giving a reason. A request starts pending. Pending requests can be cancelled by their owner; approved/rejected/cancelled records remain in history.
2. As `scheduling.supervisor@example.com`, open **Time-off management**. Filter by status or overlapping date range, approve or reject a pending request, and optionally add a note. Reviewer and UTC decision timestamps are recorded. Decisions are final in this phase; students cannot approve requests.
3. In **Schedule generator**, generate Monday `2026-11-16`. Approved all-day leave blocks every included local date; pending/rejected/cancelled requests do not. Existing availability, classes, eligibility, hour caps and double-booking rules remain enforced.
4. Review the draft. Reassign a saved shift, remove an assignment, or fill all/part of an uncovered period in 30-minute intervals. The backend immediately validates current student inputs and updates coverage, gaps, hours, revision and audit history atomically. Invalid edits leave the draft unchanged. If another supervisor edited the version, refresh before retrying.
5. Review validation warnings. Publishing rechecks all assignments against current leave and other constraints. Changed staffing demand requires generating a new draft. If coverage is incomplete, explicitly acknowledge uncovered employee-hours, then check the review confirmation and publish.
6. Sign in as a student and open **My schedule**: only that student's assignments in the current published version appear. Select the Monday to view a particular week. Without a filter, the newest published week is shown. Draft testing previews remain separate.
7. Generate and publish a replacement for the same week. The prior published version and all assignments are archived atomically and remain visible in supervisor version history. Published and archived schedules are read-only.
8. To test late leave approval, approve a request covering an existing assigned date. Supervisor dashboard/time-off/schedule pages show conflict warnings on load or refresh. Existing assignments and published status remain unchanged. Fix a draft directly, or generate, review and publish a replacement for an official schedule. There are no email or push notifications in this phase.

Scheduling uses department-local calendar dates (`America/Chicago` by default); leave dates include both endpoints. Audit timestamps are UTC and serialized with timezone information. Editing/publishing use the same pure `assignment_error` hard-constraint function as generation. Coverage is recalculated from fixed saved demand without running a second scheduling algorithm. Staffing changes require a fresh generation; current student constraints are always rechecked. See [Phase 4 design and endpoints](docs/workflows.md).

Run verification:

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s scheduler/tests -v
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic check
cd ../frontend
npm run lint
npm run build
```

## Phase 5: time and attendance

Upgrade the existing local environment from the repository root (the migration preserves existing schedule and leave data):

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
backend\.venv\Scripts\python.exe -m pip install -e .
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a separate terminal from the root:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Existing `.env` files and passwords are preserved. `backend/.env.example` adds optional attendance policy settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| `CLOCK_IN_EARLY_MINUTES` | 15 | How early a student can clock in before scheduled start |
| `CLOCK_IN_LATE_MINUTES` | 30 | How late a student can clock in after scheduled start |
| `ATTENDANCE_LATE_GRACE_MINUTES` | 5 | Grace before a recorded clock-in is flagged late |

Values must be 0–240 minutes. Restart the API after changing settings. The clock-in window includes its opening boundary and its late boundary, but always closes before shift end. A missing clock-in after the window closes must use the correction process. No endpoint accepts a student-supplied actual clock timestamp.

Demonstrate attendance:

1. Use existing accounts, or initialize the scheduling demo with `.\.venv\Scripts\python.exe -m app.seed_scheduling --demo` from `backend/` and privately choose passwords.
2. As supervisor, create or use a staffing window around the current department-local time, ensure the student is eligible and available, generate the current Monday week, and publish it. The seed's daytime windows are not automatically eligible for clock-in at night; choose an appropriate upcoming shift and clock in when its window opens. Same-day scheduling's existing 23:30 latest end boundary still applies.
3. As that student, open **My attendance**. Review the next shift and today's shifts, then **Clock in**. Only that student's current published shift is eligible. Duplicate attempts or a second simultaneous clock-in are rejected. The API uses its own current UTC time.
4. Open the supervisor's **Attendance management** view. The active employee list refreshes every 30 seconds and on manual refresh. Filter record history by student, scheduled local shift date or status; compare planned wall-clock hours with actual elapsed hours, and inspect late/missed indicators. Active records stay visible regardless of date/status filters.
5. As student, **Clock out**. Clock-out remains possible if the schedule has since been replaced, and may occur after midnight. Actual weekly hours are clipped to the department-local Monday–Sunday week, including active elapsed time. They are separate from planned schedule hours and do not truncate real work to scheduler hour caps.
6. Submit a correction for missed or incorrect times. Select the original shift, enter proposed times in the displayed department timezone, choose first/second occurrence only if using a repeated DST hour, and explain the correction. Missing clock-in/out requests require the scheduled shift to have ended. Proposals must be in the past, positive, at most 24 elapsed hours, and start on the original local shift date (or preceding night if work continues past scheduled start). Midnight-crossing clock-out is supported.
7. As supervisor, approve or reject the request in the correction queue. Approval revalidates overlaps and record revision, changes the working attendance values atomically, and retains before/after timestamps, supervisor identity and decision time in the audit history. A stale proposal must be rejected and resubmitted. Missing-clock-in requests use a zero-hour `missing` placeholder until approved; pending/rejected proposals never count as worked time.
8. Export the filtered attendance records as CSV. Export uses authenticated department scope; students cannot access it. The file uses UTC clock timestamps and includes the department timezone, scheduled/actual hours, original shift IDs, and schedule status. Spreadsheet formula prefixes in names are neutralized.

Attendance remains linked to its original assigned shift when another schedule version is published; history is not moved or deleted. All new persisted timestamps use canonical ISO UTC strings with an explicit `Z` and deserialize as aware UTC datetimes. The frontend displays department-local times with timezone abbreviations (for example CST/CDT). DST gaps are rejected; ambiguous scheduled times use the first occurrence, while correction forms support an explicit second occurrence. Actual hours use UTC elapsed duration, so a DST-transition shift can differ from planned wall-clock duration.

See [attendance design and API endpoints](docs/attendance.md). Run the complete verification commands in the previous section; attendance tests are included in backend discovery. Phase 5 adds no AWS service integrations, DynamoDB, GPS, biometrics, payroll/wage calculations, or email/SMS delivery. The application is hosted manually on EC2 as described below.


## Legacy manual AWS EC2 deployment update

Historical reference only: these are prior-account deployment notes, not evidence of infrastructure in the new Free Plan account. Do not reuse the old IP, role, region or instance as the new target. The current project uses campusshift/us-east-2; see the current deployment status above.

CampusShift has been deployed manually from GitHub to an AWS EC2 instance using SSH from a Mac terminal. The following details describe the confirmed server setup; HTTPS and full deployed application testing remain pending.

| Item | Deployment details |
| --- | --- |
| Public URL | <http://3.133.115.154> |
| AWS Region | `us-east-2` (Ohio) |
| Instance type | `t3.micro` |
| Operating system | Ubuntu 26.04.1 LTS (64-bit x86_64), as reported for the deployed server |
| Project directory | `/home/ubuntu/CampusShift` |
| Backend directory | `/home/ubuntu/CampusShift/backend` |
| Frontend source directory | `/home/ubuntu/CampusShift/frontend` |
| Frontend deployment directory | `/var/www/campusshift` |
| Backend service | `campusshift.service` |
| systemd configuration | `/etc/systemd/system/campusshift.service` |
| Nginx configuration | `/etc/nginx/sites-available/campusshift` |
| Database | SQLite, initialized using Alembic migrations |
| HTTPS | Not configured |

Nginx serves the built React frontend and proxies `/api/` requests to FastAPI on `127.0.0.1:8000`. FastAPI runs through systemd, and its service is configured to start automatically when EC2 boots. SQLite stores application data on the instance; DynamoDB is not used.

This legacy deployment is manual. There is no GitHub Actions deployment workflow, and copies of this Ubuntu server's Nginx/systemd files are not included. The new Phase 6 Amazon Linux templates/runtime files are tracked separately and have not been applied to this server. The public IP may change after stopping and starting the EC2 instance.

### Server status checks

Run these commands in the SSH session on EC2:

```bash
sudo systemctl status campusshift.service
sudo systemctl status nginx
sudo journalctl -u campusshift.service -n 100 --no-pager
curl http://127.0.0.1:8000/api/health
```

The API health endpoint checks liveness only; it does not verify database readiness or the full application workflow.

### Initial data and remaining verification

Database migrations have been run. Creation of the demo department and supervisor account is **not confirmed**, and the demo-data seeding script has not been run or verified as part of this deployment update. Migrations alone do not create these records. See the backend setup section for the explicit demo seed commands; public registration creates student accounts only.

Before treating the deployment as production-ready:

- Configure HTTPS before using real account credentials.
- Confirm the initial department and supervisor provisioning, then verify registration and login.
- Test student profiles, classes, availability, staffing locations and requirements, schedule generation/editing/publication, time off, attendance corrections, and CSV export through the public website.
- Verify frontend page refreshes and direct links, API proxying, and service recovery after an EC2 reboot.
- Configure and verify SQLite backups and restoration.
- Add reproducible deployment configuration and document the manual update procedure.

Do not commit server secrets, SSH private keys, or the SQLite database to Git.
