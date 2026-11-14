# CampusShift — current deployment audit

Refreshed November 13, 2026 (America/Chicago). Project/account `548280227313`;
selected Region `us-east-2`; CLI profile `campusshift`. This report supersedes the
earlier audit and host addendum where their observations differ.

**Assessment:** existing EC2 hosting, frontend delivery, FastAPI liveness, SQLite
integrity/schema and local regression checks are verified. Complete presentation
acceptance remains pending. The selected architecture stays EC2/Nginx/React/
FastAPI/SQLite. No Lambda/Aurora deployment is proposed or performed.

Methods: fresh STS/EC2/service inventory; strict-host-key SSH with the user's
existing key; read-only SQLite connection; unauthenticated public HTTP requests;
GitHub API; local isolated tests and frontend build into `/private/tmp`.
No production record mutations, service restarts, deployments, infrastructure/SG
changes, credential changes, database migrations, commits or pushes occurred.
No secret values, password hashes or individual application records are included.
Audit artifacts alone were written inside docs/architecture. Evidence summaries:
[current-audit-evidence](current-audit-evidence/).

## VERIFIED COMPLETE

| Finding | Supporting evidence | Recommended next action |
| --- | --- | --- |
| Correct authorized AWS project | Fresh STS get-caller-identity: account 548280227313, campusshift-diagram-reader identity. | Retain scoped read-only inventory access. |
| Existing EC2 runs normally | describe-instances: i-0b662a28fc2d1aeaf, t3.micro, running, 3.133.115.154 / 172.31.7.136, us-east-2a. Instance/system/attached-EBS checks all ok; reachability passed. | Keep this deployment target; verify application workflows separately. |
| Storage attachment and capacity | vol-02dd0fbe1cd9a0e52: attached root /dev/sda1, 20 GiB gp3, 3000 IOPS / 125 MiB/s. SSH df: root 20% used, about 15 GiB available. Available RAM about 508 MiB at observation; no swap. | Observe capacity during final rehearsal. This is a snapshot of health, not a load test. |
| Public routing | VPC vpc-037fd02904c677068; subnet subnet-04f8e92b45880a336. Main route rtb-029b4811950e603b4 has active default route through igw-0e40f27c2e32899b8 and local VPC route. | Preserve existing routing. |
| SG and backend listener isolation | sg-0c293c3a0ee64fd10 permits public IPv4 80/443, SSH 22 from one administrator /32, no IPv6 ingress, unrestricted IPv4 egress. SSH ss confirms backend bound to 127.0.0.1:8000; external 8000 request times out. IMDS tokens required. | Keep API loopback binding; no need to expose 8000. |
| Nginx and backend process management | SSH systemctl: nginx/campusshift active and enabled; Restart=always, NRestarts=0. Service/process cwd /home/ubuntu/CampusShift/backend. Earlier same-session command check identified uvicorn main:app; current executable Python 3.12.16. OS file identifies Ubuntu 26.04.1 LTS. | Retain configuration; record actual runtime instead of using the prepared Amazon Linux installer defaults. |
| Effective Nginx configuration | nginx -T exits 0; listen 80; document root /var/www/campusshift; /api/ proxies to http://127.0.0.1:8000; try_files fallback to /index.html. | Preserve SPA and proxy behavior in any later TLS change. |
| HTTP frontend and API delivery | GET / and /student/attendance return 200, identical SPA HTML; Server nginx/1.28.3 (Ubuntu). JS/CSS return 200. /api/health returns healthy CampusShift JSON publicly and on loopback. Unknown API path returns JSON 404. | Complete browser/authenticated acceptance; delivered assets are not proof of every UI flow. |
| Frontend asset parity with current local source | Fresh npm build produces index-DvLhM7V9.js and index-D-O9YkoH.css. SHA-256 values match files served publicly and files read under /var/www/campusshift/assets. | Record these hashes with the next release. Exact asset parity does not establish backend source parity or historical frontend commit identity. |
| Deployed service checkout identified | Clean host checkout fc04a91d4a6e5790b2b392409d00e4a5ef99b636; systemd and running process cwd point into it. | Treat this as the deployed backend checkout revision; an immutable startup/build hash is absent, so exact loaded-code provenance beyond this remains limited. |
| SQLite is actually used on EC2 | Process environment DATABASE_URL dialect sqlite; open process FDs point to /home/ubuntu/CampusShift/backend/campusshift.db. Read-only DB inspection succeeds. | Preserve this path and environment in any approved release. Local SQLite is no longer the only evidence. |
| DB integrity and schema | PRAGMA integrity_check returns ok; alembic_version is 9e57ab896061, matching current repository schema head. Expected scheduling, publication, time-off and attendance tables exist. | No schema change is justified by this audit; verify workflows and backup restore next. |
| Aggregate application data exists | Read-only counts: 2 users (1 student, 1 supervisor), 1 department, 5 class rows, 4 availability rows, 2 schedule runs, 1 assigned shift. No identities or row contents retrieved. | Use existing authorized fictional accounts for acceptance. Counts do not establish data accuracy, publication state or successful workflows. |
| Unauthenticated access protection | GET /api/auth/me; students/me/classes, availability, schedule, time-off, attendance; supervisor/schedules and employees all return JSON 401. | Test successful login, expiry, ownership and role/department isolation with authorized test accounts. A 401 is not evidence of a working database-backed operation. |
| Signing configuration present | Runtime JWT_SECRET is 64 bytes; value not exposed. | Verify expiry, entropy/provenance and other security settings privately if required; length alone does not establish security. |
| Current local regression checks | Full backend unittest discovery from backend: 90 entries, 88 passed, 2 PostgreSQL-only tests skipped. Scheduler: 15/15. npm lint and npm build pass. Local SHA 1fdf261d62353bb1c8eff8d66c489bf348ed9847. | Use this as local evidence only; it does not certify the older deployed backend. Initial wrong-directory test invocation failed imports; documented-directory rerun passed without code changes. |
| GitHub/local repository state | Fresh GitHub main 1243fceb646b8fa1a9b8aa92021175aed0d1d9c2, Restore EC2 deployment and retire serverless infrastructure. Local merge 1fdf261… includes it; only two extra historical documentation files differ in tracked content. No tracked local modifications. | Local updates are complete. No further pull/merge is required for this observed GitHub target. Do not push as part of audit. |
| Architecture choice matches live topology | Host and AWS reads confirm EC2/Nginx/static frontend/FastAPI/SQLite/EBS. Current GitHub retires serverless code/templates and selects EC2. No new Alembic version files differ between deployed and target revisions (env.py does differ). | Keep the current architecture. Review runtime/configuration changes before an eventual release even though migration versions match. |
| No unexpected resources in successful Ohio listings | One EC2 and one attached EBS volume; no owned EBS snapshots, NAT Gateways, Elastic IP allocations, VPC endpoints, ELBv2 or classic load balancers returned. No extra detached EBS volumes. | Limit absence claims to these services/Region; complete denied inventory through authorized access. |

## INCOMPLETE OR BROKEN

| Finding | Supporting evidence | Recommended next action |
| --- | --- | --- |
| HTTPS unavailable | External HTTPS connection refused; host has no 443 listener; effective Nginx listens only on 80. SG permitting 443 is insufficient. | Prepare trusted TLS and renewal on the existing EC2 host, preserving routes and loopback binding; obtain required approval before production changes. Do not send real credentials over HTTP. |
| Readiness route absent from deployed backend | /api/ready returns JSON 404 publicly and directly at 127.0.0.1:8000. Source at deployed fc04a91 has health but no ready route; current repository implements ready. SQLite schema/integrity independently pass. | Plan reviewed backend update after consistent backup; this is a release gap, not evidence of database failure or solely a proxy problem. |
| Backend checkout behind GitHub | Host fc04a91… versus target 1243fce…; includes backend configuration/session/logging/readiness changes. Frontend assets already match target build. | Review the precise diff, backup and rollback before an approved EC2 release. Do not run Amazon Linux/PostgreSQL provisioning scripts on this Ubuntu/SQLite host. |
| EBS data protection gap | Encrypted=false, DeleteOnTermination=true, owned Ohio snapshots empty. | Establish verified off-instance backups first; review encryption/termination protection separately without replacing storage during audit. |
| SQLite backup implementation gap | Repository scripts/database_backup.sh uses pg_dump/pg_restore. Host user/root crontab checks return no successful crontab; no application backup references found in checked cron/systemd configs; only dpkg backup timer observed. | Prepare a SQLite online-backup solution, protected off-instance storage, retention and disposable restore test. No backup was created or live file overwritten in this audit. Existing external backups remain possible but unverified. |
| Repository production guardrail incompatible with selected SQLite | Current config.py refuses SQLite under APP_ENV=production. Actual process APP_ENV is unset. | Review a SQLite-compatible validation/hardening change separately; do not change live APP_ENV or migrate engines implicitly. |
| Local database-file permissions warrant review | Host DB mode 0644; service runs as ubuntu. | Inspect parent-directory access and local-user exposure; prepare least-privilege permissions/service changes separately. File mode alone does not prove public exposure. |
| Architecture/status documentation is stale in specific places | Current remote EC2 docs still say engine/path/processes/revision uninspected; this audit now confirms them. Remote docs/architecture.md retains historical Phase 3 unpublished-only wording despite later publication support. README mentions a new Amazon Linux Python runtime while live host is Ubuntu/Python 3.12.16. | Update docs in a later documentation task using these verified facts, clearly separating historical phases/reference installers. No existing application/deployment docs were edited during this audit. |

## NOT YET VERIFIED

| Finding | Supporting evidence / limitation | Recommended next action |
| --- | --- | --- |
| Successful live authentication and registration | No live test passwords or authorized sessions supplied; no successful login/registration performed. Existing user counts and 401s do not prove authentication works. | Use existing fictional student/supervisor accounts through a protected connection. Verify login, logout/expiry and registration only in an approved test fixture; never reset existing passwords merely to test. |
| Live class schedule and availability CRUD/conflicts | Read routes deny missing tokens; isolated local API tests cover CRUD/overlap/ownership. No live record writes made. | Execute fictional class/availability create/edit and overlap/conflict checks after authorized test access is established; preserve existing records. |
| Live generation, draft editing and publishing | DB contains two runs/one shift; local scheduling/workflow tests pass, but those rows are not an execution record of this audit and publication status was not retrieved. No live generation/publish POSTs made. | Run controlled supervisor draft generation, conflict review/edit, publication and student visibility checks with fictional data. |
| Live time-off workflow | Time-off table has zero rows at inspection. Local tests pass; no live submit/decision/cancel performed. | Test fictional request, supervisor decision, cancellation and scheduling exclusion/audit. Empty table does not prove a defect. |
| Live attendance workflow | Attendance table has zero rows at inspection. Local tests pass; no clock actions, correction decisions or CSV workflow tested live. | Test eligible fictional published shifts, clock-in/out, hours, duplicate prevention, corrections/audit and role-scoped export. |
| Complete UI/browser execution | HTML/assets retrieved and matched; no browser automation or authenticated UI interaction performed. | Rehearse actual student/supervisor presentation flows, direct-route refresh and browser errors. |
| Persistence across restart/reboot | SQLite on attached EBS and service boot enablement confirmed; no restart/reboot or fictional-row persistence test performed. | After backup and maintenance approval, record a fictional row, restart the service and recheck same path/row. Do not stop/start EC2 solely for this audit; automatic public IP may change. |
| Verified backup retention and recovery | Limited host discovery found no application backup files/jobs. AWS Backup vault listing denied; no external copy inspected. AMI source snapshot on a volume is not a current DB backup. | Inspect existing external storage and custom job locations; prove a consistent backup restores into a disposable file and passes integrity/schema checks. Never overwrite live DB. |
| Sensitive-data classification | Only counts/schema were inspected; no user emails/names, password hashes or application records read. Two accounts need not be fictional. | Have the owner classify existing data before any future test fixture, migration or backup transfer; preserve it until then. |
| Complete unexpected-resource/charge inventory | Fresh AccessDenied for RDS instances/clusters, Lambda, CloudFormation, logs, S3, CloudFront, AWS Backup, ECS/EKS and API Gateway. Extra reads for Secrets Manager, plan state and us-east-1 logs also denied. Cost Explorer denied. | Use an existing authorized owner/read-only billing identity to review denied services, global resources and relevant Regions. No IAM/plan changes are part of this audit. |
| Independent reconfirmation of serverless cleanup | GitHub docs record teardown and three secrets marked for deletion; this identity cannot independently list the relevant services/secrets. No serverless code is present in current main. | Check retained cleanup receipts and authorized metadata listings. Do not recreate anything; repository absence is not proof of cloud absence. |
| Actual current charges/credits | Observed potential billable components: t3.micro, 20 GiB EBS, one public IPv4. CPU mode remains Unlimited (earlier same-session fresh read); actual cost/plan queries denied. Docs estimate ~$12.84/month before variable costs/credits, not a measured bill. | Review AWS Settings > Billing and surplus CPU/transfer/backup usage. No new price lookup or independent cost forecast performed here. |
| Additional host security configuration | JWT length, bindings and SG verified; full effective CORS, expiry, rate limiting, installed dependency vulnerabilities and patch status not audited in this refresh. | Inspect relevant metadata privately and review security posture before a later release; do not infer these from repository defaults. |

Completion order: verify backup/recovery; prepare reviewed HTTPS and backend release
with rollback; then perform the authenticated fictional workflow rehearsal and
approved persistence test. Complete billing inventory with authorized read access.
These recommendations do not authorize or perform production changes.
