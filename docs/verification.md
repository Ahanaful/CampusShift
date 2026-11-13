# Verification

## Stage B serverless preparation — November 13, 2026

Current implementation/runbook: [serverless deployment](aws-serverless-deployment.md).
Nothing is deployed. No account plan, Advanced Features, IAM/SCP policy, existing
AWS resource, Git commit or push was changed. Earlier Stage A and research-only
results below are historical; the helper now defaults to Ohio and accepts the
expected AWS-managed project human role.

- Backend: `cd backend; .venv/Scripts/python.exe -m unittest discover -s tests -q`:
  **158 tests, OK, 6 skipped** (three PostgreSQL-only checks and three inherited
  injected-exception tests whose TestClient re-raise assertions are covered in
  their original tests; Mangum returns an HTTP 500 instead).
- PostgreSQL: `backend/.venv/Scripts/python.exe scripts/test_postgresql.py`:
  **158 tests, OK, 3 skipped**, against disposable local PostgreSQL 16.15. Included
  real Alembic upgrade/check/downgrade/upgrade, repeatable migration and seed jobs,
  DML app-role access/DDL denial, NullPool physical connection closure, concurrent
  writes and the existing phase 2–5 contracts. Backup/restore and overwrite/
  populated-target/approval refusals passed with synthetic counts `6|1|14|2|4`.
  The helper removed its own test container.
- Existing auth, scheduling, workflow and attendance test contracts also ran
  through **real Mangum HTTP API v2 event handling**, including JWT, department
  ownership, CORS, status/body/CSV handling and sanitized unexpected HTTP 500.
- Scheduler: `backend/.venv/Scripts/python.exe -m unittest discover -s scheduler/tests -v`:
  **15 passed**.
- Frontend: ESLint and Vite production build passed with local Node 22.22.0.
  Browser network timeout now allows 35 seconds for Aurora resume; no write retry.
- CloudFormation: `cfn-lint` passed for platform, frontend, serverless and artifact
  templates. AWS **ValidateTemplate in us-east-2** passed for the new backend,
  artifact bucket and reused frontend templates. This creates no resources and
  does not establish create permissions, capacity or end-to-end networking.
- Read-only refresh confirmed intended account ending 7313, ACTIVE FREE/$100,
  Aurora PostgreSQL 16.15/db.serverless orderable in Ohio with min capacity 0,
  Lambda concurrency 10/unreserved 10, and successful Secrets Manager metadata
  listing. Detailed account evidence remains ignored in `.local/serverless/`.
- Linux artifact: built Python 3.12/x86_64 ZIP using a digest-pinned official Lambda
  Docker image, full dependency constraints and Ohio RDS CA. Actual ZIP smoke
  tests use `scripts/verify_lambda_package.py` in a container with **no network**:
  native psycopg/Argon2 imports, cached adapter/warm request, DB-free health,
  private 0600 passfile/0700 directory and escaping, no packaged tests/.env/DBs.
  Final ZIP: **13,364,265 bytes compressed / 42,608,152 bytes unpacked**.
  Final measured local Docker run: cold extraction/import/health **1,698 ms**, warm
  health **1 ms**, 50 students/35 weekly staffing requirements **1,761 ms** with
  100% coverage. These are workstation measurements, not deployed Lambda latency
  or Aurora performance guarantees. Final package metadata is ignored locally.

**Still requires approved deployment:** actual resource creation, execution-role
and service-linked-role permissions, CloudFront/HTTP API browser behavior,
private Aurora TLS access, AWS cold starts, 0-ACU pause/resume timing, concurrent
capacity at 1 ACU/1024 MiB, observed credit use, and a reviewed snapshot restore
drill. Follow the explicit cloud checklist in the current runbook. No such cloud
integration tests, load test or billing alarm creation has run.

## Project-based Free Plan correction - November 13, 2026

The user confirmed the assigned home region is **Ohio/us-east-2**. AWS's primary project documentation shows that AWS manages the organization, SCPs and human-access role; generic account setup/scoped Console-IAM instructions were inappropriate for this project. The managed region policy explains the earlier us-east-1 denial pattern. No policy change or Advanced Features activation is necessary to use the supported regional APIs in Ohio.

Read-only Ohio rechecks succeeded for all previously denied EC2 DescribeVpcs/Subnets/RouteTables/InternetGateways/KeyPairs/InstanceTypes/InstanceTypeOfferings/SecurityGroups/ManagedPrefixLists operations, both RDS instance/orderable-options reads, SSM public AMI GetParameter/DescribeParameters metadata, CloudFormation ListStacks and **both live ValidateTemplate calls**. Lambda ListFunctions and HTTP API listing also succeeded. Existing default VPC/three public subnets were found; no networking was created or modified.

Additional regional reads advertised **Aurora PostgreSQL 16.15/db.serverless** as orderable with minimum capacity **0 ACU**. The official Ohio price catalog reports Aurora Standard Serverless v2 **$0.12/ACU-hour**, Aurora storage **$0.10/GiB-month**, PostgreSQL db.t3.micro **$0.018/hour** and gp3 storage **$0.115/GiB-month**. This establishes advertised regional options/prices, not a deployed cluster, proven pause/resume behavior or a measured workload cost.

The research task changed only local documentation/cost-status metadata. No IAM/SCP policies, account plan, Advanced Features, CLI profile settings, resource creation, stacks/change sets, runtime deployment, commits or pushes occurred. No application code changed and no new application regression run was claimed. Private full evidence is ignored in `.local/aws-project-home-region.json`. See [the corrected decision](aws-project-free-plan-decision.md); previous Stage A findings remain historical observations with a superseded diagnosis.

## AWS Free Plan Stage A — November 13, 2026

Actual Windows/read-only AWS results for the dedicated campusshift profile in **us-east-1**:

- CLI **2.40.2** confirmed. Non-secret region/output preferences created; user completed browser login. The requested `aws sts get-caller-identity --profile campusshift` succeeded. User confirmed the account ending 7313 is the intended new account. No credential/key/token values were printed; configure-list credential rows were redacted in the helper.
- Free Tier API confirmed **FREE / ACTIVE / USD 100 remaining**, expiring May 12, 2027 at 7:36 p.m. America/Chicago (May 13 00:36 UTC).
- Current identity is an existing **AccountFullAccessRole** with **AdministratorAccess** attached and no permission boundary. Read-only IAM inspection confirmed this; no role/user/policy was created or changed by the assistant. The tool now refuses provisioning with this known broad identity, pending a reviewed scoped replacement.
- S3 list, CloudFront distribution/VPC-origin list, CloudWatch log-group list, IAM profile list, budget/credit and quota reads succeeded. S3 returned zero buckets, VPC origins zero items and account budget listing zero budgets. Standard EC2 quota is **5 vCPUs**; quota-read success is not launch authorization.
- EC2/network/AMI, RDS instance/orderable-options, SSM and CloudFormation reads were **explicitly denied by an organization SCP**. Both live CloudFormation ValidateTemplate requests were attempted and denied by that SCP. DescribeOrganization confirmed member-account status; reading the governing policy document was denied, so its full conditions/intent are unknown. No denial is attributed solely to the Free Plan; extra IAM allows cannot override it. No alternate-region probes or policy modifications were attempted.
- Three local CloudFormation templates (platform/frontend/optional IAM log role) passed **cfn-lint 1.60.1**. Backend discovery ran **88 tests: 86 passed, 2 PostgreSQL-only tests skipped**. Nine new mocked AWS-tool tests cover explicit profile/environment isolation, redaction, missing login, root/wrong-account rejection, FREE/credit guards, read-only preflight, SCP reporting and broad-role execution refusal. No cloud API is called by these tests.
- Official public us-east-1 pricing reads confirmed EC2 t3.micro **$0.0104/hour** and RDS PostgreSQL db.t3.micro Single-AZ **$0.018/hour**, gp3 **$0.115/GiB-month**; RDS catalog published November 12. IPv4 **$0.005/hour** comes from AWS pricing; EBS **$0.08/GiB-month** remains an explicit planning rate to recheck in Calculator. Proposed public-origin footprint is **$27.64/month baseline**, **$30–35/month planning envelope**, not a workload-tested cap or a live deployment.
- Git whitespace checks passed. No application business logic or frontend was changed for this Stage A adaptation; prior Phase 6 build/PostgreSQL evidence below remains historical, not a new claim of deployed verification.

Private full account/organization identifiers and raw preflight evidence are kept only in ignored `.local/` logs. No application resources, IAM entities, budget/alert resources, plan upgrades, organization membership/policy changes, CDK/bootstrap, destructive operations, commits or pushes were performed. Stage A audit is finished with blocking findings: authorized organization policy review, scoped identity and final HTTPS/Stage B resource approval remain. See [Stage A next steps](aws-stage-a.md) and [IAM/profile setup](aws-profile-setup.md).

## Phase 6 preparation

Executed locally on Windows with Python 3.12, Node 22.22.0 and disposable Linux Docker containers:

- **SQLite regression run: 79 tests discovered, 77 passed and 2 PostgreSQL-only tests skipped.** Existing authentication, department/ownership controls, scheduling, publication, leave and attendance remained intact. New checks cover production fail-closed configuration, structured log redaction and database readiness. Test fixtures are isolated and do not alter the developer database.
- **PostgreSQL regression run: all 79 tests passed** with PostgreSQL **16.15**. Shared API fixtures run in unique disposable PostgreSQL schemas; independent legacy SQLite migration tests continue to exercise SQLite. The full actual Alembic chain upgraded/downgraded/re-upgraded on PostgreSQL, `alembic check` reported no model changes, and synthetic cloud-demo setup preserved a published run/attendance across new connections and repeated seeding. Partial index predicates/uniqueness, concurrent overlapping availability (201/409), concurrent clock-ins (201/409) and stale draft edits (200/409) were verified.
- **15 independent scheduler tests passed.** No scheduling algorithm rewrite was required.
- The real `database_backup.sh` created a synthetic custom-format dump and restored it to a new empty local PostgreSQL database. User/run/shift/attendance/audit counts matched: **6 / 1 / 14 / 2 / 4**. Existing-backup overwrite, populated-target restore and restore-without-approval were rejected. No AWS/real employee data was used.
- **Both CloudFormation templates passed cfn-lint 1.60.1** with no findings. This is local schema/lint validation, not AWS `validate-template` or proof of service permissions. Six direct CloudFront function checks preserved `/api` paths and assets while rewriting SPA routes.
- **Frontend ESLint and Vite production build passed.** No frontend business logic changes were needed; deployment uses a blank VITE_API_BASE_URL for same-origin API requests.
- Linux deployment/backup scripts passed Git Bash syntax checks. Nginx configuration passed `nginx -t` in a disposable nginx:stable-alpine container, using a temporary self-signed test fixture and no published ports. This syntax test does **not** validate real origin TLS; deployment still requires a publicly trusted certificate. Python compilation and allowlisted source packaging passed. Private configuration/databases/dependencies are excluded from the archive.
- The local PostgreSQL test container was removed after each run; Docker images remain available locally. Git diff whitespace checks passed. No AWS resources, remote server changes, commits, pushes or external messages were created.

The local PostgreSQL image ID was `sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d`. `scripts/test_postgresql.py --image IMAGE_OR_DIGEST` supports exact local image selection. This does not establish compatibility with every RDS PostgreSQL version; inspect permitted versions and run deployed acceptance against the chosen one.

AWS CLI discovery exited with a clear **CLI unavailable** message. No active AWS identity, temporary credentials, creation/pass-role permissions, live CloudFormation validation or resources were verified. A complete read-only discovery tool and commands are provided. A matching trusted API origin certificate/domain, authorized existing networking, approved SSM SecureString/decrypt path, explicit billable-resource approval and actual deployed HTTPS/role/workflow checks remain prerequisites. CloudWatch delivery, Amazon Linux bootstrap/systemd startup, SELinux integration, live RDS TLS, reboot recovery, full cloud recreation, certificate renewal, browser interaction and cloud backup restoration have **not** been executed here. The old README's manual EC2 deployment is recorded history and was not inspected or modified.

Initial local verification exposed SQLite-only database-copy assumptions in concurrency test helpers and an overly specific index-count assertion. The helpers now exercise pooled PostgreSQL directly or an isolated SQLite file, with explicit connection cleanup on Windows; the corrected complete runs passed. Deployment is prepared, not declared complete. See [AWS deployment](aws-deployment.md), [feasibility](aws-architecture.md) and [recovery](sandbox-recovery.md).

## Phase 5

Executed locally on Windows using Python 3.12 and Node.js 22.22.0:

- Applied additive attendance migration `9e57ab896061`; `alembic check` passed. Existing Phase 1–4 workflows and migration-preservation tests remain passing.
- **74 backend tests passed**. New checks include server-generated clock timestamps, published-shift ownership, early/late eligibility, duplicate/active constraints, clock-out authorization, private history, correction approval/rejection/staleness, overlap prevention at request and approval, audit/record rollback, archived-shift attendance retention, department-scoped reports/CSV, spreadsheet formula escaping, UTC storage, real concurrent clock-ins, midnight/weekly boundary clipping, early clock-in on a preceding local date, and daylight-saving fold/gap behavior.
- A fall-back shift recorded three actual elapsed hours versus two scheduled wall-clock hours. A spring-forward interval resolved to one elapsed hour versus two wall-clock hours. Correction inputs can select the second repeated local hour; nonexistent spring times are rejected.
- **15 independent scheduler tests passed** unchanged.
- Frontend lint and production build passed with the attendance pages, CSV client support, department-local timezone abbreviations, and polling that preserves correction input options.
- A live HTTP scenario through Vite created a temporary department, generated and published a currently eligible shift, clocked in/out using the real server clock, rejected a duplicate clock-in, showed supervisor active attendance, approved a correction, inspected original-value audit history, exported CSV as supervisor and rejected student export. Attendance SPA routes returned 200. Only isolated test data was removed afterward; existing application records were preserved.
- Backend import reported CampusShift API 0.5.0. Database, `.env`, dependency folders and portable tooling remain ignored by Git. No cloud resources, commits or pushes were created.

The local API and Vite server were left running. Browser automation was unavailable, so clicking the forms/buttons/export download and checking responsive appearance remain manual QA tasks. Reports are currently unpaginated, active totals are 30-second server snapshots, and correction proposals have a documented 24-hour limit. No GPS, biometrics, payroll/wage calculations or email/SMS were introduced.

## Phase 4

Executed locally on Windows with Python 3.12 and Node.js 22.22.0:

- Applied `fab90f5980a1` to the local SQLite database. `alembic check` passed. Migration tests preserved original Phase 2 users and Phase 3 schedule/assignment data, verified FK integrity, and exercised a Phase 3→4→3→4 round trip without data loss for drafts.
- **48 backend tests passed**, including Phase 1–3 regressions and new leave lifecycle, filtering, UTC audit timestamps, cancellation, ownership/department/role isolation, approved-only generation constraints, late-approval warnings, manual edit validation, capacity, hours, class/availability/eligibility/leave conflicts, double booking, stale revision rejection, rollback, publication acknowledgements, official student visibility, archival history and unique current publication tests.
- A real two-thread file-backed SQLite edit test accepted one edit and rejected the stale edit with 409. A direct duplicate-publication database update failed the partial unique index. Simulated persistence/audit failures preserved the original draft or published version.
- **15 independent scheduler tests passed**, including inclusive approved-leave date boundaries and invalid approved date ranges, with the original availability/hour/fairness/eligibility tests intact.
- `npm run lint` and `npm run build` passed for the final frontend source.
- Live HTTP checks through Vite passed leave submission/approval, existing-assignment warnings, reassignment/removal/refill, rejection of unacknowledged gaps, publication, current official student visibility, explicit replacement publication/archive, and audit retrieval. Late approval over the replacement's shifts produced supervisor warnings while student published hours remained unchanged. New SPA routes returned 200. Temporary smoke accounts and their isolated department/data were removed; existing application records were preserved.

The API and Vite server were started and left running on ports 8000 and 5173. No AWS resources, commits, pushes, or external messages were created.

Limitations: browser rendering, clicking forms/menus/filters, publication checkbox interactions, and responsive appearance were not exercised in a browser because browser automation was unavailable. Supervisor warnings update on decision/navigation or explicit refresh, not push delivery. Final leave decisions cannot be reversed in this phase. Existing published assignments are preserved when later leave is approved, so supervisors must explicitly publish a reviewed replacement. Scheduler granularity, heuristic optimality and local wall-clock/DST assumptions remain as documented.

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
