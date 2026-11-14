# Authorized SSH verification addendum

Audit date: November 13, 2026 (America/Chicago). Existing key supplied by user;
SSH used strict checking against recorded host keys. No key contents, secret
values or application records were displayed. Read-only host checks only.
This supersedes the original audit's lack-of-SSH findings; authenticated workflow,
restart persistence, restore rehearsal and denied AWS/billing checks remain pending.

## VERIFIED COMPLETE

| Finding | Evidence | Next action |
| --- | --- | --- |
| Authorized host access | SSH as ubuntu to 3.133.115.154 succeeded using supplied existing key. | Retain private key securely; never commit it. |
| Host OS/runtime | /etc/os-release: Ubuntu 26.04.1 LTS; running service executable is Python 3.12.16. | Use these versions when reproducing runtime issues. |
| Runtime source location/revision | Service and process working directory /home/ubuntu/CampusShift/backend; checkout clean at fc04a91d4a6e5790b2b392409d00e4a5ef99b636. Running command confirms Uvicorn and main:app. | Record this as the running service's checkout revision; no immutable startup hash exists to independently prove every loaded file matches disk. Compare to newer GitHub before any separately reviewed update. |
| Service management | nginx/campusshift active and enabled; campusshift Restart=always, NRestarts=0, start timestamp 2026-11-13 01:26:10 UTC, user ubuntu. | Keep services unchanged during audit. |
| Effective web routing | sudo nginx -T succeeds; listen 80, root /var/www/campusshift, /api/ proxy to http://127.0.0.1:8000, SPA try_files fallback to /index.html. | Associate static assets with a release manifest during a later deployment. |
| Backend listener isolation | ss -ltn confirms 127.0.0.1:8000; public listeners are port 80 and SSH 22. | Retain loopback API binding. |
| Live SQLite identity | Runtime environment DATABASE_URL dialect is sqlite; process open file descriptors point to /home/ubuntu/CampusShift/backend/campusshift.db. File also matches backend environment configuration. | Preserve existing SQLite deployment; no migration to another engine needed for this audit. |
| Database integrity/schema | Read-only SQLite connection: PRAGMA integrity_check = ok; alembic_version = 9e57ab896061. Class, availability, scheduling, time-off, publication and attendance tables present. | Complete authenticated workflow tests; table presence and integrity do not prove business correctness. |
| Signing-key presence | Runtime JWT_SECRET exists and is 64 bytes; no value exposed. APP_ENV absent in process and backend environment file. | Verify expiry/CORS/other effective settings separately; length alone does not establish entropy or security. |
| Capacity at observation | Root 20% used, ~15 GiB available; ~515 MiB available RAM; no swap. | Observe capacity during presentation rehearsal; this is a point-in-time reading. |

## INCOMPLETE OR BROKEN

| Finding | Evidence | Next action |
| --- | --- | --- |
| HTTPS listener absent | Host socket inventory has port 80 but no 443; nginx configuration only listens on 80. Confirms earlier external HTTPS refusal. | Prepare separately authorized EC2 TLS/certificate/renewal work. |
| DB permissions are broad | SQLite file mode 0644, 221184 bytes; backend runs as ubuntu. | Review directory traversal permissions and local users, then plan least-privilege file/service hardening separately; no chmod performed. |
| Release freshness/readiness gap remains | Running checkout fc04a91… predates local 0b445f6… and remote 1243fce…; public /api/ready returns 404. | Review a SQLite-compatible EC2 release after backup; do not blindly run prepared Amazon Linux/PostgreSQL installers. |

## NOT YET VERIFIED

| Finding | Evidence / limit | Next action |
| --- | --- | --- |
| Application backups and off-instance recovery | No user crontab; no CampusShift/SQLite references found in checked /etc/cron.d, cron.daily, cron.hourly or matching systemd timers. Only dpkg backup timer observed. Shallow filename checks of checkout, /home/ubuntu/backups and /var/backups found no application backup. This is not an exhaustive backup inventory. | Inspect root crontab, custom scripts/storage and external copies; confirm backup consistency/retention and rehearse restore in a disposable location. |
| Persistence across restart | No restart or data mutation performed. EBS-backed file and healthy schema now verified. | Perform separately approved fictional-row/service-restart acceptance test. |
| Successful live workflows and browser execution | No student/supervisor test sessions supplied; only unauthenticated route checks and isolated local tests completed. | Use existing fictional test accounts over a protected connection for authentication, classes, availability, generation/publishing, time off and attendance. |
| Complete spending and resource scope | Host access does not extend denied AWS service/billing reads. | Complete these checks through existing authorized read-only project access. |
