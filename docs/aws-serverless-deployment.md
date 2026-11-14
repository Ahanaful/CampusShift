# Historical serverless attempt — retired

**Current deployment is EC2.** The user chose EC2 after cost comparison and authorized full cleanup of the attempt. The Lambda/Aurora and Lambda/RDS routes are no longer deployment targets. See [current EC2 status and teardown verification](aws-current-deployment.md) and [operations](aws-deployment.md).

## What happened

On November 13, 2026, an artifact stack deployed and a verified Lambda ZIP was uploaded. The private Aurora API stack failed because Free Plan Aurora permits only Express configuration. CloudFormation rolled it back while retaining selected resources. The frontend change set was prepared but never executed. No application database was created, no migration/seed ran and the EC2 server was not modified.

Lambda plus regular RDS PostgreSQL was then considered. At current Ohio rates, a continuously running `db.t3.micro` with 20 GiB gp3 alone was $15.44/month; the light-demo whole-stack model was $17.156. The existing EC2 compute/disk/IP baseline was $12.842. The user chose EC2 because the alternative costs more and adds deployment work.

## Cleanup

All three attempt stacks, artifact object versions/bucket, three log groups, DB subnet/cluster-parameter groups and separate VPC/network dependencies were removed. The three generated secrets are marked for deletion with a seven-day recovery window ending November 21, 2026; AWS does not charge secrets marked for deletion. The existing EC2 instance, default VPC, root volume and application data remain.

Lambda entry points, Mangum dependency, private jobs, builders and serverless templates were removed from the active tree; earlier code remains in Git history. Shared PostgreSQL support and application correctness/security fixes were retained. No regular RDS replacement was provisioned.

No commands in this historical record should be used to recreate the attempt. The user requested EC2 only and no plan upgrade.
