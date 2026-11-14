"""Explicit AWS discovery/change-set/upload tools. No default provision or deletion.

Run --help. Credentials are resolved by AWS CLI, never read or printed by this script.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import re

ROOT = Path(__file__).resolve().parents[1]


class AWS:
    def __init__(self, region, profile="campusshift"):
        self.region = region
        self.profile = profile

    def environment(self):
        # Named profiles must never accidentally use a different account's
        # ambient static/container credentials or the EC2 metadata service.
        blocked = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN",
                   "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE",
                   "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "AWS_CONTAINER_CREDENTIALS_FULL_URI",
                   "AWS_CONTAINER_AUTHORIZATION_TOKEN", "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE"}
        return {**{key: value for key, value in os.environ.items() if key not in blocked},
                "AWS_EC2_METADATA_DISABLED": "true", "AWS_CLI_AUTO_PROMPT": "off", "AWS_MAX_ATTEMPTS": "2"}

    def command(self, *arguments):
        return ["aws", "--profile", self.profile, "--region", self.region, "--no-cli-pager",
                "--cli-connect-timeout", "8", "--cli-read-timeout", "20", *arguments]

    def text_call(self, *arguments):
        result = subprocess.run(self.command(*arguments), capture_output=True, text=True,
                                env=self.environment(), timeout=60)
        if result.returncode:
            # Commands never retrieve secret values. Avoid SDK/CLI debug mode.
            raise RuntimeError(result.stderr.strip())
        return result.stdout

    def call(self, *arguments):
        return json.loads(self.text_call(*arguments, "--output", "json") or "{}")

    def outputs(self, stack):
        value = self.call("cloudformation", "describe-stacks", "--stack-name", stack)
        return {row["OutputKey"]: row["OutputValue"] for row in value["Stacks"][0].get("Outputs", [])}


def redact_profile_listing(value):
    return "\n".join("[REDACTED credential row]" if re.search(r"access_key|secret_key|session_token|security_token", line, re.I) else line
                     for line in value.splitlines())


def require_identity(aws, expected_account=None):
    identity = aws.call("sts", "get-caller-identity")
    if identity.get("Arn", "").endswith(":root"):
        raise RuntimeError("Root CLI identity is not permitted. Use the dedicated non-root campusshift identity")
    if expected_account and identity["Account"] != expected_account:
        raise RuntimeError("Active account is not the explicitly authorized account; no mutation performed")
    return identity


def require_free_plan(aws):
    plan = aws.call("freetier", "get-account-plan-state")
    if plan.get("accountPlanType") != "FREE" or plan.get("accountPlanStatus") != "ACTIVE":
        raise RuntimeError("An ACTIVE FREE account plan is required; no upgrade or mutation performed")
    if plan.get("accountPlanRemainingCredits", {}).get("amount", 0) <= 0:
        raise RuntimeError("Positive remaining credits could not be confirmed; stop for cost review")
    return plan


def known_broad_identity(identity):
    # AWS supplies this human role in Free Plan projects. Preserve the supported
    # project login workflow; do not modify its managed policies.
    return ":assumed-role/AccountFullAccessRole/" in identity.get("Arn", "")


def discover(aws, expected_account=None):
    report = {"profile": aws.profile, "region": aws.region, "creation_permissions": "NOT TESTED; reads do not prove create rights or Free Plan feature eligibility", "checks": {}}
    try:
        identity = require_identity(aws, expected_account)
        report["checks"]["identity"] = {"status": "confirmed_read", "result": identity}
        report["identity_review"] = "AWS-managed project human role; expected project login identity" if known_broad_identity(identity) else "non_root; scope/MFA still require review"
    except RuntimeError as error:
        report["checks"]["identity"] = {"status": "blocked", "detail": str(error)}
        report["next_step"] = "Follow docs/aws-profile-setup.md, then rerun preflight. No other account calls attempted."
        print(json.dumps(report, indent=2))
        return 1
    checks = {
        "lambda_capacity": ("lambda", "get-account-settings"),
        "http_apis": ("apigatewayv2", "get-apis", "--query", "Items[].Name"),
        "secret_metadata": ("secretsmanager", "list-secrets", "--filters", "Key=name,Values=campusshift", "--query", "SecretList[].{Name:Name,ARN:ARN}"),
        "account_plan_and_credits": ("freetier", "get-account-plan-state"),
        "free_tier_usage": ("freetier", "get-free-tier-usage"),
        "budgets": ("budgets", "describe-budgets", "--account-id", identity["Account"], "--query", "Budgets[].{Name:BudgetName,Limit:BudgetLimit,Actual:CalculatedSpend.ActualSpend} || `[]`"),
        "instance_profiles": ("iam", "list-instance-profiles", "--query", "InstanceProfiles[].{Name:InstanceProfileName,Roles:Roles[].RoleName}"),
        "vpcs": ("ec2", "describe-vpcs", "--query", "Vpcs[].{Id:VpcId,Cidr:CidrBlock,Default:IsDefault}"),
        "subnets": ("ec2", "describe-subnets", "--query", "Subnets[].{Id:SubnetId,Vpc:VpcId,AZ:AvailabilityZone,PublicIp:MapPublicIpOnLaunch}"),
        "routes": ("ec2", "describe-route-tables", "--query", "RouteTables[].{Id:RouteTableId,Vpc:VpcId,Associations:Associations,Routes:Routes}"),
        "internet_gateways": ("ec2", "describe-internet-gateways", "--query", "InternetGateways[].{Id:InternetGatewayId,Attachments:Attachments}"),
        "key_pairs": ("ec2", "describe-key-pairs", "--query", "KeyPairs[].KeyName"),
        "instance_options": ("ec2", "describe-instance-types", "--instance-types", "t3.micro", "--query", "InstanceTypes[].{Type:InstanceType,Architectures:ProcessorInfo.SupportedArchitectures,Vcpu:VCpuInfo.DefaultVCpus,MemoryMiB:MemoryInfo.SizeInMiB}"),
        "instance_offerings": ("ec2", "describe-instance-type-offerings", "--location-type", "availability-zone", "--filters", "Name=instance-type,Values=t3.micro"),
        "amazon_linux_image": ("ssm", "get-parameter", "--name", "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64", "--query", "Parameter.Value"),
        "security_groups": ("ec2", "describe-security-groups", "--query", "SecurityGroups[].{Id:GroupId,Name:GroupName,Vpc:VpcId}"),
        "cloudfront_prefix": ("ec2", "describe-managed-prefix-lists", "--filters", "Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing"),
        "rds": ("rds", "describe-db-instances", "--query", "DBInstances[].{Id:DBInstanceIdentifier,Class:DBInstanceClass,Engine:Engine,Public:PubliclyAccessible}"),
        "rds_classes": ("rds", "describe-orderable-db-instance-options", "--engine", "postgres", "--db-instance-class", "db.t3.micro", "--query", "OrderableDBInstanceOptions[].{Version:EngineVersion,Class:DBInstanceClass,AZ:AvailabilityZones[].Name}"),
        "s3": ("s3api", "list-buckets", "--query", "Buckets[].Name || `[]`"),
        "cloudfront": ("cloudfront", "list-distributions", "--query", "DistributionList.Items[].{Id:Id,Domain:DomainName} || `[]`"),
        "cloudfront_vpc_origins": ("cloudfront", "list-vpc-origins"),
        "cloudformation": ("cloudformation", "list-stacks", "--query", "StackSummaries[].{Name:StackName,Status:StackStatus}"),
        "ssm_metadata_only": ("ssm", "describe-parameters", "--max-results", "5", "--query", "Parameters[].{Name:Name,Type:Type}"),
        "cloudwatch": ("logs", "describe-log-groups", "--log-group-name-prefix", "/campusshift/", "--query", "logGroups[].logGroupName"),
        "ec2_vcpu_quota": ("service-quotas", "get-service-quota", "--service-code", "ec2", "--quota-code", "L-1216C47A"),
        "rds_quotas": ("service-quotas", "list-service-quotas", "--service-code", "rds", "--query", "Quotas[].{Name:QuotaName,Value:Value,Code:QuotaCode}"),
        "cloudfront_quotas": ("service-quotas", "list-service-quotas", "--service-code", "cloudfront", "--query", "Quotas[].{Name:QuotaName,Value:Value,Code:QuotaCode}")
    }
    for name, arguments in checks.items():
        try:
            report["checks"][name] = {"status": "confirmed_read", "result": aws.call(*arguments)}
        except RuntimeError as error:
            detail = str(error)
            status = "blocked_by_scp" if "explicit deny in a service control policy" in detail.lower() else "blocked_or_unavailable"
            report["checks"][name] = {"status": status, "detail": detail}
    plan = report["checks"]["account_plan_and_credits"].get("result", {})
    report["free_plan_gate"] = "confirmed" if (plan.get("accountPlanType") == "FREE" and plan.get("accountPlanStatus") == "ACTIVE" and plan.get("accountPlanRemainingCredits", {}).get("amount", 0) > 0) else "blocked_or_unverified"
    report["service_eligibility"] = "Service reads are evidence of read access only. Read-only discovery does not authorize new resources. Existing EC2 is the selected deployment; optional RDS/CloudFront templates require separate cost and configuration review."
    budgets = report["checks"]["budgets"].get("result")
    report["budget_setup"] = "no_budgets_found" if budgets == [] else "inspect_budget_alerts_in_console; thresholds/credit treatment not verified"
    if any(item["status"] == "blocked_by_scp" for item in report["checks"].values()):
        report["policy_blocker"] = "IAM allows cannot override managed SCP restrictions. Confirm the project's assigned home region in settings.aws.com (CampusShift: us-east-2); regional service calls in us-east-1 are restricted. Do not modify managed policies or activate Advanced Features."
    print(json.dumps(report, indent=2))
    return 0 if report["free_plan_gate"] == "confirmed" and all(item["status"] == "confirmed_read" for item in report["checks"].values()) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-2")
    parser.add_argument("--profile", default="campusshift")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("discover", "preflight"):
        discovery = sub.add_parser(name, help="Read-only account-plan, service, network and quota checks")
        discovery.add_argument("--expected-account", help="Optionally compare STS with the account ID confirmed in your Console")
    sub.add_parser("profile-info", help="Redacted aws configure list output")
    sub.add_parser("plan", help="Offline proposed resources/cost assumptions; no AWS access")
    validate = sub.add_parser("validate")
    validate.add_argument("template", choices=["platform", "frontend"])
    outputs = sub.add_parser("outputs")
    outputs.add_argument("stack")
    change = sub.add_parser("change-set")
    change.add_argument("template", choices=["platform", "frontend"])
    change.add_argument("stack")
    change.add_argument("parameters", type=Path, help="JSON array of ParameterKey/ParameterValue, no secret values")
    change.add_argument("--type", choices=["CREATE", "UPDATE"], default="CREATE")
    execute = sub.add_parser("execute")
    execute.add_argument("stack")
    execute.add_argument("change_set")
    upload = sub.add_parser("upload-frontend")
    upload.add_argument("stack")
    for command in (change, execute, upload):
        command.add_argument("--expected-account", required=True, help="Explicit authorized AWS account ID")
        command.add_argument("--approve-costs", action="store_true", required=True, help="Use only after reviewing resource/cost plan")
    args = parser.parse_args()
    if args.action == "plan":
        if args.region != "us-east-2":
            raise RuntimeError("The EC2 estimate is for the selected Ohio region only")
        print((ROOT / "infrastructure/cost-plan.us-east-2.json").read_text())
        return 0
    if not shutil.which("aws"):
        print("AWS CLI unavailable. Install AWS CLI v2 and use the dedicated campusshift profile. No permissions verified.", file=sys.stderr)
        return 2
    aws = AWS(args.region, args.profile)
    if args.action == "profile-info":
        print(redact_profile_listing(aws.text_call("configure", "list")))
        return 0
    if args.action in {"discover", "preflight"}:
        return discover(aws, args.expected_account)
    identity = require_identity(aws, getattr(args, "expected_account", None))
    if hasattr(args, "approve_costs"):
        if args.region != "us-east-2":
            raise RuntimeError("CampusShift mutations require the confirmed project home region us-east-2")
        require_free_plan(aws)
    if args.action == "validate":
        print(json.dumps(aws.call("cloudformation", "validate-template", "--template-body", f"file://{ROOT / 'infrastructure' / (args.template + '.json')}"), indent=2))
    elif args.action == "outputs":
        print(json.dumps(aws.outputs(args.stack), indent=2))
    elif args.action == "change-set":
        parameters = json.loads(args.parameters.read_text())
        allowed = json.loads((ROOT / "infrastructure" / f"{args.template}.json").read_text())["Parameters"]
        if any(row["ParameterKey"] not in allowed for row in parameters):
            raise RuntimeError("Unknown template parameter; never pass secret values")
        name = "review-" + str(int(time.time()))
        result = aws.call("cloudformation", "create-change-set", "--stack-name", args.stack,
                          "--change-set-name", name, "--change-set-type", args.type,
                          "--template-body", f"file://{ROOT / 'infrastructure' / (args.template + '.json')}",
                          "--parameters", f"file://{args.parameters.resolve()}")
        print(json.dumps(result, indent=2))
        print(f"Review with: aws --profile {args.profile} --region {args.region} cloudformation describe-change-set --stack-name {args.stack} --change-set-name {name}")
        print("Nothing executed. Review replacements, IAM/pass-role restrictions, costs and TLS prerequisites before execution.")
    elif args.action == "execute":
        review = aws.call("cloudformation", "describe-change-set", "--stack-name", args.stack, "--change-set-name", args.change_set)
        if review.get("Status") != "CREATE_COMPLETE" or review.get("ExecutionStatus") != "AVAILABLE":
            raise RuntimeError("Change set is not ready for execution")
        # Replacement/deletion needs a separate operator-reviewed path.
        if any(change["ResourceChange"].get("Action") == "Remove" or change["ResourceChange"].get("Replacement") in {"True", "Conditional"} for change in review.get("Changes", [])):
            raise RuntimeError("Change set can remove/replace resources. Explicit destructive review required; use AWS console after approval")
        print(json.dumps(aws.call("cloudformation", "execute-change-set", "--stack-name", args.stack, "--change-set-name", args.change_set)))
    elif args.action == "upload-frontend":
        values = aws.outputs(args.stack)
        env = {**os.environ, "VITE_API_BASE_URL": ""}
        npm = shutil.which("npm.cmd") if os.name == "nt" else shutil.which("npm")
        if not npm:
            raise RuntimeError("Install Node 22.13+ and npm")
        subprocess.run([npm, "ci"], cwd=ROOT / "frontend", env=env, check=True)
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", env=env, check=True)
        # Upload assets first, index last. Never --delete old hashed assets.
        subprocess.run(aws.command("s3", "sync", str(ROOT / "frontend/dist"), f"s3://{values['AssetsBucket']}/", "--exclude", "index.html", "--cache-control", "public,max-age=31536000,immutable"), env=aws.environment(), check=True)
        subprocess.run(aws.command("s3", "cp", str(ROOT / "frontend/dist/index.html"), f"s3://{values['AssetsBucket']}/index.html", "--cache-control", "no-cache,max-age=0", "--content-type", "text/html"), env=aws.environment(), check=True)
        aws.call("cloudfront", "create-invalidation", "--distribution-id", values["DistributionId"], "--paths", "/index.html", "/")
        print(values["ApplicationUrl"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as error:
        print(f"Deployment stopped: {error}", file=sys.stderr)
        sys.exit(1)
