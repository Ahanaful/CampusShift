# AWS Free Plan recovery (legacy filename)

The active target is the new AWS Free account plan, profile campusshift, us-east-1. This filename is retained for existing links; AWS Academy session resets and LabRole assumptions no longer apply. See [Stage A](aws-stage-a.md) and [deployment runbook](aws-deployment.md).

Resources normally persist across browser/CLI sessions. Temporary login expiration does not delete infrastructure. The Free Plan can close access when credits or plan time expire; retained RDS/S3/logs do not override account lifecycle rules. Do not upgrade or join Organizations without explicit approval. Store only fictional demonstration data, and keep verified protected backups outside the account.

## Before ending a demonstration

1. Record source revision, actual image/engine versions and non-secret stack outputs in private operator notes. Do not commit credentials, passfiles, JWT secrets, private keys or dumps.
2. Create a restricted PostgreSQL custom-format backup using database_backup.sh. Copy it to approved encrypted off-account storage, record a checksum and test an isolated restore. Dumps contain password hashes and attendance/audit records even with fictional identities.
3. Review actual credits/expiry with the Free Tier API and Console. Budget alerts must track gross consumption excluding credits. Account for EC2/RDS hours, EBS/storage, public IPv4, snapshots, S3 versions and optional logs. Alerting does not stop resources.
4. Stop/terminate/delete only after explicit approval and a verified backup. Storage continues while compute is stopped; inspect RDS automatic restart rules before relying on a stop for cost control. Do not confuse a stopped service or signed-out CLI with a billing stop.

## Recover a session or application

1. For expired credentials, run aws login --profile campusshift --region us-east-1 as the dedicated IAM identity. Rerun STS and read-only preflight; compare account/region. Never switch to root CLI or old Academy credentials.
2. Inspect surviving stacks and outputs before recreating anything. Confirm ownership/tags/account/region; do not launch duplicates or adopt/delete unfamiliar data. Read the actual current EC2 IP from outputs and update any operator-controlled DNS only after verification.
3. For a code failure, inspect systemd/journal/application logs and current symlink. Retain prior code releases. Switch back only after checking compatibility with the current schema; do not automatically downgrade published/archived history.
4. For data recovery, create a separately approved empty fictional database. Restore the trusted custom-format dump before running migrations or seeding that target. The restore tool refuses populated public schemas, uses a transaction and never invokes --clean. Update protected runtime configuration, run Alembic upgrade/check and validate original shift/publication/attendance links.
5. If resources were intentionally removed, rerun the Stage B permission/resource/HTTPS/cost review with current service availability and credit balance. Obtain explicit approval, then follow CloudFormation change-set deployment using fresh outputs, not old resource IDs.
6. Deliver protected credentials/trusted certificates through verified SSH and generate a new JWT secret if the old one is unavailable; that deliberately invalidates old tokens. Preserve existing configuration on ordinary updates.
7. For a clean demo, use the explicit synthetic fixture command. Never import real employee records into this demonstration environment. Rerun HTTPS, registration/roles, scheduling, time-off, publication, attendance/corrections, CSV, restart and restore checks; record actual results.

## Retention and cleanup

Current templates retain RDS, versioned S3 and optional logs. Stack deletion can still terminate EC2 and its root volume, so it is destructive and approval-gated. List retained resources/snapshots/versions afterward; they may continue consuming credits. Check exact account, region, tags, IDs and backup before removing any retained resource. Do not use account-wide deletion loops. RDS deletion protection is not permission to assume backup recovery will work.

An EC2-local PostgreSQL fallback lacks managed RDS backup/failover and competes with API memory; root-volume termination destroys its database. A retained EBS volume or snapshot still requires independent backup verification. Legacy SQLite installations in another account are historical and must not be mistaken for the new target or copied without a synthetic-data review.
