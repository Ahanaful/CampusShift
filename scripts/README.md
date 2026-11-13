# Scripts

> Current Stage B: use assigned us-east-2 and the existing managed project login. The helper now defaults to Ohio, accepts the AWS-managed human role, reviews Ohio costs, and supports approval-gated serverless commands. Read the [serverless runbook](../docs/aws-serverless-deployment.md). No resources are provisioned by default.

Phase 6 tools, used from the repository root:

| Tool | Purpose |
| --- | --- |
| `aws_deploy.py` | Profile-safe read-only preflight/redacted diagnostics/plan/template validation/output lookup; explicit approved change-set creation/execution and frontend upload |
| `build_lambda.py` | Local Linux/Python 3.12 x86_64 ZIP, pinned runtime image/dependency constraints and Ohio RDS CA; writes only ignored `.local/serverless/` |
| `verify_lambda_package.py` | Actual ZIP import/health/passfile/50-student scheduler smoke test in a network-isolated Linux Lambda container |
| `package_backend.py` | Allowlisted source archive in ignored `.local/`, excluding secrets and databases |
| `configure_server.py` | Interactive Linux-only secret/passfile/TLS configuration; refuses existing configuration |
| `deploy_backend.sh` | Explicit new-release install/migrations/systemd/TLS Nginx on the new Amazon Linux server |
| `test_postgresql.py` | Disposable loopback Docker PostgreSQL regression and synthetic backup/restore verification |
| `database_backup.sh` | Restricted PostgreSQL dump; explicit restore only into an empty target |
| `verify_deployment.py` | HTTPS/readiness/deep-link checks and optional privately prompted fictional-account role checks |
| `requirements-infrastructure.txt` | Pinned local CloudFormation validator, separate from runtime dependencies |

Read [serverless deployment instructions](../docs/aws-serverless-deployment.md) before use. AWS tools require the non-root campusshift profile in us-east-2; change sets, uploads, execution and private jobs require prior resource/cost approval plus the expected account ID. `job ... seed` also needs `--approve-demo-data` and prompts privately for a password. `parameters` reads existing stack outputs and writes non-secret local inputs. No default provisioning or deletion occurs. Existing deployments and data are preserved. Linux host scripts remain the EC2 fallback, not Windows workstation setup scripts. Actual cloud creation/network/auto-pause tests remain pending approval.

First complete [IAM/browser login](../docs/aws-profile-setup.md) and [Stage A](../docs/aws-stage-a.md). `preflight` checks account plan/credits and quotas without creating anything. `plan` is offline. Mutations additionally require an ACTIVE FREE plan, positive credits, matching account and explicit cost approval; none were run during Stage A.
