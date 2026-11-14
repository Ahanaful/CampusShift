# Infrastructure

**Current target: the existing EC2 application in Ohio (`us-east-2`).** The serverless attempt was torn down and its templates removed. [Current inventory, costs and cleanup evidence](../docs/aws-current-deployment.md) are authoritative.

- `cost-plan.us-east-2.json` models the existing running `t3.micro`, 20 GiB gp3 and public IPv4: about $12.84/month before credits/extras. No attempt-secret charges remain after marking them for deletion.
- `cost-comparison.us-east-2.json` preserves the EC2 versus Lambda/RDS comparison and records post-cleanup costs.
- `platform.json` and its example parameters prepare a **new Amazon Linux EC2** deployment with optional private RDS PostgreSQL/logging. They do not manage the existing manual Ubuntu host and must not be executed as its updater.
- `frontend.json` and its example parameters prepare optional private S3/CloudFront with an HTTPS origin. No such resources are currently deployed.
- `runtime/` contains prepared systemd, TLS Nginx, logging and log rotation configuration; host paths/services must be inspected before reuse.
- `iam/` contains historical scoped-policy proposals. Human access is AWS-managed; do not apply them to managed roles.
- `cost-plan.us-east-1.json` is historical pricing research and must not select a resource Region.

No default provisioning or cleanup runs from these files. Use [EC2 operations](../docs/aws-deployment.md). Keep project resources in the selected Region and preserve the active Free Plan. No CDK/bootstrap or Lambda@Edge is used.
