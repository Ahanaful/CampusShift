# EC2 troubleshooting

Current deployment: `CampusShift-Server` in `us-east-2`, profile `campusshift`. Start with [current status](aws-current-deployment.md) and [EC2 runbook](aws-deployment.md).

| Symptom | Check |
| --- | --- |
| AWS login expired | Refresh with `aws login --profile campusshift --region us-east-2`, then check STS identity. |
| Regional API denied | Confirm Ohio in AWS Settings and the profile; do not use the MCP endpoint Region for EC2 resources. |
| Previously working AWS access suddenly denied | Check AWS Settings > Billing and ask the project owner about a spend limit. Do not broaden managed policies. |
| Browser cannot connect | Verify the instance is running, its current public IP, EC2 health checks, SG rules and Nginx/backend services. Stop/start may change the IP. |
| SSH times out | Confirm the operator IP still matches the restricted SSH rule and the correct key is available; do not open SSH to the world. |
| Frontend loads but API fails | Check Nginx proxy target and the real backend service; `/api/health` tests liveness, not database persistence. |
| Database unavailable | Inspect the host's actual database configuration without printing secrets. Check migrations and backup state before editing data or restarting database processes. |
| HTTPS unavailable | Current verification covers HTTP only. Do not send real credentials over HTTP or disable certificate verification to hide TLS errors. |
| Unexpected credit use | The EC2 baseline is ~$12.84/month before extras. Unlimited CPU credits, traffic and future backup/snapshot storage can add cost. |

Do not run the prepared Amazon Linux setup scripts on the existing Ubuntu host. Do not redeploy removed serverless templates or execute historical change sets. Restore/replacement requires inspection and a data-preserving plan; instance termination deletes its root disk.
