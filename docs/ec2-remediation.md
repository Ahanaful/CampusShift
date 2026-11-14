# EC2 remediation — release plan and completed rollout

**Status update:** The user approved and completed the rollout. See [production results](production-rollout.md). The plan below is the preserved pre-deployment review, not the current deployment status.

Originally prepared November 13, 2026 (America/Chicago). At preparation, no production changes, certificate
issuance, service restarts, resource changes, commits or pushes performed.
Target stays Ubuntu EC2 i-0b662a28fc2d1aeaf in us-east-2 with SQLite on EBS.

## Implemented locally

- `scripts/sqlite_backup.py`: Python standard-library SQLite online backup API,
  read-only source, bounded backup time, integrity checks, atomic no-overwrite
  publication, 0600 files in owner-only 0700 directories. Completed snapshots only
  are pruned after a successful backup. Uses an advisory lock for concurrent runs.
- `backup` keeps the last 14 successful snapshots by default (about 14 days with
  one daily run; additional manual runs shorten the time span). WAL contents are
  captured by SQLite; never copy an active DB file with cp/scp.
- `restore` always creates a NEW file, checks integrity and refuses to replace any
  existing target or symlink. No automatic production restore exists.
- `pull` reads the newest completed backup over existing strict-host-key SSH,
  verifies its SHA-256 and SQLite integrity, and keeps 30 local copies by default.
  It never triggers a remote backup or mutates the server. Transfer errors are
  sanitized; SSH credentials are not printed or embedded in configuration.
- Daily Ubuntu backup service/timer candidates are under `infrastructure/runtime/`.
  The script is installed to a stable path separate from release directories.
- macOS launchd example polls for the newest completed backup hourly while the
  computer is awake. Replace its placeholders before use; it is not installed.
- Existing HTTPS verifier accepts exact-origin/path HTTPS redirects as well as
  HTTP rejection; it no longer requires CloudFront's HTTP policy.
- Source packaging includes SQLite tooling and timer files. PostgreSQL tooling
  remains separate and must not be used against this database.

## Backup deployment and off-server recovery

**Only after production approval:** create `/home/ubuntu/backups/campusshift`
owned by ubuntu with mode 0700 and `/home/ubuntu/.local/lib/campusshift`; install
`sqlite_backup.py` there and install the backup service/timer into systemd. Review
unit paths, run `systemd-analyze verify` on Ubuntu, perform one manual snapshot,
verify it, restore it into a NEW private temporary directory and compare schema
revision and selected aggregate counts. Then enable the daily timer.

Example operator commands, not executed against production:

```sh
python3 /home/ubuntu/.local/lib/campusshift/sqlite_backup.py backup \
  --database /home/ubuntu/CampusShift/backend/campusshift.db \
  --directory /home/ubuntu/backups/campusshift --keep 14
python3 /home/ubuntu/.local/lib/campusshift/sqlite_backup.py verify /path/to/completed.sqlite3
python3 /home/ubuntu/.local/lib/campusshift/sqlite_backup.py restore \
  --backup /path/to/completed.sqlite3 --destination /private-recovery-dir/new.sqlite3
```

Simplest off-server destination without adding AWS storage: this existing computer,
using an owner-only folder such as `.local/backups/campusshift` under this checkout
(already ignored). This is a recommendation, not a configured destination. Confirm
whole-disk encryption/protected storage before transferring potentially sensitive
records; the local FileVault status command did not establish encryption here.
Only this machine holds the private SSH key. Existing known_hosts verification is
required; do not use StrictHostKeyChecking=no or widen the SSH security group.
Pull must run from a network matching the existing allowed administrator /32.

After remote backups exist and destination is approved, run locally:

```sh
.venv/bin/python scripts/sqlite_backup.py pull \
  --host ubuntu@3.133.115.154 \
  --identity /Users/shehransalam/Downloads/cskey.pem \
  --directory .local/backups/campusshift --keep 30
```

Copy the reviewed, substituted launchd example into the user's LaunchAgents only
after approval, then bootstrap it. Python/script/key/destination arguments must be
absolute paths; XML-escape special characters. No passwords appear in the plist.
A sleeping/offline laptop or changed administrator IP prevents off-server copies;
check the last successful copy daily. This is not an always-on managed backup.

Costs: 14 local snapshots use existing EBS free capacity (currently ~15 GiB free);
30 off-server copies consume laptop storage. No additional AWS resource is needed.
Ordinary outbound data transfer can still incur usage charges. This is not a
claim of zero transfer charges. Keep data private and inspect backup timer failures
in journald; off-server/expiry monitoring is still an operational responsibility.
An additional EBS volume or snapshot remains within AWS and costs storage; neither
is a free off-instance substitute. No S3 bucket or snapshot was created.

Restore procedure: verify source backup; restore into a separate 0700 directory;
verify integrity, expected Alembic revision and aggregate counts; start a disposable
application against that file to verify readiness/login and a fictional fixture.
NEVER point a test instance at the live database. For actual disaster recovery,
obtain maintenance approval, preserve the failed DB/WAL/SHM and existing writes,
stop the app, select the validated replacement file explicitly, verify ownership/
permissions, update the service database path and restart. Recovery loses writes
newer than the snapshot. No code rollback automatically restores a database.

## Backend release review and rollback

- Host checkout: clean `fc04a91d4a6e5790b2b392409d00e4a5ef99b636`.
- GitHub target observed: `1243fceb646b8fa1a9b8aa92021175aed0d1d9c2`.
- Local merge base: `1fdf261d62353bb1c8eff8d66c489bf348ed9847`, plus these uncommitted
  remediation files. The generated source archive's SHA-256 is the candidate
  identifier, not a claim that local changes are committed on GitHub.
- Reviewed changes include readiness, safe request logging, settings validation,
  DB session/transaction support, PostgreSQL compatibility and installer tooling.
  `backend/requirements.txt` adds psycopg[binary] 3.2.9; it is not a request to
  migrate SQLite. No Lambda components are restored.
- No Alembic version scripts differ from fc04a91; only migration env.py changes.
  Live DB revision already equals `9e57ab896061`; no upgrade/downgrade is needed
  for this candidate. Do not run destructive migrations or demo seeds.
- Latest main.py already implements `/api/ready`; missing schema/table returns
  sanitized 503, migrated DB returns 200 and Cache-Control: no-store. Local tests
  verify this; deployed backend remains unchanged and still returns 404.
- Existing static JS/CSS already match the current source build. Preserve assets
  for this backend-only release, avoiding an unnecessary frontend replacement.

Concrete release plan, **approval required**:

1. Deploy the backup tooling/timer; create, verify and pull a snapshot; rehearse
   restore before changing backend. Also retain private copies of existing service
   configuration and old code. Never include environment secrets in an archive
   intended for Git/sharing.
2. Upload the SHA-256 verified source-only archive into a NEW directory under
   `/home/ubuntu/releases/campusshift/`. Do not extract over the running checkout.
   Create an isolated venv using the verified Python 3.12 interpreter; install
   pinned requirements and the scheduler package. This avoids altering the old
   venv, which is required for rollback. Package installation needs network access.
3. Copy the existing backend environment file to a private runtime env (0600),
   changing only DATABASE_URL to the absolute existing SQLite file and preserving
   signing key/settings. An absolute URL is essential because relative paths are
   resolved under the new release directory. Do not display the copied file.
   Preserve APP_ENV unchanged: current repository production mode refuses SQLite;
   flipping it is not part of this release. That limitation remains documented.
4. Prepare a systemd drop-in resetting WorkingDirectory, ExecStart and
   EnvironmentFile to the new release/venv/private runtime env. Reset the old
   EnvironmentFile list before specifying the new one. Retain original unit and
   rollback drop-in. Verify source compilation/dependencies/schema compatibility
   before the switch. Do not run the prepared Amazon Linux/PostgreSQL installer.
5. In an approved brief maintenance window, daemon-reload and restart only
   campusshift. Nginx continues serving static frontend, but API requests can fail
   briefly. Verify loopback/public health and readiness, DB path/revision, service
   state and protected-route behavior. No live fixture writes unless separately
   authorized. Complete fictional workflow rehearsal after secure access exists.
6. Rollback on failed startup/readiness/auth checks: remove/revert ONLY the new
   drop-in, daemon-reload and restart campusshift with old checkout/venv/env. Keep
   the same live DB, old code and static files. No downgrade or DB restore: no
   migration versions changed. Validate health and existing read workflows.
   Rollback procedure is rehearsed conceptually and local process persistence is
   tested; the actual production switch/rollback remains unexecuted.

`python scripts/package_backend.py` reuses the source allowlist, excludes .env,
databases and tests, and produces `.local/campusshift-backend.tar.gz`. Candidate
hash/contents are recorded in `.local/phase6e-release-manifest.json`. Rebuild and
review the manifest if any source changes before deployment. Nothing is committed
or pushed automatically.

## Free trusted HTTPS on the existing IP

No domain/DNS access is configured. A domain purchase is **not required**:
[Let's Encrypt's official IP-certificate guidance](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)
supports Certbot 5.4+ webroot issuance using the shortlived profile (six-day
certificates). Certbot is not installed on this host; snap is available. No
certificate has been requested. The existing public IP is automatic and may change
on stop/start, requiring new issuance/configuration; no Elastic IP is created.

After approval:

1. Preserve current Nginx site/config; install a verified Certbot >=5.4 (e.g.
   supported snap package) and choose one renewal mechanism, avoiding duplicate
   timers. Record current IP from EC2 before issuance.
2. Add only the HTTP ACME location below to existing port-80 server; create the
   challenge directory; nginx -t and graceful reload. Preserve the current SPA/API
   paths while obtaining the certificate. Webroot validation does not require
   stopping Nginx.

```nginx
location ^~ /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
    default_type text/plain;
    try_files $uri =404;
}
```

3. Obtain a publicly trusted IP certificate using webroot, shortlived profile and
   the observed IP. Operator must approve ACME registration/terms and optionally
   provide an expiry-notice email. Example (only after approval):

```sh
sudo /snap/bin/certbot certonly --webroot --webroot-path /var/www/letsencrypt \
  --preferred-profile shortlived --ip-address 3.133.115.154
```

Confirm resulting certificate paths with `certbot certificates` and adjust the
candidate if needed. Never serve a staging or self-signed certificate publicly.

4. Review `infrastructure/runtime/nginx-ec2-ip-https.conf`, run nginx -t on Ubuntu
   with real certificate files, then graceful reload. It preserves SPA/proxy,
   redirects HTTP to a fixed HTTPS IP and adds security headers; ACME path stays
   reachable by HTTP. Port 8000 stays loopback; current SG already permits 443,
   so no SG update is planned. CSP must be verified in an actual browser.
5. Enable existing package renewal or the prepared twice-daily certbot timer with
   nginx test/reload deploy hook (not both). Run certbot renew --dry-run, verify
   timer execution and certificate expiry. Six-day lifetime makes unattended
   renewal and failure monitoring essential. Validate trust with normal TLS checks,
   never -k. Run verify_deployment.py over HTTPS with authorized fictional accounts;
   confirm browser auth uses the HTTPS origin and there is no mixed content.
6. Rollback config from the saved site, nginx -t, graceful reload. Certificate
   files may remain private; do not delete keys as part of config rollback. Short
   HSTS can keep browsers on HTTPS for a day, so preserve functioning HTTPS during
   incident recovery rather than treating HTTP as an authenticated fallback.

No new AWS service or domain charge is planned. Package downloads and normal
transfer usage remain possible. Certificate issuance/config testing is blocked on
production approval, not on purchasing a domain. Nginx/systemd candidate syntax
has not been executed by local Linux validators (not installed here); on-host
validation is an explicit gate before activation.

## EBS and cost review

Fresh EBS read: 20 GiB gp3, Encrypted=false, DeleteOnTermination=true. Prior scoped
inventory found no account-owned snapshots in Ohio, extra volumes, NAT Gateways,
Elastic IPs, VPC endpoints or load balancers. CPU credits are Unlimited.

Safest sequence: verify off-instance SQLite restore first; obtain approval for a
retained snapshot and any storage charges; if encryption is required, copy the
snapshot encrypted and create an encrypted replacement volume in the SAME AZ;
plan maintenance, validate boot/filesystem/application and retain the original
volume for rollback. Root-volume detach/attach requires an approved stop window;
the automatic public IP/certificate can change. Snapshot consistency for SQLite
must be coordinated with the application, or use the validated SQLite snapshot
for application recovery. No live-volume encryption-in-place is proposed. Review
DeleteOnTermination separately; disabling it requires approval and does not replace
backups. This task does not replace, detach, encrypt or terminate any resource.

Fresh Cost Explorer query is AccessDenied for ce:GetCostAndUsage. The read-only
identity cannot complete billing or previous denied service inventories. Existing
docs estimate ~$12.84/month before credits/variable costs; this is not actual spend.
Use existing authorized AWS Settings > Billing access to confirm credits, CPU
surplus, transfer and any future snapshot costs; no paid resource is created here.

## Validation and outstanding acceptance

- 11 remediation tests: WAL/committed-data backup, retention, permissions,
  no-overwrite/symlink protection, missing/corrupt/empty inputs, timeout cleanup,
  tampered-download rejection, HTTP downgrade/cross-origin rejection, actual local
  Uvicorn registration/login/class persistence across restart and restored DB.
  SSH pull transport test is mocked; no production backup was downloaded.
- Full backend suite: 90 entries, 88 passed, 2 PostgreSQL-only skips. Covers
  fictional student/supervisor auth, role/department isolation, class/availability,
  generation/draft editing/publication, time off and attendance/corrections.
- Scheduler: 15 passed. Existing frontend lint/build passed during the preceding
  audit; no frontend source changed in remediation.
- Production readiness/HTTPS, production timer, off-server transfer and host
  restart/restore acceptance are NOT complete. No production credentials or data
  used in the local tests. No live DB was overwritten or service restarted.
