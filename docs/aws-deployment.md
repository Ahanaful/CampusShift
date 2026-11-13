# Existing EC2 deployment: operations and verification

Updated November 13, 2026. This is the current deployment runbook. Preserve the
existing application; do not create resources or apply the alternative templates.
See the [dated verification report](aws-ec2-verification.md) for evidence and limits.
The application is a university demo with unresolved security and testing work,
not a verified production service.

## Current architecture and inventory

```text
Browser -- HTTP :80 --> Nginx --> /var/www/campusshift (React build)
                            --> /api/ --> 127.0.0.1:8000 (FastAPI/Uvicorn)
                                          systemd --> SQLite on EC2 EBS
```

The following inventory is operator-reported unless the verification report says
otherwise. Public responses cannot prove AWS ownership or internal configuration.

| Item | Existing configuration |
| --- | --- |
| Expected account / region | `548280227313` / `us-east-2` (Ohio) |
| Instance name / ID | `CampusShift-Server` / `i-0b662a28fc2d1aeaf` |
| Type / disk | `t3.micro` / 20 GiB gp3; encryption and free capacity unverified |
| OS | Ubuntu 26.04.1 LTS, reported; confirm `/etc/os-release` |
| Public application | <http://3.133.115.154> |
| Source | <https://github.com/Ahanaful/CampusShift> |
| Checkout / backend / frontend | `/home/ubuntu/CampusShift`, subdirectories `backend`, `frontend` |
| Python environment / settings | `backend/.venv`, `backend/.env` |
| Service unit | `/etc/systemd/system/campusshift.service` |
| Nginx site / assets | `/etc/nginx/sites-available/campusshift`, `/var/www/campusshift` |
| Backend listener | Reported `127.0.0.1:8000` |
| Database | Reported SQLite; default resolves to `backend/campusshift.db`; verify effective URL privately |
| Network rules | Reported SSH restricted to developer IP, HTTP/HTTPS public; AWS read still needed |

The public address may change after stop/start unless statically assigned; do not
stop the instance to test persistence. [AWS stop/start behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).

## Read-only AWS and server inspection

Use an existing authorized profile; do not create keys, enable services or widen
permissions. This workstation currently lacks AWS credentials and SSH identities.
These commands are pending operator steps, not executed verification:

```bash
aws sts get-caller-identity --profile campusshift --region us-east-2 --query Account --output text
# Continue only if the result is exactly 548280227313.
aws ec2 describe-instances --profile campusshift --region us-east-2 \
  --instance-ids i-0b662a28fc2d1aeaf \
  --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Type:InstanceType,IP:PublicIpAddress,Image:ImageId,Groups:SecurityGroups,Volumes:BlockDeviceMappings}'
aws ec2 describe-instance-status --profile campusshift --region us-east-2 \
  --instance-ids i-0b662a28fc2d1aeaf --include-all-instances
# Use only SG IDs and volume IDs returned above:
aws ec2 describe-security-groups --profile campusshift --region us-east-2 --group-ids VERIFIED_SG_ID
aws ec2 describe-volumes --profile campusshift --region us-east-2 --volume-ids VERIFIED_VOLUME_ID
```

Inspect SG ingress for SSH restricted to an authorized address, no public 8000,
and intended 80/443 rules, including IPv6. Confirm volume size/type/encryption.
Account mismatch or access denial ends AWS changes; do not alter the account plan.

Connect as `ubuntu` using the existing authorized SSH key and verified host key.
Do not disable host-key checking. On the server:

```bash
cat /etc/os-release
cd /home/ubuntu/CampusShift
git status --short
git rev-parse HEAD
git remote -v
sudo systemctl is-active campusshift nginx
sudo systemctl is-enabled campusshift nginx
sudo systemctl show campusshift -p User -p Group -p WorkingDirectory -p Restart -p RestartUSec -p NRestarts
sudo nginx -t
ss -ltn
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://localhost/api/health
curl -i http://localhost/api/ready
df -h /
free -h
stat -c '%a %U:%G %n' backend/.env
```

Privately inspect the service unit and active Nginx configuration. Confirm the
venv interpreter, `main:app`, backend working directory, `.env` loading, loopback
binding, startup enablement and `Restart=on-failure` or `always` with a delay.
Inspect recent `journalctl -u campusshift -n 100 --no-pager` locally; redact secrets,
request data and tokens before sharing. Do not paste environment files, full
process environments or unreviewed unit/log contents into reports.

Check only JWT presence and byte length (at least 32), token lifetime (1–60
minutes), environment mode, exact CORS origins and SQLite path privately. Do not
print JWT values. Same-origin `/api` hosting needs no permissive cross-origin
access. A public timeout on port 8000 does not prove loopback binding or SG rules.

## Database inspection, seeds and backups

From `backend`, use the same service environment and identity:

```bash
.venv/bin/python -m alembic current
.venv/bin/python -m alembic heads
.venv/bin/python -m alembic check
```

This checkout expects head `9e57ab896061`, through initial, scheduling, workflow,
and attendance revisions. Privately inspect SQLite's `sqlite_master` table names,
`alembic_version`, and `PRAGMA integrity_check` using a read-only connection to
the **verified effective database path**. Never open an assumed filename in a mode
that silently creates a new database. Compare table names with SQLAlchemy metadata;
check only counts/existence of demo departments and accounts, not password hashes.
Migrations do not create demo users. Live tables, revisions and demo users remain
unverified.

`app.seed --demo` creates Campus Library and student/supervisor example accounts;
`app.seed_scheduling --demo` creates the separate Scheduling Demo department and
staffing data. They prompt privately for a password and preserve existing account
passwords. They accept SQLite but are documented for disposable local data.
`app.seed_cloud_demo` targets the separate PostgreSQL proposal. None was executed
against EC2. Review department/account collisions before any explicit live seed;
do not create users or reset passwords just to obtain test credentials.

Before any migration/update, create a consistent SQLite backup using Python's
SQLite backup API or SQLite `.backup` against the verified file, with destination
outside the checkout/web root and mode 0600. Do not copy a running WAL database's
main file alone. Keep backups off the instance through an existing approved
mechanism; new services require approval. Test integrity and restoration on a
separate disposable copy. Check database ownership, restrictive file permissions
(e.g. 0600) and writable parent directory for journal/WAL files. Do not chmod an
unverified path or recursively change the checkout permissions.

Persistence acceptance needs a recorded fictional row, an approved service
restart, then a read of the same row and database path. This was not executed.

## Installation and configuration reference

These are reference steps for repairing the **existing checkout after review**,
not instructions to clone a second deployment. Do not execute installation,
seeding, migrations or restarts during read-only verification.

If source is missing, first investigate the existing path and remote. For an
approved repair, use the existing GitHub repository and a reviewed commit. Never
overwrite a dirty checkout or run the Amazon Linux bootstrap on Ubuntu.

Backend setup (only if the existing environment needs rebuilding):

```bash
cd /home/ubuntu/CampusShift/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e ..
# Create .env only if absent; preserve existing values and permissions.
```

Privately configure a random `JWT_SECRET` of at least 32 bytes, the verified
absolute SQLite `DATABASE_URL`, token lifetime and exact frontend CORS origin.
Generate a secret directly into protected storage; never print it into a shared
terminal transcript. Keep `.env` outside Git, owned/readable only by the service
identity. Never place secrets in `VITE_*` variables.

**Compatibility constraint:** `Settings.from_env()` in this checkout rejects
SQLite under `APP_ENV=production`. The reported SQLite server's mode/revision is
unknown. Do not set production mode or migrate to PostgreSQL as an incidental
fix. Keeping the existing mode also leaves development API docs available unless
blocked elsewhere. A reviewed SQLite hardening change would need explicit
security validation before deployment.

Only after backup, review and maintenance approval, apply migrations with the
service's effective environment using `.venv/bin/python -m alembic upgrade head`.
Never downgrade the live schema to test it.

The service should invoke this command from the backend directory, as a non-root
user with access to the database and protected environment:

```text
/home/ubuntu/CampusShift/backend/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The unit should use `Type=simple`, `WorkingDirectory`, an appropriate `User` and
`Group`, `Restart=on-failure`, `RestartSec=5`, and `WantedBy=multi-user.target`.
Do not use development reload or multiple SQLite writers as a tuning shortcut.
Capture and review the existing unit before editing; these settings are a
recommended reference, not a verified copy of the live file.

Frontend build:

```bash
cd /home/ubuntu/CampusShift/frontend
npm ci
# Ensure VITE_API_BASE_URL is unset/empty for same-origin /api calls.
npm run build
npm run lint
```

Review `.env.production` and shell build settings privately. Vite's development
proxy is not included in the build. Stage `dist` beside the existing deployed
assets, validate it, and switch assets only during an approved update. Retain the
previous assets for rollback and avoid deleting assets requested by open clients.

Minimum Nginx reference (compare with the actual site before changes):

```nginx
server {
    listen 80;
    server_name 3.133.115.154;
    root /var/www/campusshift;
    index index.html;
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location / { try_files $uri $uri/ /index.html; }
}
```

The absent trailing URI on `proxy_pass` preserves `/api/`. Unknown API routes
must remain JSON 404 responses rather than the SPA. This HTTP example describes
the current topology; configure TLS before accepting real credentials.

## Manual updates, restart and rollback

No update, migration, restart or reload was performed during this verification.
For a separately approved maintenance window:

1. Record the deployed full Git SHA, clean/dirty status, database path/revision,
   effective configuration metadata, unit/site copies and current frontend assets.
2. Fetch the remote branch without merging; review `git diff HEAD..origin/main`,
   migration changes, dependencies and configuration against the **server SHA**.
   Stop if there is teammate work or incompatible schema/configuration.
3. Back up SQLite consistently and validate restoration on a disposable copy.
   Select the reviewed commit; avoid blind `git pull` or `reset --hard`.
4. Fast-forward only after review (`git merge --ff-only REVIEWED_COMMIT`), install
   reviewed dependencies, stage the frontend build, and apply only reviewed
   additive migrations under the verified service environment.
5. If the unit changed, run `sudo systemctl daemon-reload`. Restart the backend
   with `sudo systemctl restart campusshift` only with downtime approval. For an
   approved Nginx change run `sudo nginx -t` before `sudo systemctl reload nginx`.
6. Run health/readiness, protected endpoints, browser routes, fictional student
   and supervisor flows and persistence checks. Capture outcomes without tokens.
7. If checks fail, restore previous code/assets/configuration where compatible.
   Schema rollback or database restore requires separate review: restoring a
   backup loses subsequent writes. Never automatically downgrade/drop tables.

## HTTPS and security requirements

No owned domain was supplied. Determine whether an existing institutional domain
can be used before purchasing anything. An existing domain plus an automated
ACME certificate on Nginx is one option. A purchased domain or paid resource
needs separate approval.

A domain is not strictly required: Let's Encrypt now supports short-lived public
IP certificates with a compatible ACME client. Review the installed client,
challenge routing, renewal automation, IP stability and Nginx reload hooks first.
These certificates last six days, making reliable renewal essential.
[Official Certbot/IP certificate guidance](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html).
Do not run a standalone challenge that stops Nginx without downtime approval.
No certificate was requested and no DNS/TLS configuration changed here.

Acceptance requires a trusted matching certificate without `-k`, secure browser
requests/assets, HTTP-to-HTTPS redirects (with ACME exceptions as needed),
renewal rehearsal, correct proxy scheme and exact HTTPS CORS settings. Opening
443 in a security group alone does not configure TLS. Do not enter real
credentials or student data into the HTTP endpoint.

Also verify SSH restriction, JWT strength, database/environment permissions,
backups, restart behavior, disk/memory, dependency advisories and authentication
rate limiting. See the report for executed audits and their limits.

## Troubleshooting

| Symptom | Checks and next step |
| --- | --- |
| Root 200, API 502 | Service status/logs, loopback listener, backend directory/venv, Nginx upstream |
| Health 200, login/data 503 | JWT presence/length, effective database URL, permissions and migrations; liveness does not check them |
| `/api/ready` 404 | Compare server SHA/routes with this checkout before any update; currently observed |
| Login succeeds but API 401 | Token expiry, bearer headers, clock and signing-secret consistency; never log tokens |
| Deep route 404 | SPA `try_files`; do not apply SPA fallback to `/api/` |
| Browser API targets localhost | Build environment and `VITE_API_BASE_URL`; rebuild only after review |
| SQLite readonly/locked | Correct DB path, file/parent ownership, disk space, active writers; do not delete DB/WAL files |
| Service fails after setting production | Current production mode requires PostgreSQL; restore reviewed config, do not migrate implicitly |
| HTTPS refused | Listener, certificate, Nginx site and SG; public 443 ingress alone is insufficient |
| Service OOM/disk full | `free -h`, `df -h`, journal/kernel logs and log retention; do not resize or delete data without approval |
