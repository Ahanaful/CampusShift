# Decision: keep Free Plan and the existing EC2 application

Selected Region: Ohio (`us-east-2`), profile: `campusshift`, help level: LOW. Human access remains AWS-managed. Keep the Free Plan, existing EC2 server and its data; do not upgrade, activate Advanced Features or change managed policies.

The earlier private Aurora proposal was rejected because Free Plan Aurora supports only Express configuration. Regular RDS PostgreSQL can connect to Lambda, but introduces always-running database compute and storage plus deployment complexity. Its light-demo model was $17.156/month versus the existing EC2 baseline of $12.842, before credits and extras. The earlier $14.042 current figure included $1.20 for retained attempt secrets; those secrets are now marked for deletion and no longer charged.

The user authorized reverting to EC2 and tearing down the serverless attempt. That request supersedes earlier retention/recovery instructions. Cleanup details and verified remaining resources are in [current deployment](aws-current-deployment.md); [cost assumptions](../infrastructure/cost-comparison.us-east-2.json) preserve the comparison.

Earlier wrong-Region SCP denials are not a reason to modify managed project policies or human access. A service being on the Free Plan allowlist does not establish that every configuration is eligible. No plan upgrade or regular RDS replacement occurred.

Follow the [EC2 operations runbook](aws-deployment.md). Historical Stage A/Academy and serverless research do not describe the current running architecture.
