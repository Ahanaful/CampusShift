# EC2 and local-development tools

Use the existing EC2 deployment, profile `campusshift` and selected Region `us-east-2`. The serverless attempt was removed. [Current status](../docs/aws-current-deployment.md) and [EC2 operations](../docs/aws-deployment.md) describe what is verified.

| Tool | Purpose |
| --- | --- |
| `aws_deploy.py` | Named-profile read-only preflight/diagnostics, offline EC2 cost plan, template validation/outputs and explicitly approved optional EC2/frontend change sets/uploads |
| `package_backend.py` | Source-only EC2 archive in ignored `.local/`, excluding secrets/databases/tests |
| `configure_server.py` | Interactive configuration for a new Linux/PostgreSQL/TLS setup; refuses existing configuration |
| `deploy_backend.sh` | New Amazon Linux release/migrations/systemd/TLS installer; not a verified updater for the existing Ubuntu host |
| `test_postgresql.py` | Disposable local PostgreSQL regression and synthetic backup/restore checks |
| `database_backup.sh` | PostgreSQL dump and explicit empty-target restore; verify the actual host database before use |
| `verify_deployment.py` | HTTPS/readiness/deep-link checks with optional privately prompted fictional-account role checks |
| `requirements-infrastructure.txt` | Separate pinned local CloudFormation validator |

Lambda packaging, upload, parameter generation and private job commands are removed. `plan` reads the current EC2 estimate; it makes no AWS calls. No default provision/deletion occurs. Optional `platform`/`frontend` templates do not manage the existing manual server; deploying them requires a separate requested change and reviewed costs.

Read-only examples from the repository root:

```bash
python scripts/aws_deploy.py plan
python scripts/aws_deploy.py --profile campusshift --region us-east-2 profile-info
python scripts/package_backend.py
```

Keep `.env`, credentials, databases, backups and generated operator inputs out of Git. Shared database/application regression tools remain available independently of AWS.
