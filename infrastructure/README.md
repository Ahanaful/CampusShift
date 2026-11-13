# Infrastructure

> **Current deployment:** the existing Ubuntu EC2/Nginx/FastAPI/SQLite server
> at <http://3.133.115.154>. Use [the EC2 runbook](../docs/aws-deployment.md)
> and [verification report](../docs/aws-ec2-verification.md). These CloudFormation
> files are prepared alternatives; no deployment of them is established. Do not
> apply them to or replace the current server. Prior AWS reads and account/credit
> observations below are historical and require rechecking.

Phase 6 preparation: `platform.json` defines an Amazon Linux EC2 backend, restrictive security groups, optional private single-AZ RDS PostgreSQL and optional seven-day CloudWatch log group. `frontend.json` defines a private versioned S3 bucket, CloudFront OAC, SPA route rewriting and HTTPS-only `/api` forwarding. No IAM resources are created.

Start with [Stage A and cost/permission review](../docs/aws-stage-a.md), [secure IAM/profile setup](../docs/aws-profile-setup.md), then [feasibility and architecture](../docs/aws-architecture.md), then [the historical EC2/RDS proposal](../docs/aws-ec2-rds-proposal.md). Templates have been prepared for review; their existence does not mean AWS permissions or deployment were verified. Existing VPC/subnets, key pair, approved SSM SecureString, a real API DNS name and trusted origin certificate are prerequisites. Parameter examples contain placeholders only. Do not execute until costs and the exact change set are approved.

`runtime/` contains systemd, Nginx TLS, structured logging, log rotation and optional CloudWatch agent configuration. Region is selected by AWS CLI, not hardcoded into resources. Preserve the documented legacy manual deployment until a replacement is verified.

The planned profile/region were campusshift/us-east-2; this workstation currently has no such profile. Stage B prepares code only. The existing managed project human role is expected; do not follow the historical Console-user instructions or apply `iam/preflight-policy.json` to managed roles. `serverless.json` creates two scoped Lambda execution roles with `CAPABILITY_IAM` after approval; no instance profile or CDK bootstrap is needed. Aurora PostgreSQL 16.15 and zero-ACU support were confirmed read-only in Ohio. Review `cost-plan.us-east-2.json`; `cost-plan.us-east-1.json` is historical. Creation rights, capacity and deployed performance remain untested.
