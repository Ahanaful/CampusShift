# CampusShift production rollout — November 13, 2026

Approved by the user. Existing EC2 architecture retained. No new AWS resources,
volume changes, production application record writes, commits or pushes.

## Live result

- URL: **https://3.133.115.154**. Publicly trusted Let's Encrypt IP certificate,
  valid until November 20 UTC. HTTP redirects to HTTPS; SPA and API routing remain.
- `/api/health` and `/api/ready`: 200 over HTTPS; unknown API path: JSON 404;
  unauthenticated protected reads: 401. TLS verification was not disabled.
- Nginx config test passed. Security headers include HSTS (one day), CSP,
  X-Content-Type-Options, X-Frame-Options and Referrer-Policy.
- Certbot 5.10.0 installed. Existing snap.certbot.renew.timer active; deploy hook
  validates/reloads Nginx. Renewal simulation including deploy hook passed.
  Custom candidate certbot timer was NOT installed, avoiding duplicate schedules.
- Backend active release: `/home/ubuntu/releases/campusshift/phase6e-61652acbf5f2`.
  Source archive SHA-256:
  `61652acbf5f22b0cb22881ea7594db2fb3ab1bd6df25d157fb3a72c9af5fd45d`.
  Based on GitHub target `1243fceb646b8fa1a9b8aa92021175aed0d1d9c2`, local merge
  `1fdf261d62353bb1c8eff8d66c489bf348ed9847` and reviewed local remediation.
  This is a source archive release, not a newly committed Git revision.
- Isolated Python 3.12.16 venv; pip check passed. A systemd drop-in switches
  WorkingDirectory, ExecStart and EnvironmentFile. Old checkout fc04a91 and venv
  remain intact. One approved backend restart occurred; readiness passed directly
  afterward. Static frontend assets were already current and remain unchanged.
- Original SQLite path preserved: `/home/ubuntu/CampusShift/backend/campusshift.db`.
  Absolute DATABASE_URL configured privately; signing settings preserved; APP_ENV
  remains unset. No migrations applied: version scripts/head unchanged.

## Backup and persistence evidence

- `campusshift-sqlite-backup.timer` active: daily 06:00 UTC plus jitter, keep 14
  successful snapshots. Python online backup API, private 0700 folder/0600 files;
  successful first run and separate temporary restore: integrity ok, schema
  `9e57ab896061`. Script installed outside release at
  `/home/ubuntu/.local/lib/campusshift/sqlite_backup.py`.
- Encrypted copies downloaded to ignored `.local/backups/campusshift-encrypted/`
  on the operator computer. AES-256-GCM with a fresh per-backup key wrapped using
  RSA-OAEP/SHA-256 and the existing cskey public key. Private key stays local.
  One encrypted backup was decrypted/restored separately and integrity/schema
  verified. A second fresh snapshot was copied after the switch.
- Local LaunchAgent `com.campusshift.backup-pull` runs hourly; first scheduled run
  exited 0. Keeps 30 encrypted copies; transfers only over strict-host-key SSH.
  Laptop must be awake, on an allowed administrator network, with key accessible.
  Backups are NOT continuously replicated to another AWS service.
- Decryption requires the original cskey private key. Preserve a protected recovery
  copy of that key separately; replacing/deleting it would prevent recovery of
  existing encrypted backups. No private key contents are in this repository.
- Existing DB after production restart: integrity ok, schema current; aggregate
  counts unchanged: 2 users, 1 department, 5 classes, 4 availability, 2 runs,
  1 assigned shift, 0 time-off and 0 attendance records. No fictional records were
  added to production. This verifies existing data survives the service restart,
  not reboot/termination recovery or every user workflow.

Encrypted recovery example (NEW destination only):

```sh
.local/backup-crypto/bin/python scripts/encrypted_backup.py restore \
  --backup /path/to/completed.sqlite3.enc \
  --identity /path/to/original/cskey.pem \
  --destination /private-recovery-directory/new.sqlite3
```

Local backup environment: `scripts/requirements-backup.txt`; do not add this
operator-only dependency to the backend environment.

## Tests and remaining limits

- Browser smoke check: HTTPS landing page rendered correctly, reported Backend connected, and no page errors were reported. Screenshot: `.local/production-https.png`. No authenticated browser session was used.

- Candidate tested on EC2 using fictional disposable fixtures: 79 application
  entries, 77 passed / 2 PostgreSQL-only skips; scheduler 15 passed.
- Earlier local full backend suite: 88 passed / 2 skipped. Remediation suite 11
  passed, including real local Uvicorn restart/restore; encryption tamper/wrong-key
  test passed. Public HTTPS acceptance script passed after switch.
- No successful authenticated live student/supervisor workflow was claimed:
  production credentials were not provided, and existing user data was preserved.
  Perform presentation rehearsal using authorized fictional accounts over HTTPS.
- EBS still unencrypted and delete-on-termination. No volume replacement,
  encryption migration or snapshot purchase was approved/performed.
- Billing remains AccessDenied; no claim that denied service inventories are empty.
  Existing EC2/EBS/public IPv4 continue; ordinary transfer/CPU surplus costs remain.
- Automatic IP can change after stop/start; then reissue/reconfigure the IP
  certificate and update URL/backup destination. Do not stop EC2 casually.
- Production-mode PostgreSQL guardrail, dependency advisory review, stronger
  service/file permissions and alerting remain follow-up security work.

## Rollback

Original service unit is unchanged; rollback copies of Nginx/service configuration
are under `/home/ubuntu/backups/phase6e-rollback` (private). For a backend rollback,
move ONLY `/etc/systemd/system/campusshift.service.d/phase6e.conf` out of the unit
directory, daemon-reload and restart campusshift. Original fc04a91 checkout/venv
and original environment resume against the same live database. No DB downgrade
or restore is performed. Verify health after rollback; older code lacks readiness.

Keep current functioning HTTPS during backend rollback. Restoring the historical
HTTP-only Nginx site is an emergency configuration rollback, not a secure login
fallback; HSTS persists in browsers for one day. No automatic database restore or
instance termination is a rollback step.
