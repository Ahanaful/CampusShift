# CampusShift

CampusShift is a student employee scheduling application for university departments. Phase 1 establishes a local development foundation: a responsive landing page, placeholders for student and supervisor dashboards, and a working API connection indicator. Authentication, scheduling, storage, and cloud deployment are intentionally future work.

## Stack and prerequisites

- Frontend: React 19, Vite 7, JavaScript, Tailwind CSS 4 (Vite plugin).
- Backend: Python 3, FastAPI, Uvicorn; standard-library unittest with HTTPX for API tests.
- Install Node.js 22.12+ (Node 22 LTS recommended), npm, Python 3.10+, and Git. Commands below use Windows PowerShell from the repository root.

## Local setup

Use two terminals. Neither application needs AWS credentials or a database.

### Backend — terminal 1

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

Using the virtual environment's Python directly avoids PowerShell activation policy issues. Optionally activate it with `.\.venv\Scripts\Activate.ps1`, then use `python` normally. For runtime dependencies alone, install `requirements.txt`; the development file includes HTTPX for tests. Uvicorn loads `.env` with `--env-file`; `main.py` reads environment variables and does not load files during import.

API: <http://127.0.0.1:8000>, interactive docs: <http://127.0.0.1:8000/docs>.

### Frontend — terminal 2

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open <http://localhost:5173>. The port is fixed so it matches the default CORS settings. If PowerShell blocks `npm.ps1`, use `npm.cmd` for these commands. Once a lockfile exists, use `npm ci` for repeatable installs.

### Verify the connection

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

The health response is `{"status":"healthy","application":"CampusShift"}`. The landing page should show **Backend connected**. Stop the backend and click **Check again** to verify the unavailable message; restart it and retry to reconnect. The frontend remains usable with the backend offline.

### Configuration

- `frontend/.env`: `API_PROXY_TARGET` defaults to `http://127.0.0.1:8000` and controls the Vite development proxy. Leave `VITE_API_BASE_URL` empty for relative `/api/health` requests.
- For a separately hosted API, set `VITE_API_BASE_URL` to its origin and rebuild. All `VITE_` variables are public browser configuration: never put secrets there.
- `backend/.env`: `CORS_ORIGINS` is a comma-separated list of allowed browser origins. Defaults allow `http://localhost:5173` and `http://127.0.0.1:5173`. Set the exact frontend origin when hosting separately.
- The Vite proxy only applies to development. A built frontend needs either a host routing `/api` to the backend or a configured `VITE_API_BASE_URL` and matching backend CORS origin. Hosting is not configured in Phase 1.

### Build and tests

From `frontend/`:

```powershell
npm run build
npm run preview
```

`preview` serves the static build on port 4173. To connect that preview directly to the local API, build with `VITE_API_BASE_URL=http://127.0.0.1:8000` in the frontend `.env`, and add `http://localhost:4173` to backend `CORS_ORIGINS`. Restart the backend after configuration changes.

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -c "from main import app; print(app.title)"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover the welcome response, exact health contract, and allowed/disallowed CORS origins.

## Repository structure

```text
frontend/          React landing page, Vite configuration, public assets
  src/             Reusable workspace cards and live API status component
backend/           FastAPI application, dependency files, environment example
  tests/           API and CORS contract tests
scheduler/         Reserved for independently testable scheduling logic
infrastructure/    Reserved for reproducible infrastructure definitions
scripts/           Reserved for shared developer automation
docs/              Architecture notes
```

## AWS Academy constraints

Target environment: AWS Academy Cloud Architecting 3 Sandbox. The supported service list includes Lambda, DynamoDB, S3, CloudFront, EC2, CloudFormation, CloudWatch, and RDS. API Gateway and Cognito are not available; IAM is read-only. Do not assume permission to create roles or deploy a service merely because its name appears on the list.

Resources, including DynamoDB tables, may disappear between sessions. Future infrastructure and initial data setup must be reproducible from code. This phase creates no AWS resources, accesses no AWS services, and needs no credentials. Keep credentials, local `.env` files, virtual environments, dependency folders, logs, and state files out of Git.

## Suggested next phase

Agree on student, department, class, availability, and shift data contracts. Implement and test scheduling constraints as a standalone package, then design persistence and a permitted sandbox deployment architecture before adding authentication or provisioning infrastructure.
