"""Deployment identity and Free Plan safety checks; no AWS access."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("campusshift_aws_tool", ROOT / "scripts/aws_deploy.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class AWSPreflightTests(unittest.TestCase):
    def test_wrong_region_stops_before_mutation(self):
        arguments = ["aws_deploy.py", "--region", "us-east-1", "execute", "campusshift-api", "review-example", "--expected-account", "123456789012", "--approve-costs"]
        with patch.object(sys, "argv", arguments), patch.object(deploy.shutil, "which", return_value="aws"), patch.object(deploy.AWS, "call", return_value={"Account": "123456789012", "Arn": "arn:aws:sts::123456789012:assumed-role/AccountFullAccessRole/session"}) as call:
            with self.assertRaisesRegex(RuntimeError, "home region"):
                deploy.main()
            self.assertEqual(call.call_count, 1)

    def test_destructive_change_set_cannot_execute(self):
        arguments = ["aws_deploy.py", "execute", "campusshift-api", "review-example", "--expected-account", "123456789012", "--approve-costs"]
        for change in ({"Action": "Remove"}, {"Action": "Modify", "Replacement": "Conditional"}):
            replies = [{"Account": "123456789012", "Arn": "arn:aws:sts::123456789012:assumed-role/AccountFullAccessRole/session"},
                       {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE", "accountPlanRemainingCredits": {"amount": 100}},
                       {"Status": "CREATE_COMPLETE", "ExecutionStatus": "AVAILABLE", "Changes": [{"ResourceChange": change}]}]
            with patch.object(sys, "argv", arguments), patch.object(deploy.shutil, "which", return_value="aws"), patch.object(deploy.AWS, "call", side_effect=replies) as call:
                with self.assertRaisesRegex(RuntimeError, "remove/replace"):
                    deploy.main()
                self.assertEqual(call.call_count, 3)

    def test_private_seed_requires_separate_demo_approval(self):
        with patch.object(deploy.getpass, "getpass") as prompt, patch.object(deploy.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "approve-demo-data"):
                deploy.invoke_job(deploy.AWS("us-east-2"), "example-jobs", "seed")
            prompt.assert_not_called()
            run.assert_not_called()

    def test_all_cli_calls_use_named_profile_and_no_ambient_credentials(self):
        aws = deploy.AWS("us-east-1", "campusshift")
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test-value-must-not-pass", "AWS_SECRET_ACCESS_KEY": "test-secret", "AWS_PROFILE": "other"}):
            env = aws.environment()
            self.assertNotIn("AWS_ACCESS_KEY_ID", env)
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            self.assertNotIn("AWS_PROFILE", env)
            self.assertEqual(env["AWS_EC2_METADATA_DISABLED"], "true")
            for operation in (("sts", "get-caller-identity"), ("s3", "cp", "a", "b")):
                command = aws.command(*operation)
                self.assertEqual(command[command.index("--profile") + 1], "campusshift")
        with patch.object(deploy.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"Account":"123456789012"}', "")) as run:
            self.assertEqual(aws.call("sts", "get-caller-identity")["Account"], "123456789012")
            self.assertIn("env", run.call_args.kwargs)

    def test_profile_diagnostic_removes_entire_credential_rows(self):
        output = "region : us-east-1\naccess_key : masked-key-suffix\nsecret_key : masked-secret-suffix\nsession_token : token-value"
        redacted = deploy.redact_profile_listing(output)
        for value in ("masked-key-suffix", "masked-secret-suffix", "token-value"):
            self.assertNotIn(value, redacted)
        self.assertIn("us-east-1", redacted)

    def test_missing_login_stops_before_any_service_checks(self):
        aws = deploy.AWS("us-east-1")
        with patch.object(aws, "call", side_effect=RuntimeError("Unable to locate credentials")) as call, patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(deploy.discover(aws), 1)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(json.loads(output.getvalue())["checks"]["identity"]["status"], "blocked")

    def test_root_and_wrong_account_rejected(self):
        aws = deploy.AWS("us-east-1")
        for identity, expected in [({"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:root"}, None),
                                   ({"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/campusshift-deployer"}, "999999999999")]:
            with patch.object(aws, "call", return_value=identity), self.assertRaises(RuntimeError):
                deploy.require_identity(aws, expected)

    def test_paid_expired_and_empty_credit_accounts_cannot_provision(self):
        aws = deploy.AWS("us-east-1")
        for plan in ({"accountPlanType": "PAID", "accountPlanStatus": "ACTIVE"},
                     {"accountPlanType": "FREE", "accountPlanStatus": "EXPIRED"},
                     {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE", "accountPlanRemainingCredits": {"amount": 0}}):
            with patch.object(aws, "call", return_value=plan), self.assertRaises(RuntimeError):
                deploy.require_free_plan(aws)

    def test_free_plan_preflight_never_calls_mutation_actions(self):
        aws = deploy.AWS("us-east-1")
        def respond(service, operation, *args):
            self.assertTrue(operation.startswith(("get-", "list-", "describe-")))
            if service == "sts":
                return {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/campusshift-deployer"}
            if operation == "get-account-plan-state":
                return {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE", "accountPlanRemainingCredits": {"amount": 100}}
            return []
        with patch.object(aws, "call", side_effect=respond), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(deploy.discover(aws), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["free_plan_gate"], "confirmed")
            self.assertIn("not prove create", report["creation_permissions"])
            self.assertEqual(report["budget_setup"], "no_budgets_found")

    def test_execution_checks_plan_before_executing_change_set(self):
        arguments = ["aws_deploy.py", "--profile", "campusshift", "--region", "us-east-2", "execute", "campusshift-platform", "review-example", "--expected-account", "123456789012", "--approve-costs"]
        with patch.object(sys, "argv", arguments), patch.object(deploy.shutil, "which", return_value="aws"), patch.object(deploy.AWS, "call", side_effect=[
            {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/campusshift-deployer"},
            {"accountPlanType": "PAID", "accountPlanStatus": "ACTIVE"}]) as call:
            with self.assertRaises(RuntimeError):
                deploy.main()
            self.assertEqual(call.call_count, 2)

    def test_explicit_scp_deny_is_reported_as_an_account_policy_blocker(self):
        aws = deploy.AWS("us-east-1")
        def respond(service, operation, *args):
            if service == "sts":
                return {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/campusshift-deployer"}
            raise RuntimeError("AccessDenied with an explicit deny in a service control policy")
        with patch.object(aws, "call", side_effect=respond), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(deploy.discover(aws), 1)
            report = json.loads(output.getvalue())
            self.assertEqual(report["checks"]["vpcs"]["status"], "blocked_by_scp")
            self.assertIn("cannot override", report["policy_blocker"])

    def test_project_managed_role_reaches_plan_gate_without_policy_changes(self):
        arguments = ["aws_deploy.py", "execute", "campusshift-api", "review-example", "--expected-account", "123456789012", "--approve-costs"]
        identity = {"Account": "123456789012", "Arn": "arn:aws:sts::123456789012:assumed-role/AccountFullAccessRole/session"}
        with patch.object(sys, "argv", arguments), patch.object(deploy.shutil, "which", return_value="aws"), patch.object(deploy.AWS, "call", side_effect=[identity, {"accountPlanType": "PAID"}]) as call:
            with self.assertRaisesRegex(RuntimeError, "ACTIVE FREE"):
                deploy.main()
            self.assertEqual(call.call_count, 2)


if __name__ == "__main__":
    unittest.main()
