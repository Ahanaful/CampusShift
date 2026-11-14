# Current AWS deployment

Updated November 13, 2026 America/Chicago (cleanup completed November 14 UTC).

**Selected deployment: the existing EC2 application.** The serverless attempt has been torn down at the user's request. Keep the active Free Plan and AWS-managed human login. Selected Region: `us-east-2` (Ohio); profile: `campusshift`.

## Live application

| Component | Verified state |
| --- | --- |
| Public application | http://3.133.115.154 |
| Instance | `CampusShift-Server`, `i-0b662a28fc2d1aeaf` |
| Compute | Running Linux `t3.micro`, `us-east-2a` |
| Root disk | 20 GiB gp3, `vol-02dd0fbe1cd9a0e52`, 3,000 IOPS / 125 MiB/s |
| Network | Existing default VPC `vpc-037fd02904c677068` |
| Web server | Nginx serving CampusShift frontend HTML |
| Backend | `/api/health` returns HTTP 200 and `{"status":"healthy","application":"CampusShift"}` |
| Access | Public HTTP/HTTPS allowed by SG; SSH restricted to `129.107.192.111/32` |

The existing server, disk, network and application data were not changed during the serverless attempt or teardown. Its public IP is automatically assigned and can change after stop/start. The current database engine/path, host processes, backup coverage and deployed Git revision have not been inspected over SSH. Application liveness does not prove all data workflows or migration readiness.

HTTPS is not verified; the tested public URL is HTTP, which does not protect login credentials. The existing root volume is unencrypted and deletes on instance termination. Preserve data and inspect backups before any future host replacement or termination. The Amazon Linux installers in the repository are preparation tools and must not be run on this Ubuntu/Nginx host without adaptation.

## Cost after cleanup

Estimated baseline for 730 running hours per month, before credits, allowances, taxes and variable usage:

| Item | USD/month |
| --- | ---: |
| EC2 `t3.micro`, $0.0104/hour | 7.592 |
| 20 GiB gp3 at $0.08/GiB-month | 1.60 |
| One public IPv4 at $0.005/hour | 3.65 |
| **Total** | **12.842 (~$12.84)** |

The instance uses Unlimited CPU credits; sustained CPU load can add surplus-credit charges. Traffic, future snapshots and backup storage are additional. No legacy 750-hour allowance is assumed. Rates were checked against current Ohio AWS Price List API and [AWS VPC pricing](https://aws.amazon.com/vpc/pricing/).

The alternative Lambda plus regular RDS demo model was $17.156/month, with more deployment work. Its database alone was $15.44/month. This drove the user's EC2 decision. See [comparison assumptions](../infrastructure/cost-comparison.us-east-2.json); its retained-secret figures describe the earlier pre-cleanup comparison, not current charges.

Last plan read: ACTIVE FREE, $100 reported credits, expiration `2027-05-13T00:36:01.583Z`. Check actual credit consumption in AWS Settings > Billing. No upgrade or managed-policy change occurred.

## Completed serverless teardown

User authorized deletion after previously asking for retention; the deletion request supersedes that earlier decision.

- Deleted stacks `campusshift-artifacts`, `campusshift-api` and `campusshift-web`, including their change sets.
- Deleted the private artifact bucket and its only versioned backend ZIP; checked for incomplete multipart uploads.
- Deleted all three attempt log groups.
- Deleted the unused DB subnet group and Aurora parameter group. No database or snapshot ever held application records.
- Removed both PostgreSQL security-group rules, two SGs, two route associations, the custom route table, two private subnets and VPC `vpc-0a86a4ba8e8e89a93`.
- Marked `campusshift-demo/database/admin`, `campusshift-demo/database/app` and `campusshift-demo/auth/jwt` for deletion. Recovery ends **November 21, 2026 at approximately 00:23 UTC**. They are inaccessible and [not charged while marked for deletion](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_delete-secret.html).
- The Lambda execution roles and temporary HTTP API were removed by the earlier rollback. No CloudFront distribution was created.

Final service listings confirmed no active CloudFormation stacks, S3 buckets, Lambda functions, HTTP/REST APIs, RDS instances/clusters, DB subnet/cluster-parameter groups or CloudFront distributions. No Ohio log groups remain; only the existing default VPC remains. AWS-created service-linked IAM roles are not billable resources and were left intact.

The repository no longer includes Lambda entry points, its adapter dependency, private Lambda jobs, Lambda packaging scripts or serverless CloudFormation templates. Shared PostgreSQL validation, transaction safety, local development, scheduler and attendance features remain. The existing EC2 host does not require a runtime rollback because no new serverless code was deployed to it.

Raw before/after discovery and deletion receipts remain ignored in `.local/serverless/`. CloudFormation deleted-stack history and CloudTrail event history are historical records, not active deployments. No configured CloudTrail trail was created.
