# Verification

## Phase 3

Executed on Windows using Python 3.12 and Node.js 22.22.0:

- Applied the additive `509aa75b1592` migration to the local database; `alembic check` found no pending model changes. A separate preservation test upgraded a database containing Phase 2 users and confirmed the original data and new safe defaults survived.
- Backend suite: **29 tests passed**, including all 20 Phase 1/2 tests. New coverage includes location eligibility, active state, staffing CRUD/overlap validation, supervisor permissions, department isolation, full-week constraint verification, preserved draft versions, snapshot stability after configuration changes, transactional rollback on failure, private student previews, additive migration preservation, and repeatable scheduling demo seeding.
- Independent scheduler suite: **13 tests passed** for valid assignments, missing/partial availability, class boundaries, multiple locations without double booking, caps/zero hours, no eligible students, fairness, reduced fragmentation, stable input ordering, week rotation/history, inactive/cross-department inputs and invalid requirements.
- Frontend build and ESLint checks passed. ESLint was added in Phase 3; the supported ESLint 10 tooling requires Node 22.13+ on the Node 22 release line.
- Live HTTP smoke check via the existing Vite proxy passed registration/login, class/availability setup, location/eligibility creation, staffing creation, draft generation, version preservation, detail/coverage/hour/gap retrieval, supervisor-only authorization, and own-shift student preview. A three-hour requirement with a one-hour class conflict yielded two assigned hours, one uncovered hour and 66.67% coverage. Deep SPA routes returned successfully. Temporary accounts, schedules, and their isolated test department were removed afterward; existing user data was preserved.
- The deterministic five-student, two-location demo was seeded twice in an isolated test database without duplicates. Its 44 employee-hours of weekly demand generated both assignments and gaps.

The current local API was restarted to load Phase 3. The backend and Vite server were left running. No persistent scheduling-demo passwords were chosen automatically: run the documented seed command to choose your own privately. No cloud resources were accessed and no changes were committed or pushed.

Limitations: browser automation remains unavailable, so actual UI interaction, responsive appearance, filters/menus, and client session expiration were not exercised in a browser. Greedy scheduling is not guaranteed globally optimal. Local wall-clock durations intentionally do not adjust for DST elapsed-time differences. Historical drafts remain snapshots when current employee inputs change. Earlier checks found and fixed a SQLite downgrade issue and inconsistent creation-time timezone formatting; the complete suites then passed.

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
