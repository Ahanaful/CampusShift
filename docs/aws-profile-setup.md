# CampusShift AWS profile

Use profile `campusshift`, selected Region `us-east-2` (Ohio), and the existing AWS-managed project login. The new AWS experience manages human access; do not create IAM team-member identities or replace managed human-role policies.

Confirm the Region in AWS Settings > View all projects > Overview > Additional Info > Region. The local `~/.aws/config` profile also records `us-east-2`. The Agent Toolkit/MCP endpoint Region `us-east-1` is distinct from the resource Region.

```bash
aws login --profile campusshift --region us-east-2
aws sts get-caller-identity --profile campusshift --region us-east-2
python scripts/aws_deploy.py --profile campusshift --region us-east-2 profile-info
```

Never share credentials, login codes, private keys, `.aws` files or `.env` contents. The helper excludes ambient credentials from named-profile commands and redacts credential rows. It blocks root identities, wrong-project mutations, out-of-Region mutations and provisioning outside the active Free Plan/credit gate.

Earlier `us-east-1` regional SCP denials were caused by the wrong Region. They are not a reason to alter managed policies, join Organizations or activate Advanced Features. If a previously working operation suddenly returns Access Denied, check spend status in AWS Settings > Billing and ask the project owner about any spend limit before changing permissions.

The Free Plan remains selected. AWS Settings manages billing and project team members. Read-only access and successful template validation do not prove creation eligibility. No automatic plan upgrade or resource creation is part of profile setup.

See [current deployment](aws-current-deployment.md). The earlier scoped-IAM-user instructions and Stage A policy proposal are historical; do not apply them to managed roles.
