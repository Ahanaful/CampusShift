# EC2 deployment and operations

For the verified Ubuntu/SQLite host, use the [EC2 remediation release plan](ec2-remediation.md).
The approved rollout is complete; see [production results](production-rollout.md).
The PostgreSQL/Amazon Linux installer is not an in-place updater.

**Use the existing CampusShift EC2 application.** Selected Region: `us-east-2` (Ohio); CLI profile: `campusshift`. Current URL, resource IDs, cost and cleanup evidence are in [current deployment](aws-current-deployment.md). The serverless attempt was removed; do not recreate it.

## Existing host

Nginx serves the frontend and proxies the API at https://3.133.115.154. The `CampusShift-Server` instance is running. The application and its data were preserved throughout teardown. SQLite at `/home/ubuntu/CampusShift/backend/campusshift.db` and systemd/Uvicorn are verified. The active release is `phase6e-61652acbf5f2`; the original Git checkout remains intact for rollback.

Trusted HTTPS and HTTP redirection are verified. `/api/health` and `/api/ready` return 200. The backup and certificate renewal timers are active; see rollout results for remaining acceptance limits.

Read-only infrastructure checks:

```bash
aws sts get-caller-identity --profile campusshift --region us-east-2
aws ec2 describe-instance-status --instance-ids i-0b662a28fc2d1aeaf --include-all-instances --profile campusshift --region us-east-2
curl --fail https://3.133.115.154/api/health
```

Use AWS Settings > View all projects > Overview > Additional Info > Region to confirm the selected Region. AWS Settings > Billing shows credit consumption. Keep the Free Plan and managed human role; no IAM team-member setup, Organizations changes, Advanced Features or CDK bootstrap is required.

## Future application updates

1. Inspect the existing host over authorized SSH using key `cskey` and verified host keys; its security group currently restricts SSH to the recorded operator IP. Identify Nginx's document root, the running backend/service, virtual environment, database path and deployed revision before writing anything.
2. Back up the application database and configuration using tools appropriate to the engine actually running. Keep secrets and backups out of Git. Verify the backup before schema or host changes.
3. Run the local backend/scheduler checks and frontend lint/build. Build with Node 22.13+ and an empty `VITE_API_BASE_URL` for same-origin `/api` requests.
4. Deploy a new source release while preserving the database and environment configuration. Apply reviewed Alembic migrations using the host's actual application environment. Never seed or downgrade a populated database automatically.
5. Install frontend assets before switching the HTML entry point; restart the actual backend service and check health, readiness when supported, login, scheduling and attendance. Keep a compatible previous release for rollback.

Exact host paths and service names must be recorded after inspection. Do not execute guessed paths or overwrite `.env`, database files or Nginx configuration. The root volume is delete-on-termination; do not terminate this instance as an application rollback. A stop/start can change its public IP.

## Repository tools

- `scripts/package_backend.py`: source-only EC2 release archive, excluding secrets, databases and tests.
- `scripts/configure_server.py` and `scripts/deploy_backend.sh`: prepared **new Amazon Linux** installation with PostgreSQL/TLS/systemd. The current Nginx response reports Ubuntu; these scripts are not a verified in-place updater for it.
- `scripts/database_backup.sh`: explicit PostgreSQL dump/empty-target restore helper; use only after confirming PostgreSQL and private connection settings.
- `scripts/verify_deployment.py`: HTTPS acceptance checks and optional fictional-account login checks. It intentionally rejects HTTP and has not been claimed to pass against the current HTTP URL.
- `scripts/aws_deploy.py`: profile-safe discovery, local cost plan and explicitly approved optional EC2/frontend CloudFormation operations. It has no Lambda deployment commands.

`infrastructure/platform.json` and `frontend.json` remain optional preparation templates for a new EC2/RDS or S3/CloudFront topology. They do not describe or manage the existing manual EC2 deployment. Do not execute them to update this server. Adding RDS, CloudFront, domains, backups or other billable resources requires a separate requested change.

See [architecture](aws-architecture.md), [profile setup](aws-profile-setup.md) and [troubleshooting](aws-troubleshooting.md). Historical service research is summarized in [serverless attempt history](aws-serverless-deployment.md).
