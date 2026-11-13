# Phase 6C/6D: existing EC2 verification report

Executed November 13, 2026 (America/Chicago); public probes began at 4:20 p.m.
Scope: existing deployment only. No resources created, migrations run on EC2,
accounts seeded on EC2, live records changed, dependency upgrades applied,
services restarted, commits made or pushes performed. See the
[current operations runbook](aws-deployment.md).

## Deployment status and evidence boundaries

**The public application is reachable; full integration and production readiness
are not established.** HTTP frontend delivery, API liveness and selected
unauthenticated authorization checks passed. HTTPS failed to connect, and the
readiness endpoint present in this checkout returned 404 on the deployment.

Operator-reported target: account `548280227313`, Ohio `us-east-2`, instance
`i-0b662a28fc2d1aeaf` / `CampusShift-Server`, `t3.micro`, Ubuntu 26.04.1 LTS,
20 GiB gp3, Nginx + systemd/Uvicorn/FastAPI + SQLite. Public HTTP responses identify
`nginx/1.28.3 (Ubuntu)` but do not prove the OS release, instance ownership,
storage, process management, listener binding or database configuration.

`aws configure list-profiles` returned no profiles. Default STS lookup reported
`NoCredentials`; explicit `campusshift` lookup reported profile not found. Both
used `us-east-2`. No EC2/SG/EBS/account-plan claims were independently verified.
`ssh-add -l`, retried outside the sandbox, reported no identities; no private key
was available in the standard SSH directory. No SSH session was attempted and no
server inspection claimed. Do not infer permissions from historical Stage A/B
observations made on a different workstation/session.

Local repository inspection started with clean `main`, commit
`a015db9a915e1e8bcdee26abb0e2ca5ba64a837a` (Prepare AWS serverless deployment
infrastructure), remote `https://github.com/Ahanaful/CampusShift.git`. The GitHub
REST read of `commits/main` returned the same full SHA. No pull/fetch/merge was
performed. **The deployed SHA is unknown.** `/api/ready` returning 404 may reflect
older code or routing differences; it is not proof of a particular revision.
No repository `AGENTS.md` was found.

## Executed public integration checks

Requests used curl with 10-second connection and 20-second total timeouts.
Sandbox network failure was retried with approved external network access before
recording results. No credentials, valid tokens or real user data were sent.

| Feature / request | Expected | Actual | Result |
| --- | --- | --- | --- |
| `GET /api/health` | 200, healthy application JSON | 200, `{"status":"healthy","application":"CampusShift"}` | PASS: liveness |
| `GET /` | 200 HTML | 200 `text/html` | PASS: delivery only |
| `GET /student/attendance` | 200 SPA HTML for direct route | 200 `text/html` | PASS: SPA fallback only |
| `GET /api/ready` | 200 ready JSON for this checkout with migrated DB | 404 JSON `Not Found` | FAIL: readiness route unavailable |
| `GET /api/students/me/attendance`, no token | 401 | 401, `Please sign in again.`, Bearer challenge | PASS |
| `GET /api/supervisor/employees`, no token | 401 | 401 with Bearer challenge | PASS |
| `GET /api/auth/me`, deliberately invalid bearer | 401 | 401 with Bearer challenge | PASS |
| `GET /api/not-a-route` | API 404, not SPA HTML | 404 JSON | PASS |
| `HEAD https://3.133.115.154/` | Trusted HTTPS connection and response | curl exit 7, port 443 connection failed | FAIL: HTTPS unavailable from this client |
| `GET http://3.133.115.154:8000/api/health` | No direct public backend connection | curl exit 28 after 10-second connection timeout; HTTP 000 | PASS for this reachability probe; SG/binding unverified |
| Health GET with `Origin: https://untrusted.example` | No CORS grant | 200 with no `Access-Control-Allow-Origin` | PASS for this origin/method |

Health is independent of database queries. HTML delivery does not verify
JavaScript execution, dashboard rendering or frontend build/source parity.
No browser automation was performed. CORS is not an authorization boundary.

## Local integration and validation results

Executed from `backend`:

```bash
../.venv/bin/python -m unittest discover -s tests -v
```

Result: **92 test entries, 89 passed, 2 skipped, 1 error** in 5.188 seconds.
The error is `test_lambda` import failure: `ModuleNotFoundError: No module named
'psycopg'`. `mangum` is also absent from the local environment; neither was
installed/upgraded here. The two skipped tests require `TEST_POSTGRESQL_URL`
(disposable PostgreSQL migration/persistence and concurrent availability tests).
Python was 3.14 locally; this is not an exact reproduction of the pinned server
runtime. Deprecation warnings were emitted by the installed FastAPI/Python
combination. The whole suite **did not pass**.

| Local feature group | Expected | Actual / evidence | Result and limit |
| --- | --- | --- | --- |
| Student/supervisor login, current user | Valid credentials authenticate correct role | Phase 2 login/current-user and role tests completed successfully on isolated data | PASS locally; live not tested |
| Invalid credentials, JWT expiry, missing/invalid/deleted-user tokens | Deny access | Corresponding Phase 2 tests passed | PASS locally; no live expiration/login test |
| Role, department and ownership restrictions | Deny cross-role/department/user access | Phase 2, scheduling, workflow and attendance tests passed | PASS locally |
| Classes and availability | CRUD, reject overlaps, preserve conflict information | Phase 2 CRUD, ranges, overlap and conflict tests passed | PASS locally |
| Employees, locations and staffing | Correct scope, eligibility and validation | Department/profile and scheduling location/requirement tests passed | PASS locally |
| Generation and published shift reads | Enforce hard constraints and visibility | Scheduling generation/version/own-shift tests passed | PASS locally |
| Manual edits and publication | Atomic updates, stale-write rejection, retained history | Workflow edit, concurrent edit, publish/history/rollback tests passed | PASS locally |
| Time off and review | Correct lifecycle, permissions and scheduling effects | Workflow approval/rejection/lifecycle and leave constraint tests passed | PASS locally |
| Clock-in/out and attendance history | Own published shifts, valid timing, atomic records | Attendance clock, ownership, concurrency, UTC/DST and totals tests passed | PASS locally |
| Attendance corrections and CSV | Audited approvals, rejection preserves times, safe export | Attendance correction, audit, privacy and CSV tests passed | PASS locally |
| SQLite schema and explicit seeds | Migration preservation and repeatable demo seed | Phase 2 and scheduling upgrade/seed tests passed on isolated DBs | PASS locally; EC2 DB untouched |
| Production guardrails/readiness | Reject unsafe config, check revision, hide docs in production | Deployment settings/readiness/logging tests passed | PASS locally; live readiness failed |
| Lambda adapter/private job | All integration tests import and execute | Missing local psycopg prevents test module import | ERROR; alternative architecture not verified |
| PostgreSQL concurrency/persistence | Run against disposable PostgreSQL | Environment not supplied; two tests skipped | NOT EXECUTED |
| Student/supervisor dashboard rendering | Browser loads and completes tasks | No browser or authorized live sessions used | NOT EXECUTED |
| Persistence across EC2 service restart | Same fictional record survives restart | No downtime approval or server access | NOT EXECUTED |

Additional executed checks:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s scheduler/tests -v` | PASS: 15 tests |
| `npm run build` in `frontend` | PASS: Vite 7.3.7 built 55 modules; generated assets ignored by Git |
| `npm run lint` in `frontend` | PASS |
| `npm audit --json` in `frontend`, approved network retry | Exit 1: 3 moderate package findings, no high/critical; minimatch plus affected eslint/config-array dependencies |
| `npm audit --omit=dev --json` | Exit 0: 0 runtime dependency findings |
| `uv tool run --from pip-audit pip-audit -r backend/requirements.txt --no-deps --disable-pip --progress-spinner off` | Exit 1: tool reported 24 advisory rows across python-dotenv 1.1.0 and PyJWT 2.10.1; repeated IDs included |

The Python audit checked declared direct pins only, not the complete transitive
resolution or installed EC2 packages. Its raw count includes duplicate advisory
rows, not 24 confirmed independently exploitable application defects. Review
advisory applicability and deduplicate before selecting a compatible patch.
Returned examples include `PYSEC-2026-2270` for python-dotenv and
`GHSA-pxh4-856f-4h89` for PyJWT. No automated fix or lockfile update was run.
The npm development finding references
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
Neither audit establishes the deployed dependency inventory.

## Security and reliability assessment

| Priority | Finding / evidence | Required follow-up |
| --- | --- | --- |
| High | Public HTTP works; HTTPS connection failed | Configure trusted TLS and renewal before real credentials/data; no domain ownership supplied |
| High | Backend audit returned advisory matches | Verify applicability and deployed pins, prepare reviewed upgrades, rerun auth/regression tests before release |
| High | Live schema/seed/JWT configuration unknown; health does not prove DB readiness | Authorized private metadata/schema inspection; no secret values in reports |
| High | Server revision differs in observable readiness behavior | Compare deployed SHA/config/routes with GitHub before any update |
| Medium | Current production mode refuses SQLite | Preserve live config; review a compatible SQLite hardening approach separately; do not switch DB implicitly |
| Medium | SSH/SG/EBS encryption and 8000 binding unverified | Read exact instance SGs, including IPv6; verify listener locally; timeout alone is limited evidence |
| Medium | Backups, restart policy, disk and memory not inspected | Read metadata, create approved consistent backup/restore rehearsal, check resources; restart only with approval |
| Medium | Login rate limiting not implemented in application; JWT revocation/refresh absent | Review scoped application/Nginx hardening; keep tokens short-lived and in memory |
| Medium | Development dependency audit reports moderate findings | Review compatible lockfile updates; rerun lint/build; no automatic upgrades |
| Review | `.env`, key and database ignore patterns exist | Tracked env files are examples and Alembic code; no tracked `.pem`/`.key` matched; this is not a full Git-history secret scan |
| Review | Untrusted-origin health response lacked CORS grant | Inspect effective live allowlist and authenticated preflights privately |

An owned institutional domain with ACME renewal is an option. A public IP can
also use a short-lived certificate with a compatible client; verify renewal and
IP stability before choosing it. [Let's Encrypt's current IP/Certbot guidance](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html).
No domain purchase, certificate issuance, DNS change, security-group change or
new AWS service is authorized by this report.

## Architecture comparison and assignment fit

| Aspect | Existing EC2 deployment | Prepared serverless alternative |
| --- | --- | --- |
| Request path | Nginx serves SPA, proxies to loopback Uvicorn | CloudFront/S3, HTTP API, Mangum/FastAPI Lambda |
| Persistence | SQLite on existing EBS; operator-managed backups | Private Aurora PostgreSQL Serverless v2; migrations/private job required |
| Lifecycle | Single host/systemd; manual update | CloudFormation stacks, packaged functions, private migration/seed jobs |
| TLS | Incomplete on public endpoint | Planned managed viewer/API TLS; not verified deployed |
| Failure/operational concerns | Single-host failure, OS patching, SQLite concurrency, disk and backup management | Cold/resume latency, connection discipline, IAM/VPC integration and deployment complexity |
| Cost | Existing compute, disk and public IPv4 usage; actual account/bill not read | Usage/ACU/storage/request charges; old estimates are assumptions, not measured costs |
| Verification status | Public connectivity tested; server internals and live workflows pending | Code/templates exist; no current AWS deployment evidence; Lambda test module blocked locally |

Inspected `serverless-artifacts.json` (private artifact bucket), `serverless.json`
(Lambda/HTTP API/Aurora/network/IAM), `frontend.json` (S3/CloudFront SPA/API routing),
and `scripts/aws_deploy.py` (explicit profile/region, identity/cost gates,
change-set review). Packaging/runtime/private-job code and tests are present.
The serverless DB contract is PostgreSQL; SQLite cannot serve as persistent
shared Lambda storage. The existing EC2 runtime files target a separate Amazon
Linux/PostgreSQL plan and must not overwrite this Ubuntu/SQLite host.

This inspection establishes implementation presence, not completeness of live
integration, current CloudFormation validation, account eligibility or successful
provisioning. No live template validation or full Lambda package build was run in
this verification. Historical template validation claims remain in their dated
preparation guides.

No supplied assignment rubric requires Lambda, Aurora, RDS or CloudFormation.
The existing architecture can host the implemented functional features; whether
it meets every grading requirement remains **unconfirmed** until the rubric is
reviewed. A migration is not currently necessary for verification and is not
recommended as a prerequisite. No migration cost/downtime proposal is activated;
if the rubric requires a different architecture, prepare a separately approved
resource/cost/data-transition/rollback plan before provisioning.

## Remaining acceptance work

1. Supply an existing authorized AWS profile and verified SSH access; confirm
   account/instance identity, EC2 checks, storage, SGs and server resources.
2. Privately record deployed SHA, environment metadata, service/Nginx settings,
   effective SQLite path, permissions, schema revision and demo account existence.
3. Establish trusted HTTPS and automated renewal before real credentials; do not
   assume that a public 443 SG rule is sufficient.
4. Use an isolated fictional department and authorized test accounts over TLS.
   Execute student/supervisor login, expiry, dashboard rendering and every CRUD,
   generation, edit, publish, time-off approval/rejection, clock and correction
   workflow listed above. Record expected/actual outcomes and cleanup only test
   records while preserving publication/attendance audit history.
5. Back up and restore a disposable SQLite copy; obtain maintenance approval for
   the restart/persistence test. Never restart or reboot during read-only checks.
6. Restore missing pinned local dependencies in a compatible environment and rerun
   the complete suite; run PostgreSQL tests only if evaluating that alternative.
   Review audit fixes separately; do not infer deployment safety from local tests.
7. Compare the assignment rubric with the architecture and outstanding SNS or
   other service requirements. Capture screenshots only after safe live tests.
8. Review this documentation diff and approve a commit; no push is authorized.

## Git change summary and validation

Documentation changes only:

- `README.md`: current EC2 status, verification links, removed contradictory
  no-deployment/serverless-primary claims; local application instructions retained.
- `docs/aws-deployment.md`: existing-server runbook, safe inspection, installation
  references, backups, updates, rollback, troubleshooting and HTTPS requirements.
- `docs/aws-ec2-verification.md`: this evidence-based status/integration/security
  report, architecture comparison and remaining acceptance work.
- `docs/aws-ec2-rds-proposal.md`: preserved previous deployment guide as a clearly
  labeled historical alternative; its commands were not executed.
- `docs/aws-serverless-deployment.md`, `docs/aws-project-free-plan-decision.md`,
  `docs/aws-architecture.md`, `infrastructure/README.md`: existing-deployment
  precedence and historical/prepared-infrastructure boundaries.

`git diff --check` passed. A local Markdown file-link check passed for all
41 relative file links across the eight changed/new documents (anchors and remote
URLs were not validated). The archived proposal was checked against the original
tracked runbook and retains it verbatim beneath its historical-status banner. No `.env`, database, key, token, audit environment or credentials
are included. No files have been staged. Proposed commit:

```text
docs: document existing AWS EC2 deployment and verification
```

The task explicitly requires approval before commit or push. A commit remains
pending that approval; direct protected-branch push is not proposed.
