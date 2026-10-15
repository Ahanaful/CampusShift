# Verification

## Phase 2

Executed on Windows with Python 3.12 and portable Node.js 22.22.0:

- Backend import and `python -m unittest discover -s tests -v`: **20 tests passed**. Coverage includes Phase 1 responses/CORS, registration/login, password hashing and incorrect credentials, JWT expiry, missing signing configuration, role permissions, department isolation, ownership restrictions, profile validation, class/availability CRUD, invalid time ranges, overlap rejection, adjacent windows, cross-type conflict reporting without modifying entries, migrations, and repeatable seeding.
- Alembic upgrade, downgrade, reinspection, and model/schema consistency were exercised on an isolated temporary database. `alembic check` also passed for the initialized local database.
- Frontend dependency installation completed; npm reported zero vulnerabilities. `npm run build` passed. There is no configured lint command.
- A live HTTP smoke check through Vite verified landing/login/registration/deep-route responses, the health proxy, student registration/login/current user, class/availability writes, conflict reporting, supervisor login/directory/class inspection/hour updates, student rejection from supervisor endpoints, and entry deletion. Only temporary randomly named test accounts were created for that check, then removed.
- The local database was migrated and the Campus Library demo department initialized. A random signing secret was generated in ignored `backend/.env`. No persistent demo account passwords were selected; use the seed command to choose your own privately.

The original API process needed restarting to load Phase 2. The updated backend and existing Vite server were left running for local use. No cloud resources were created and no changes were committed or pushed for Phase 2.

The Windows sandbox blocked temporary-directory access during one migration test run; the complete suite passed with elevated tool execution. Browser automation was unavailable: actual browser rendering, menu/form interaction, responsive appearance, redirect behavior, and the client session timer were not exercised in a browser. Build and HTTP integration checks do not substitute for those manual checks. Use the README workflow to finish browser QA.

## Phase 1 (historical)

Verified locally on Windows with Python 3.12 and a portable Node.js 22.22.0 runtime:

- Frontend dependency installation completed and generated `frontend/package-lock.json`; npm reported zero vulnerabilities.
- `npm run build` passed with Vite 7.3.7.
- Backend import printed `CampusShift API`.
- `python -m unittest discover -s tests -v` passed all four API/CORS tests.
- A live Vite server returned HTTP 200 for the page and transformed React module.
- A request to `http://127.0.0.1:5173/api/health` passed through Vite to a live Uvicorn backend and returned the exact expected health object.
- `git diff --check` passed (Git emitted only an LF-to-CRLF informational warning).

The verification servers were stopped afterward. No cloud resources were accessed or deployed, and nothing was committed or pushed.

## Environment limitations

Node/npm were absent from PATH, so verification used a portable Node runtime in ignored `.local/`. Regular development requires installing Node or adding a local runtime to PATH. The Windows sandbox blocked Python package setup and esbuild child processes; those steps succeeded with tool execution outside the sandbox.

No browser preview tool was available. Visual rendering, responsive layouts in a browser, and clicking the offline/retry status flow were not verified. Follow the root README's manual connection checks to verify those states.
