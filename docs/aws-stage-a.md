# CampusShift Stage A: new AWS Free Plan account

> **Superseded diagnosis:** assigned home region is us-east-2. Corresponding Ohio reads and both template validations succeed. Do not ask the owner to change the managed SCP or create a Console IAM user based on this historical report. Read [the corrected project decision](aws-project-free-plan-decision.md).

Reviewed November 13, 2026. **Live preflight now confirms an ACTIVE FREE plan with $100 credits, but organization-level explicit denies block EC2/RDS/SSM/CloudFormation reads. The current profile is an existing AdministratorAccess role, not the intended scoped identity. No provisioning is authorized or attempted.** Selected region: **us-east-1 (N. Virginia)**. Dedicated CLI profile: **campusshift**. The new account has **no confirmed CampusShift infrastructure**. Old Academy/Ubuntu/IP references are historical and must not be reused as this account's resources. No CDK dependency exists; do not run `cdk bootstrap`.

## Evidence and blockers

| Check | Actual result |
| --- | --- |
| Existing infrastructure/scripts/application configuration inspected | Completed; reusable relational PostgreSQL, production/auth/readiness, migrations, SPA client, TLS/runtime/backup tools preserved |
| AWS CLI available | Confirmed `aws-cli/2.40.2`, Windows AMD64 |
| Dedicated profile | Non-secret profile preferences created: campusshift, us-east-1, JSON output |
| Human identity | Browser login verified an assumed AccountFullAccessRole with attached AdministratorAccess and no permission boundary; scoped IAM/MFA identity remains to be established/reviewed. No such role or policy was created by the assistant |
| STS identity | Requested STS command succeeded with campusshift. User confirmed account ending 7313 is the intended new Free Plan account. It is an organization member; full identifiers/evidence stay in ignored local logs |
| Free plan / credits / expiration | Live GetAccountPlanState returned FREE / ACTIVE / USD 100. Expiry: May 12, 2027 at 7:36 p.m. America/Chicago (May 13, 2027 00:36 UTC) |
| VPC/subnets/AMI/key pair/quotas | VPC/subnet/route/SG/instance/SSM AMI reads explicitly denied by an SCP. Standard EC2 quota read succeeded: 5 vCPUs; quota is not launch permission |
| Service access | S3 and CloudFront list APIs succeeded; EC2/RDS/CloudFormation reads explicitly denied by an organization SCP. No service creation was tested |
| CloudFormation validation | All three local templates pass cfn-lint. Both live ValidateTemplate calls were attempted and explicitly denied by the same SCP; no stacks/change sets created |
| HTTPS origin | Current template requires an owned hostname/certificate; neither supplied. ListVpcOrigins succeeded with zero items, but EC2/network policy blocks the private alternative too |
| Budget monitoring | Current-account DescribeBudgets returned zero budgets. Default AWS credit emails/organization-wide monitoring were not verified; no alert setup performed |
| AWS modifications | No roles/policies, instances, DBs, buckets, stacks, distributions, budget changes, plan upgrades or destructive operations performed by the assistant |

Local preferences alone do not establish identity; browser login has now succeeded for the broad role above. Review [the exact IAM/Console/browser-login steps](aws-profile-setup.md) to establish the intended scoped identity. The following are read-only rechecks after identity/policy resolution:

```powershell
aws sts get-caller-identity --profile campusshift
aws configure get region --profile campusshift
backend/.venv/Scripts/python.exe scripts/aws_deploy.py --profile campusshift --region us-east-1 profile-info
backend/.venv/Scripts/python.exe scripts/aws_deploy.py --profile campusshift --region us-east-1 preflight
backend/.venv/Scripts/python.exe scripts/aws_deploy.py --profile campusshift --region us-east-1 validate platform
backend/.venv/Scripts/python.exe scripts/aws_deploy.py --profile campusshift --region us-east-1 validate frontend
backend/.venv/Scripts/python.exe scripts/aws_deploy.py --profile campusshift --region us-east-1 plan
```

To assert the intended account, add `--expected-account YOUR_CONSOLE_ACCOUNT_ID` after `preflight`. Do not publish raw credential diagnostics. `profile-info` redacts entire credential rows from internally captured `aws configure list`. Every AWS call, including frontend S3 upload, explicitly selects the profile; ambient access keys/container/metadata credentials cannot silently supply another identity. Root identities are rejected. Mutations additionally require matching account, positive credits, ACTIVE FREE plan and the existing explicit cost-approval flags. No script calls plan-upgrade, Organizations or CDK commands.

If billing reads return AccessDenied despite the prepared policy, the account owner may need to activate IAM access under **Account → IAM user and role access to Billing information → Edit → Activate IAM Access**. This enables IAM evaluation; it does not grant broad billing permissions. The prepared policy permits selected reads only. Check the exact error rather than attaching BillingFullAccess or AdministratorAccess.

## Free Plan service assessment

| Service | Public evidence | Remaining account-specific check |
| --- | --- | --- |
| EC2 | AWS catalog lists both plans; live regional reads explicitly denied by SCP | Organization owner must review the deny. Instance/VPC/AMI/launch feasibility is blocked despite a readable 5-vCPU quota; no launch attempted |
| RDS PostgreSQL | AWS catalog lists both plans; live DescribeDBInstances and orderable-options reads explicitly denied by SCP | Resolve intended-account/organization policy first, then verify exact 16.x micro/gp3/encryption and subnet eligibility; no DB created |
| S3 | AWS catalog lists both plans; ListBuckets succeeded and returned zero buckets | Exact private bucket configuration and create rights remain untested; no bucket created |
| CloudFront | ListDistributions and ListVpcOrigins succeeded; no origins returned | OAC/function/origin feature creation is untested. Do not opt into a paid CloudFront plan. EC2 SCP deny prevents validating the backend design |
| CloudFormation | ListStacks and both live ValidateTemplate calls explicitly denied by SCP | Organization owner review required; local schema validation passes, but no cloud stack operation is authorized/tested |

Service availability, IAM permission, regional quota/capacity and a specific feature's Free Plan eligibility are separate checks. A successful empty list is evidence only of read access; AccessDenied is not proof that a service is unavailable under the Free Plan. Old "750 free EC2/RDS hours for 12 months" offers must not be assumed for this new account. Use the current Free Tier API/Console. No unlimited service access, create permission or live deployment is claimed.

AWS Free Plan can close access when credits or time expire. Do not join Organizations/Control Tower to enable identity tooling: doing so can auto-upgrade the account. IAM browser login is used instead of provisioning organization-based Identity Center. Existing scoped federation is acceptable if it does not require an upgrade. IAM is no longer inherently read-only: the **Stage A policy is intentionally read-only**, and exact deployment permissions will be reviewed separately.

## Organization-policy blocker: next manual diagnostic step

The live deny messages identify an **explicit deny in a service control policy (SCP)**. Read-only DescribeOrganization confirms this is a member account controlled by a different management account. Reading the policy document itself was denied, so its name, full conditions, intent and whether the restriction is Free Plan/provider-managed or owner-configured are **not known**. The assistant did not create/join this organization, remove policies or change the plan; the account-plan API still reports FREE.

1. STS account was compared with the Console and the user confirmed account ending 7313 is correct. Keep that profile/account/region; do not use another account/region to bypass this restriction.
2. If it is correct, send the denied operation/region/SCP ARN from the private preflight evidence to the **authorized organization management-account owner** or AWS account support. Ask whether the policy intentionally restricts this member and whether the proposed CampusShift service set is permitted **without changing the account plan**.
3. The owner can inspect **AWS Organizations ? Policies ? Service control policies** and the account/root/OU policy attachments. Merely inspect/review; do not detach a guardrail, leave an organization or change it broadly as a deployment workaround. If permitted, the owner must propose a narrow, separately approved correction. No change is made by this assistant.
4. More IAM policies or EC2/CloudFormation roles cannot override an SCP explicit deny. Moving from the broad role to a scoped identity is still required for least privilege, but that alone will not repair these service denies. Do not upgrade based on these errors: they do not prove a Free Plan exclusion.
5. After the authorized resolution, rerun preflight and read-only template validation. If the policy is intentional and cannot be changed within the user's constraints, report the existing EC2/RDS/CloudFormation architecture blocked and present a genuinely permitted alternative for approval before implementing/deploying it.

## Template and tooling audit

| Area | Reused / Stage A change / remaining review |
| --- | --- |
| Frontend | Private S3/OAC, encryption/versioning, SPA function, HTTPS viewers, no-cache API with bearer/query forwarding retained. Same-origin `/api` means no browser secrets or production localhost origin |
| Backend | AL2023 x86_64, IMDSv2, non-root systemd Uvicorn, loopback upstream, TLS Nginx and protected passfile/JWT delivery retained; no business logic rewrite |
| Region/profile | All tooling explicitly uses campusshift/us-east-1; removes old sandbox identity assumptions, stops on missing login/root/wrong account/invalid Free Plan |
| EC2 costs | Allowed size narrowed to reviewed t3.micro; Standard CPU credits explicitly prevent EC2 Unlimited surplus charges, at the cost of throttling during sustained load |
| RDS costs | Allowed class narrowed to db.t3.micro; explicit orderable PostgreSQL 16 minor required; Single-AZ, enhanced monitoring and Performance Insights off; extended-support enrollment disabled; 20-GiB gp3 and no storage autoscaling |
| Ownership | Stable project-tagged RDS identifier and Project/Environment tags aid permission/cost scoping. No data-bearing replacement has been executed |
| Secrets | Existing SSM SecureString dynamic reference + protected SSH-delivered runtime passfile is reusable; scoped Put/GetParameter/KMS access and exact secret path need Stage B review. No values in templates/user-data/outputs |
| Networking | Current template reuses an existing public subnet and two private DB subnets. New-account preflight must confirm them; default VPC subnets must not be assumed private. If absent, plan explicit private subnets/route tables with no NAT; creation needs approval |
| HTTPS | Existing frontend.json remains a public **HTTPS** custom-origin design. CloudFront VPC origin, private HTTP listener and no-NAT bootstrap are not implemented by that template |
| IAM | Main templates create no IAM resources. Stage A human read policy and optional log-only EC2 role/profile template prepared; exact write policy awaits confirmed IDs and architecture |
| Safety | Account-plan guard, resource replacement/removal refusal and explicit creation/cost gates retained. Recovery is normal persistent AWS resource/backup recovery, not a session-reset assumption |

The current main templates need no IAM capability acknowledgement. The separate `infrastructure/iam/runtime-logs.json` creates unnamed IAM Role/InstanceProfile resources and requires **CAPABILITY_IAM** if explicitly approved/deployed. If a later template specifies RoleName/InstanceProfileName, review **CAPABILITY_NAMED_IAM**. A capability flag acknowledges a template's IAM content; it does not grant the deployer any permission.

## IAM roles and deployment permissions

| Identity/resource | Required now? | Precise purpose / scope |
| --- | --- | --- |
| Human campusshift-deployer Console user with MFA and CLI temporary login | Yes, manual setup | SignInLocalDevelopmentAccess plus project preflight reads. No access keys or broad admin policy |
| Additional human deployment role/write policy | Stage B only | Limit CloudFormation operations to campusshift-* stack ARNs; exact underlying EC2/RDS/S3/CloudFront/SSM/KMS operations to approved resources, region and tags. Separate create/configure from destructive cleanup |
| EC2 instance role/profile | Not required for current base path | Application uses PostgreSQL, not AWS APIs; SSH installs source and passfile credentials. No static AWS credentials on EC2 |
| Optional CloudWatch instance role/profile | Only if approved | Provided template trusts EC2 and permits only CreateLogStream/PutLogEvents/DescribeLogStreams on the chosen application log group; no log-group creation, S3, IAM or admin permissions |
| CloudFormation execution role | Not required for this small human-run deployment | Current calls use the invoking identity's temporary credentials. A persistent service role would add delegation/pass-role risk; add only if later automation justifies it |
| RDS service-linked role | May be required on first RDS creation | AWSServiceRoleForRDS may be created by RDS; grant scoped iam:CreateServiceLinkedRole with the RDS service-name condition only if absent and separately approved |
| CloudFront VPC-origin service-linked role | Only for the proposed private-origin alternative | AWSServiceRoleForCloudFrontVPCOrigin is service-managed. Review service-linked-role/network-interface permissions; not a generic instance profile or an organization requirement |

For Stage B, underlying write actions must cover exactly the chosen template resources: EC2 launch/tag/SG/ingress/egress and optional network provisioning; RDS instance/subnet-group configuration/tagging; S3 bucket/encryption/public-block/versioning/bucket-policy plus asset upload; CloudFront distribution/OAC/function/security policy/invalidation; and the approved SSM secret path/default service KMS key. Resource ARNs and required wildcard create APIs must be documented individually before attaching a deployment policy. Do not solve deployment errors with service-wide FullAccess. If a runtime profile is selected, permit `iam:PassRole` only on its exact role ARN with `iam:PassedToService=ec2.amazonaws.com`; do not grant pass-role to `*`. Secret rotation, role changes, replacements and deletion stay separately reviewed.

The Stage A read identity cannot prove EC2 launch permissions with RunInstances DryRun because it deliberately lacks that write action. After the exact Stage B write policy is approved/installed, a fully parameterized `--dry-run` can test authorization without launching, but it still does not prove capacity or Free Plan feature admission. No dry-run launch was executed here.

## Proposed resources and monthly cost

This is the **existing public-HTTPS-origin** template footprint, proposed only. Costs are gross on-demand usage before credits/free allowances, 730 running hours/month, reviewed November 13, 2026 for us-east-1. This is not a promise of zero credit use.

| Resource | Quantity / rate | Monthly estimate |
| --- | --- | ---: |
| Amazon Linux EC2 t3.micro | 1 × $0.0104/hour | $7.59 |
| Encrypted gp3 root EBS | 12 GiB × $0.08/GiB-month planning rate | $0.96 |
| EC2 public IPv4 | 1 × $0.005/hour | $3.65 |
| RDS PostgreSQL db.t3.micro, Single-AZ | 1 × $0.018/hour | $13.14 |
| RDS gp3 storage | 20 GiB × $0.115/GiB-month | $2.30 |
| **Fixed baseline** | | **$27.64** |
| S3 versions/backups, CloudFront usage, optional logs and incidental traffic | Low-traffic planning allowance; exact free offers unverified | **Plan $30–35 total** |

EC2 and RDS hourly rates were read from official public us-east-1 pricing data; RDS catalog publication was 2026-11-12. The IPv4 rate comes from AWS VPC pricing. EBS is a planning rate to reconfirm in the us-east-1 Calculator during Stage B. RDS price excludes surplus CPU credits (RDS T3 can incur them), extra backup/snapshot storage, cross-AZ DB traffic and other variable usage. No workload measurement exists yet; $35 is not a hard cap. Standard EC2 credits can throttle the app rather than incur surplus EC2 credit charges. Recheck rates before provisioning.

The inventory also includes one existing VPC/public subnet/two private DB subnets, two SGs and their rules, one DB subnet group, one private versioned frontend bucket/OAC/bucket policy, one CloudFront distribution, SPA function and response-headers policy, one existing/new approved key pair, an approved standard SSM SecureString and optionally one seven-day log group/profile. IAM/CloudFormation do not make the underlying compute free. No NAT Gateway, ALB/NLB, extra EC2, Multi-AZ, enhanced monitoring, paid support, reservation, Savings Plan or paid Marketplace component is proposed.

At $30–35/month, $100 covers roughly 2.9–3.3 always-on months, not the approximately six-month plan duration. Keeping a $20 reserve leaves about 2.3–2.7 months. Running only during demonstrations reduces compute-hours; storage/snapshots/versions persist, and stopped RDS instances automatically restart after the supported maximum stop period (check current RDS stop policy before scheduling). Do not promise six months of always-on availability under $100. On the Free Plan this is credit consumption; it is not an authorization to charge a Paid Plan.

Before provisioning, approve and configure email-only AWS Budgets alerts for actual monthly gross cost at $10/$20/$30 and forecast at $30; **exclude Credits/Refunds** from the budget cost calculation so credit-funded consumption does not appear as zero. Also review remaining credits at $75/$50/$25 and stop for review at $20. Use Billing → Free Tier/Credits and the Free Tier API for actual balance/expiry. Budget alerts are notifications, not resource stops. Email recipients and budget creation remain manual/approval-gated; no SNS topic or budget action role is needed just for email alerts.

## HTTPS choices for Stage B

1. **Current template, least change:** CloudFront default HTTPS viewer domain, private S3, `/api` forwarded over verified HTTPS to EC2. Requires an operator-controlled API hostname and publicly trusted matching origin certificate. An existing delegated subdomain avoids a purchase; none is confirmed. No certificate can be obtained for an AWS-owned EC2 hostname by assuming ownership. No public HTTP auth or self-signed-origin workaround is acceptable. The CF prefix list reduces direct access but admits other distributions; backend authorization remains essential.
2. **No purchased domain candidate:** CloudFront VPC origin to private EC2, with browser HTTPS on the generated cloudfront.net name and private-only HTTP from CloudFront to Nginx. This is **not end-to-end TLS**, but avoids sending auth over public plaintext. It requires a VPC-origin/SG/template change and an approved private administrative/bootstrap path. With no NAT or extra instance, review EC2 Instance Connect Endpoint and prepackaged dependencies/source via a private S3 gateway endpoint; confirm feature availability, IAM roles, artifacts and additional resource/operating complexity first. Current dnf/pip internet bootstrap will not work unchanged in a no-NAT private subnet. It is a proposal, not a deployable/verified template or the $27.64 public-origin quote. If end-to-end TLS is required even on the private hop, retain the trusted-origin-certificate requirement.

No-domain VPC origins are not a reason to silently add a NAT Gateway, ALB, paid endpoint or use an external DNS service without ownership. If neither design is feasible within the Free Plan, present a revised resource/cost plan before provisioning. Existing templates remain secure-failing until a trusted custom origin is supplied; they have not been weakened to public HTTP.

## Exact next steps: Stage B

1. The intended account is confirmed. Have its authorized organization owner review the explicit EC2/RDS/SSM/CloudFormation SCP denies. Establish a scoped IAM/MFA login instead of AccountFullAccessRole. Rerun STS/preflight; no additional IAM allow overrides the SCP. No credentials need to be shared.
2. Once SCP restrictions are legitimately resolved, rerun live validation of both main templates with the authenticated scoped profile. Review the Free Plan Console eligibility of the exact t3.micro, PostgreSQL 16.x micro/gp3, OAC/function and any VPC-origin feature without clicking Create/Launch/Upgrade.
3. Choose the HTTPS option. Confirm an owned origin hostname/certificate, or approve designing the private-origin/no-NAT bootstrap alternative. Inventory any missing private subnets/routes/management endpoints before quoting it.
4. Fill ignored parameter files from actual preflight results: account/region, VPC/subnets/AZs, key pair, administrator /32, regional CF prefix list, exact PostgreSQL 16 minor, secret path/version, optional runtime profile. Never insert passwords or JWT secrets.
5. Produce the exact resource-scoped deployment IAM policy and any service-linked-role/pass-role grants for those IDs. Have the owner review/install only those permissions. Do not create a CloudFormation execution role or runtime profile unless the selected design requires it. Finalize the current price quote, $100 credit runway, email-only budget alerts and an approved cleanup/retention plan.
6. Present that concrete inventory, permissions, HTTPS path, monthly estimate, credit runway and blockers for **explicit approval**. Stage B does not execute resources. Only after approval proceed to Stage C change-set creation/review/execution and incremental deployment. Creating a change set is not part of this Stage A audit.

Sources: [AWS Free Tier service catalog](https://aws.amazon.com/free/), [plan terms](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html), [account-plan API](https://docs.aws.amazon.com/cli/latest/reference/freetier/get-account-plan-state.html), [Always Free tracking](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/tracking-free-tier-usage.html), [EC2 T3 pricing](https://aws.amazon.com/ec2/instance-types/t3/), [RDS us-east-1 catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/us-east-1/index.json), [EBS pricing](https://aws.amazon.com/ebs/pricing/), [public IPv4 pricing](https://aws.amazon.com/vpc/pricing/), [CloudFront VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html), [CloudFront service-linked role](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-service-linked-roles.html).

The SCP interpretation is supported by [AWS Organizations policy evaluation documentation](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html): member-account AdministratorAccess cannot override an SCP deny. This is distinct from Free Plan product eligibility.
