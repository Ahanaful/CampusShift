> **Historical proposal, not the existing deployment runbook.** The current target
> is the existing Ubuntu EC2/SQLite application. Use [its runbook](aws-deployment.md).
> The account/region/blocker claims below are dated preparation notes. No resource
> creation or application of this Amazon Linux/PostgreSQL configuration is authorized.

# Phase 6 deployment runbook ? AWS Free Plan

> **Project correction:** use assigned us-east-2 and existing AWS-managed human access. Prior us-east-1 policy-blocker/Console-user prerequisites below are superseded; both main templates passed live validation in Ohio. Read [the corrected decision](aws-project-free-plan-decision.md). EC2 runtime steps remain a proposed alternative after approval; the Lambda/Aurora option is not implemented here. Do not activate Advanced Features or change policies.

No CampusShift resources are confirmed in the new Free Plan account. Historical Academy/Ubuntu deployment references do not belong to this target. Use this runbook only after the Stage A/B gates in [aws-stage-a.md](aws-stage-a.md); do not run the Amazon Linux installer on an old Ubuntu server. No production records are migrated, no commit/push is performed and no creation/deletion command is executed automatically.

## Current Stage A blocker

Authenticated preflight returned an ACTIVE FREE plan/$100, but an organization SCP explicitly denies EC2/RDS/SSM/CloudFormation reads, including template validation. The current login is a broad AccountFullAccessRole. Do not proceed with this runbook until the intended account is confirmed, its authorized organization owner resolves/reviews the policy, and the scoped deployment identity/Stage B plan is approved. No additional IAM permission overrides an SCP deny.

## Prerequisites and approval gate

Start with [the dedicated IAM profile setup](aws-profile-setup.md) and [Stage A evidence/resource/cost review](aws-stage-a.md). Region is us-east-1 and profile is campusshift. No Organizations, account upgrade, broad admin permissions or CDK bootstrap is needed. Stage A/B are preparation/review only. The existing templates still require a trusted public API hostname/certificate; the no-domain VPC-origin alternative is not implemented in these templates.

Use Git, Python 3.11+ on the operator workstation, Node 22.13+, AWS CLI v2, SSH/SCP with host-key verification, the dedicated non-root campusshift browser-login profile with temporary credentials, an existing authorized VPC/public subnet/two private subnets in different AZs, a key pair and operator `/32`. Check actual RDS engine/class availability and network routes. An instance profile is optional for base SSH/passfile deployment. The scoped CloudWatch-only role/profile template can be created only after separate approval; do not reuse any Academy LabRole.

Read `aws-architecture.md` for the proposed resource list, ongoing usage and remaining permission checks. Obtain explicit approval for those resources/costs before using `--approve-costs`. This flag records the operator's already-granted approval; it does not grant permission by itself. `--expected-account` prevents accidental writes to another account. There is no unattended cleanup. Export only temporary credentials through the dedicated IAM browser login through your approved AWS session workflow; never paste them into source or a command shared with others.

Run commands from repository root. On Windows use `backend/.venv/Scripts/python.exe` in place of `python`; on Mac/Linux use your virtual environment's Python.

```bash
python -m pip install -r scripts/requirements-infrastructure.txt
python scripts/aws_deploy.py --profile campusshift --region us-east-1 discover
cfn-lint infrastructure/platform.json infrastructure/frontend.json
python scripts/aws_deploy.py --profile campusshift --region us-east-1 validate platform
python scripts/aws_deploy.py --profile campusshift --region us-east-1 validate frontend
```

These checks do not create resources. Do not interpret read access or local lint as create authorization or account-specific Free Plan feature eligibility. If AWS CLI/credentials are absent, stop the AWS portion and use local tests; do not claim cloud verification.

For RDS, an approved operator must create a standard SSM **SecureString** containing a strong database master password using the AWS console's protected value input, under the chosen environment-specific path, and note its version. Do this only after resource/secret approval. Do not use a plaintext String, put the value in template parameters/CLI history or print `get-parameter --with-decryption` output. CloudFormation needs permission to resolve this parameter and decrypt its key. If unavailable, treat RDS provisioning as blocked; use the documented local-PostgreSQL fallback only after its own review. Dynamic references do not automatically rotate an existing database password; coordinate rotations explicitly.

## Platform change set

Copy `infrastructure/platform.parameters.example.json` to ignored `infrastructure/platform.parameters.local.json`; replace all placeholders using discovery. Select the region through CLI. The DatabaseEngineVersion parameter requires a supported PostgreSQL 16 minor from preflight; do not guess its regional availability. The reviewed EC2/DB sizes are t3.micro/db.t3.micro; larger types require a new cost review. EC2 uses Standard CPU credits to avoid Unlimited surplus charges; RDS extended-support enrollment and Performance Insights are disabled. The AMI resolves from the regional Amazon Linux 2023 public SSM parameter; record its resolved AMI ID in your deployment record. Recreating from that alias gets patched images, not a bit-identical old image.

```bash
# Only after explicit resource/cost approval:
python scripts/aws_deploy.py --profile campusshift --region us-east-1 change-set platform campusshift-platform infrastructure/platform.parameters.local.json --expected-account VERIFIED_ACCOUNT_ID --approve-costs
aws --profile campusshift --region us-east-1 cloudformation describe-change-set --stack-name campusshift-platform --change-set-name RETURNED_CHANGE_SET
# Review all changes and underlying permissions before executing:
python scripts/aws_deploy.py --profile campusshift --region us-east-1 execute campusshift-platform RETURNED_CHANGE_SET --expected-account VERIFIED_ACCOUNT_ID --approve-costs
aws --profile campusshift --region us-east-1 cloudformation describe-stack-events --stack-name campusshift-platform
python scripts/aws_deploy.py --profile campusshift --region us-east-1 outputs campusshift-platform
```

For updates use `--type UPDATE` to create a new reviewable change set. The executor refuses removals or possible replacements; those require separately approved operator review in AWS. Re-running a completed create is not an update: inspect stack status first. Stack creation failures are visible in events. No script retries with wider permissions. The template creates no IAM resources and does not pass `CAPABILITY_IAM`.

Outputs supply instance ID/public IP, RDS endpoint/port/name/user and optional log group; do not hardcode them in source. Confirm `cloud-init status --wait` on the new EC2 host and review `/var/log/cloud-init-output.log` before continuing. User-data installs Amazon Linux Python 3.11/Nginx and creates a non-login application user; it contains no secrets and does not start authentication endpoints. Verify actual package availability rather than assuming bootstrap success.

## Origin TLS, database account and secret delivery

Map your operator-controlled API DNS name to the returned EC2 IP. Obtain a publicly trusted certificate matching that name using your approved DNS validation process. The runbook cannot create a domain/certificate for you. CloudFront's default HTTPS domain does not remove this prerequisite. If no domain/trusted certificate is available, stop before exposing authentication publicly.

Transfer the certificate, chain, private key and official regional/global RDS CA bundle through SCP over verified SSH. Install into `/etc/campusshift/tls/fullchain.pem`, `/etc/campusshift/tls/privkey.pem` (root:root 0600 for key, directory 0700) and `/etc/campusshift/rds-ca.pem` (0644). Obtain CA bundle from [AWS RDS certificate documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html); do not disable TLS verification to fix connectivity. Certificate issuance/renewal and DNS changes are external operator steps, not automated provisioning. Protect temporary transfer files and remove them after installation. Do not put certificates' private keys in Git or user-data.

Connect to RDS only from the backend host or a verified SSH tunnel, with libpq `sslmode=verify-full`. Use a PostgreSQL client matching the RDS major version and an interactive password prompt, never a password argument. Create a dedicated application login/database for the demo. Example inside interactive `psql` as the master user:

```sql
CREATE ROLE campusshift_app LOGIN;
\password campusshift_app
CREATE DATABASE campusshift_app OWNER campusshift_app;
```

Run those statements only for a fresh setup; first inspect existing roles/databases on repeat deployments. The `\password` prompt keeps the password out of SQL history. This owner role can run the application's migrations without RDS superuser rights. Do not put a master login into the API service. `DatabaseName` from the template is the initial admin database; use `campusshift_app` in runtime configuration after creating the dedicated database. A future migration-only role would further narrow runtime DDL privileges.

## Package and deploy the backend

```bash
python scripts/package_backend.py
scp -i PATH_TO_KEY .local/campusshift-backend.tar.gz ec2-user@STACK_BACKEND_IP:/tmp/campusshift-backend.tar.gz
scp -i PATH_TO_KEY scripts/configure_server.py scripts/deploy_backend.sh ec2-user@STACK_BACKEND_IP:/tmp/
```

On the **new** Amazon Linux host, extract the source archive into a temporary operator directory so the configuration script can find the Nginx template. This archive contains allowlisted source only, no `.env`, database, Git history, frontend dependencies or private keys.

```bash
mkdir -p "$HOME/campusshift-setup"
tar -xzf /tmp/campusshift-backend.tar.gz -C "$HOME/campusshift-setup"
sudo python3.11 "$HOME/campusshift-setup/scripts/configure_server.py"
sudo bash /tmp/deploy_backend.sh /tmp/campusshift-backend.tar.gz RELEASE_ID
sudo systemctl status campusshift.service --no-pager
curl --fail http://127.0.0.1:8000/api/ready
```

`RELEASE_ID` must be a new simple identifier (for example a Git short SHA plus build suffix); existing release directories are never overwritten. Configuration prompts privately for the dedicated app DB password, generates a JWT signing secret, creates a campusshift-owned 0600 libpq passfile, and a root:campusshift 0640 service environment. It refuses existing configuration; preserve it on updates. No secret is passed to AWS, SSH, pip, psql or Uvicorn in command arguments. Do not run with shell tracing. The source package and all releases are root-owned/non-writable by the application user.

Installer uses pinned direct Python requirements, the pure scheduler package, Alembic upgrade/check, an atomic `current` symlink, non-root systemd Uvicorn with two workers (no reload) and TLS Nginx. It leaves prior code releases in place. Failed migrations stop deployment; no schema downgrade or data deletion is attempted. If readiness fails after switching, inspect logs and deliberately roll back the symlink only if old code supports the current schema. Do not blindly downgrade a database containing published history.

Amazon Linux's vendor Nginx package can include a default port-80 server. Our template never permits inbound 80, but remove/disable that vendor default before considering origin setup complete. If SELinux is enforcing, use the distribution's approved `httpd_can_network_connect` policy for loopback proxying; do not disable SELinux. Confirm permissions with `nginx -t`, `ss -lntp`, and local TLS validation. From an SSH session, test SNI/hostname and the full trust chain without opening an administrator HTTPS exception:

```bash
curl --fail --resolve YOUR_API_DOMAIN:443:127.0.0.1 https://YOUR_API_DOMAIN/api/ready
```

`configure_server.py` requires Linux/POSIX. `APP_ENV=production` rejects SQLite, weak signing secrets and HTTP/wildcard CORS origins. `/api/health` remains liveness only; `/api/ready` checks a migrated database at the expected revision. API documentation routes are disabled in production.

Required runtime variables are `APP_ENV=production`, password-free `DATABASE_URL=postgresql+psycopg://USER@RDS_HOST:5432/DATABASE?sslmode=verify-full&sslrootcert=/etc/campusshift/rds-ca.pem&connect_timeout=5`, `PGPASSFILE`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES=30`, and `CORS_ORIGINS=` for same-origin CloudFront. Attendance policy variables remain optional with existing defaults. Never place secrets in frontend variables. Do not print environment files when debugging.

## Synthetic demonstration data

Run explicitly on the backend host from `/opt/campusshift/current/backend`, as the service user with its protected environment loaded. This creates only fictional example.com identities in the isolated Scheduling Demo department. It preserves existing accounts/passwords and published versions. Historical attendance is visibly synthetic and is inserted through the audited correction workflow, not fake clock endpoint timestamps.

```bash
sudo bash -c 'set -a; source /etc/campusshift/application.env; set +a; cd /opt/campusshift/current/backend; exec sudo --preserve-env=APP_ENV,DATABASE_URL,JWT_SECRET,CORS_ORIGINS,PGPASSFILE -u campusshift ../.venv/bin/python -m app.seed_cloud_demo --synthetic-demo'
```

The command prompts privately for NEW account passwords, creates several students, supervisor, classes, availability, eligibility/staffing, generates/publishes a completed prior week and adds up to two corrected attendance records with audit history. Repeating the same week avoids duplicate schedules/attendance and never resets passwords. Optional `--week-start YYYY-MM-DD` must be a completed Monday week. Existing local-only seed commands retain their SQLite safety restriction. To demonstrate live clock actions, create/publish an eligible current-time shift through the UI and use real server time as described in the root README.

## Frontend and CloudFront

Only after origin TLS is verified, fill ignored `infrastructure/frontend.parameters.local.json` using the example with your API DNS name. Then review and execute a separate approved frontend change set:

```bash
python scripts/aws_deploy.py --profile campusshift --region us-east-1 change-set frontend campusshift-frontend infrastructure/frontend.parameters.local.json --expected-account VERIFIED_ACCOUNT_ID --approve-costs
aws --profile campusshift --region us-east-1 cloudformation describe-change-set --stack-name campusshift-frontend --change-set-name RETURNED_CHANGE_SET
python scripts/aws_deploy.py --profile campusshift --region us-east-1 execute campusshift-frontend RETURNED_CHANGE_SET --expected-account VERIFIED_ACCOUNT_ID --approve-costs
python scripts/aws_deploy.py --profile campusshift --region us-east-1 outputs campusshift-frontend
python scripts/aws_deploy.py --profile campusshift --region us-east-1 upload-frontend campusshift-frontend --expected-account VERIFIED_ACCOUNT_ID --approve-costs
```

The upload runs npm ci/build with a blank public API origin, uploads hashed assets first and index last, and invalidates `/index.html` and `/`. It never deletes old object versions/assets. Wait for distribution status Deployed before testing. Private S3 is accessed through OAC; do not enable website hosting/public bucket access to resolve 403s. CloudFront default HTTPS certificate needs no custom viewer domain. All SPA deep links rewrite to index except `/api` paths, which retain real error responses. API caching and error TTLs are zero; Authorization and queries are forwarded. Same-origin access avoids production CORS complexity.

## PostgreSQL migration, fallback and backups

Run the full migration chain against a **fresh synthetic** PostgreSQL database; it already supports native PostgreSQL ALTER statements. Existing Boolean defaults are quoted values PostgreSQL accepts, and partial index predicates specify both dialects. No new schema revision was needed. PostgreSQL does not use SQLite PRAGMA/batch-rebuild behavior. The local integration harness verifies upgrade/downgrade/re-upgrade, metadata consistency, seed repetition, publication/attendance and concurrency. It does not transfer SQLite rows. If fictional SQLite fixtures must be retained, export/reseed intentionally after an explicit schema-aware conversion review; no automatic cross-database copy tool is provided for personal records.

If RDS or SSM dynamic references are blocked, use PostgreSQL on the same EC2 only as an approved Free Plan demo fallback: create the platform with `CreateDatabase=false`, install the supported PostgreSQL server/client packages for that Amazon Linux release, initialize a new database volume, enable its service, keep `listen_addresses='127.0.0.1'`, require SCRAM password auth in pg_hba.conf, and create the dedicated app user/database with interactive `\password`. Do not initialize over an existing data directory. Run configure_server.py with `--local-postgres`; this permits unencrypted **loopback only** DB transport, not a public database endpoint. No 5432 inbound rule is needed. Package names/service initialization should be verified on the selected AMI before changes. This fallback is a documented operator procedure, not an automatically tested installer. For multi-user deployment do not fall back to SQLite: its file storage, single writer, backups and instance lifecycle are unsuitable as the target architecture.

EC2-local PostgreSQL competes with API workers for micro-instance memory, has no RDS-managed backup/failover, and its default root EBS volume is deleted on termination. Back up fictional data outside the instance before termination, intentional teardown or Free Plan expiration. A separate retained EBS volume is possible only after a further resource/cost review. RDS and other resources normally persist across sessions until stopped/deleted or the account lifecycle ends. Free Plan credit/time expiry can close access; retain verified backups outside the account.

Install a PostgreSQL client matching the server major version. Use scripts/database_backup.sh as campusshift with `PGHOST`, `PGUSER`, `PGDATABASE`, `PGPASSFILE`, `PGSSLMODE=verify-full`, `PGSSLROOTCERT` set (loopback fallback uses `PGSSLMODE=disable`).

```bash
bash scripts/database_backup.sh backup /APPROVED_PRIVATE_DIRECTORY/demo.dump
# Copy the dump to approved encrypted storage outside the AWS account; never Git.
# Restore only into a newly created empty fictional database, after approval:
bash scripts/database_backup.sh restore /APPROVED_PRIVATE_DIRECTORY/demo.dump --approve-empty-target-restore
```

Backup refuses overwriting a file; restore refuses populated public schemas and never uses `--clean`. pg_restore is transactional and exits on errors. A dump contains password hashes and attendance data even when fictional: restrict access, encrypt at rest/in transfer, establish retention and verify a restore to an isolated empty database. Restore requires a reviewed trusted dump; do not restore untrusted SQL. RDS automated retention is one day, single AZ, encrypted, with enhanced monitoring off. RDS/logs/S3 have Retain policies; cleanup is explicit.

## Monitoring and deployed acceptance

JSON application logs omit request bodies, headers, queries, raw paths and exception details. Auth failures have no email/password; scheduling failures identify department only. Nginx access logs are off; error logs are local. Logrotate retains seven copies with a size threshold. A permitted existing profile can optionally send application.log via the provided CloudWatch agent configuration. Install the official agent, replace `__LOG_GROUP__` with stack output and start it using its supported control command only after confirming log-stream/create/put permissions. No IAM policy or role is attached automatically. If unavailable, collect protected local logs via SSH and report CloudWatch as blocked.

```bash
sudo journalctl -u campusshift.service -n 100 --no-pager
sudo tail -n 100 /var/log/campusshift/application.log
sudo tail -n 100 /var/log/nginx/campusshift-error.log
python scripts/verify_deployment.py HTTPS_APPLICATION_URL --accounts
```

Run this acceptance checklist on fictional data and record actual results; none is claimed as AWS-verified yet:

- Verify HTTPS trust/HSTS, HTTP rejection, origin certificate validation, denied public origin 8000/5432, private S3, no caching of user-specific API/CSV responses, deep-route refresh and API errors remaining JSON.
- Register a synthetic student into the demo department; log in separately as student and seeded supervisor. Verify 401 without tokens, 403 for wrong roles and cross-department/ownership denial with a second isolated demo department if available.
- Create/edit/delete a class and availability; verify overlap rejection and class conflict warning.
- Create staffing/location eligibility; generate a week, approve time off, regenerate and confirm absence; manually edit, publish, replace and confirm archived versions and student-only official assignments.
- Publish an eligible current-time shift; clock in/out using real server time. Verify duplicate/multiple-active rejection, late/missed indicators, correction approval/rejection/audit and supervisor-only filtered CSV.
- Restart the service, verify migrated data still exists, and inspect readiness/logs; after separate reboot approval, reboot EC2, rediscover its IP/update DNS if needed, verify service auto-start and the same records.
- Create/verify a protected dump, restore into an isolated empty database and compare fixture counts/audit/history. Exercise full recreation in a separately approved fresh environment using stack outputs, not remembered IPs.
- Check UI buttons/forms, responsive layouts, filters, expiration and CSV downloads in a real browser. Script/build/API checks do not establish browser QA.

## Safe teardown (only after explicit destructive approval)

First record stack outputs, take/verify an off-account fictional-data backup and list retained resources. Review costs of retaining them. Delete the frontend stack with `aws --profile campusshift --region us-east-1 cloudformation delete-stack --stack-name campusshift-frontend`; CloudFormation removes the distribution but retains the versioned bucket. Delete the platform stack with the analogous command **only after approval**: it terminates EC2 and its root volume, while the protected RDS and optional log group are retained. These are destructive commands, not automatic cleanup steps. Do not run them against the legacy deployment.

After distribution deletion completes, an authorized operator must separately review whether to empty/delete S3 object versions and delete markers, remove retained log groups/SSM parameters, and disable RDS deletion protection for final database deletion with a chosen final snapshot. Example inspection commands are `aws s3api list-object-versions --bucket RETURNED_BUCKET` and `aws rds describe-db-instances`; do not use broad account-wide deletion loops. RDS/snapshots/bucket versions continue consuming storage until explicitly removed. Before deleting any retained resource, verify its account, region, tags, exact ID and backup. No deletion script bypasses these reviews.
