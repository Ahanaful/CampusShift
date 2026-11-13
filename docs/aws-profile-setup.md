# Dedicated campusshift AWS profile: Stage A

> **Do not follow the Console IAM-user instructions below for this project-based account.** AWS supplies managed human access through Builder ID/AWS Settings and restricts IAM login profiles. Use the existing campusshift login and explicit us-east-2 regional calls. No Advanced Features/policy change is needed for these operations. Read [the corrected decision](aws-project-free-plan-decision.md); the earlier generic-account setup below is historical only.

Target account: the user's new **AWS Free account plan**, with $100 credits now observed through the logged-in profile's Free Tier API (user confirmed the intended account). Target region: **us-east-1 (N. Virginia)**. No access to the old Academy account is required. No root access keys, AdministratorAccess, CDK/bootstrap, organization, account upgrade or application provisioning is part of this setup.

AWS CLI **2.40.2** is installed on this Windows PC. Initial checks listed no profiles; `aws sts get-caller-identity --profile campusshift` failed because the profile did not exist. After browser login, STS succeeded as AccountFullAccessRole (AdministratorAccess attached), and the live plan API returned FREE/ACTIVE with $100. EC2/RDS/SSM/CloudFormation reads are blocked by an organization SCP. That broad role is not the intended scoped identity; see the current evidence in aws-stage-a.md before creating additional IAM entities. Do not send passwords, MFA codes, credential files, access keys or login authorization codes to the assistant.

## Current blocker and scoped identity setup

The authenticated account is an organization member; additional IAM permissions cannot override its explicit SCP deny. The intended account is confirmed; request an authorized management-account policy review first. The following narrow Console setup remains available if its owner permits IAM user creation; it will not itself resolve the SCP. The assistant has created no IAM user/role/policy. If using the existing broad role for one-time Console setup, do not attach its AdministratorAccess to the new identity.

## Create a Console-only IAM user with scoped read permissions

Perform these one-time Console steps as the account owner or an existing identity authorized to manage IAM. Root may be needed for initial account setup; protect it with MFA and use it only for that bootstrap, never CLI login. These instructions do not grant the new user broad administrative access.

1. Open the AWS Console and confirm the account is the new Free Plan account. In **Billing and Cost Management → Free Tier**, confirm the plan/expiry; check **Credits** for the actual remaining credit and expiration. Do not click Upgrade. Avoid creating/joining AWS Organizations or enabling an organization-based Identity Center instance: joining Organizations automatically upgrades a Free Plan account.
2. Open **IAM → Policies → Create policy → JSON**. Paste the complete JSON from `infrastructure/iam/preflight-policy.json`. Choose **Next**, name it **CampusShiftPreflightReadOnly**, review it and choose **Create policy**. It grants selected discovery/credit/quota/template-validation reads; it cannot provision infrastructure, modify IAM, upgrade a plan or retrieve private secret values. Its regional infrastructure reads are limited to us-east-1; global service reads use `*` where the APIs require it.
3. Open **IAM → Users → Create user**. Enter **campusshift-deployer**. Select **Provide user access to the AWS Management Console**. If prompted to use Identity Center, choose **I want to create an IAM user**. Do not create an AWS organization. Select a protected Console password and require changing it on first sign-in. Do not create access keys.
4. On **Set permissions**, choose **Attach policies directly**. Attach **CampusShiftPreflightReadOnly** and AWS-managed **SignInLocalDevelopmentAccess**. Allow the Console's **IAMUserChangePassword** policy if requiring the initial password change; this is self-password management, not administrator access. Do not attach AdministratorAccess, PowerUserAccess, IAMFullAccess, EC2FullAccess or RDSFullAccess. Review and create the user.
5. Open **IAM → Users → campusshift-deployer → Security credentials → Multi-factor authentication → Assign MFA device**. Give the device a label, choose an authenticator app or security key/passkey as appropriate and complete enrollment using your device. Keep codes private. As account owner you can enroll the new user's MFA during bootstrap without adding general MFA/IAM management permissions to the discovery policy.
6. Copy the IAM user's **Console sign-in URL** from the user page; keep the initial password in your password manager. Sign out of the owner/root session, or use a separate private browser session. Sign in as **campusshift-deployer**, change the initial password and verify MFA is working.

IAM user/policy creation is a manual, scoped identity setup explicitly requested for Stage A; the assistant does not create IAM entities in your account. If a Console screen requires a Paid Plan upgrade or broader IAM policy than this setup, stop and record the restriction rather than accepting it. If an account admin can provide an existing scoped federated identity without joining an organization, use that instead.

## Configure the local profile with short-lived browser credentials

In your own Windows PowerShell terminal:

```powershell
aws --version
aws configure set region us-east-1 --profile campusshift
aws configure set output json --profile campusshift
aws login --profile campusshift --region us-east-1
```

The login command opens the browser. Select the **campusshift-deployer** IAM session in the new account and authorize the local CLI sign-in. Do not select root or an old Academy session. This uses temporary credentials, managed/refreshed by AWS CLI, instead of permanent access keys. AWS CLI writes protected local configuration/login cache outside the repository; never copy those files into CampusShift or share them. If the command does not open a browser, follow AWS CLI's displayed browser instructions privately. Do not paste the authorization URL/code into chat.

If the profile already exists, inspect it safely before reconfiguring; do not overwrite another identity. A successful `aws configure set` only sets non-secret preferences; it does not authenticate. `aws login` requires SignInLocalDevelopmentAccess, which grants local sign-in/token exchange, not deployment rights. Do not fall back to root keys if login is denied.

After the browser flow succeeds:

```powershell
aws sts get-caller-identity --profile campusshift
aws configure get region --profile campusshift
backend/.venv/Scripts/python.exe scripts/aws_deploy.py --profile campusshift --region us-east-1 profile-info
backend/.venv/Scripts/python.exe scripts/aws_deploy.py --profile campusshift --region us-east-1 preflight
```

`profile-info` executes `aws configure list --profile campusshift` internally but replaces entire access/secret/session-token value columns with `[REDACTED]` before displaying anything. Do not paste raw `aws configure list` output (even its partial key suffixes) or `export-credentials` output. STS account ID/ARN are identifiers, not secrets, but keep them private when publishing evidence. The preflight script rejects a root identity and never falls back to default/environment credentials. The API calls only read/list/describe/validate; no EC2 RunInstances, SSM secret decryption or billing mutation occurs.

## What happens next

The prepared Stage A policy grants read-only discovery rights; the actual logged-in AccountFullAccessRole currently has AdministratorAccess and must be replaced by the reviewed scoped identity. The tool blocks provisioning with that known broad role. No IAM policies were attached by the assistant. Deployment is deliberately blocked with this identity until Stage B defines the exact account/region/resources and approves a resource-scoped deployment policy. Do not respond to an AccessDenied by granting AdministratorAccess. Required access is documented in `aws-stage-a.md`; runtime/CloudFormation roles are separate from the human login and usually unnecessary for the current SSH/passfile deployment.

The assistant ran the read-only checks after your login; see aws-stage-a.md for successes and explicit policy denials. After an authorized identity/policy correction, the same checks can be rerun. A successful service read does not prove that provisioning is permitted by your Free Plan or IAM policy. Never run `freetier upgrade-account-plan`.

Sources: [AWS CLI browser login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html), [AWS Sign-In permissions](https://docs.aws.amazon.com/signin/latest/userguide/security-iam-awsmanpol.html), [Free account plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).
