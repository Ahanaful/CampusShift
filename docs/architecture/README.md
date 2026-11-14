# CampusShift deployed architecture

Generated November 13, 2026, using Python diagrams 0.25.1 and Graphviz 16.1.1.

- `campusshift-architecture.png`: 9391 × 3100 pixels, 300 DPI.
- `campusshift-architecture.svg`: scalable layout with embedded AWS icon images.
- `campusshift_architecture.py`: reproducible source; no AWS operations.
- `repository-inventory.json`: paths, line counts and SHA-256 fingerprints of the 131 tracked text files read during repository inspection.

## Live AWS evidence

`aws sts get-caller-identity --profile campusshift` succeeded for account
548280227313 using the existing diagram-reader identity. No credentials or secret
values were read or saved. Subsequent commands were `aws ec2 describe-<resource>
--profile campusshift --region us-east-2 --output json`, for instances,
security-groups, vpcs, subnets, route-tables, internet-gateways, network-acls,
nat-gateways, addresses and volumes. The instances query selected only inventory
fields; no user data was requested. No write commands were used.

| Resource | Verified configuration |
| --- | --- |
| EC2 | CampusShift-Server, i-0b662a28fc2d1aeaf, running t3.micro |
| Addresses | Public 3.133.115.154; private 172.31.7.136; no Elastic IP returned |
| VPC | vpc-037fd02904c677068, default, 172.31.0.0/16 |
| Workload subnet | subnet-04f8e92b45880a336, 172.31.0.0/20, us-east-2a, public IP mapping enabled |
| Other subnets | 172.31.16.0/20 in us-east-2b; 172.31.32.0/20 in us-east-2c; no workload instances returned there |
| Main route table | rtb-029b4811950e603b4; local VPC route and active 0.0.0.0/0 route to IGW; no explicit subnet association, so main table applies |
| Internet Gateway | igw-0e40f27c2e32899b8, attached to workload VPC |
| Attached security group | sg-0c293c3a0ee64fd10 / launch-wizard-1; inbound TCP 80 and 443 from 0.0.0.0/0, SSH 22 from a single administrator IPv4 /32; unrestricted IPv4 egress; no IPv6 ingress |
| Default SG | sg-03e385ad9819b32d6; self-referencing inbound, unrestricted IPv4 egress; not attached to instance |
| Network ACL | acl-00fcb79dd1114bba9, attached to all three subnets; rule 100 permits all IPv4 inbound/outbound, followed by default deny |
| EBS | vol-02dd0fbe1cd9a0e52, attached /dev/sda1 root volume, 20 GiB gp3, 3000 IOPS / 125 MiB/s, unencrypted, delete on termination enabled |
| NAT Gateways | None returned in region |

The diagram shows workload resources rather than unused default subnets or the
unattached default security group. It does not assert that other AWS services are
absent: no account-wide service inventory was performed.

## Comparison with repository evidence

The current [README](../../README.md), [EC2 runbook](../aws-deployment.md), and
[verification report](../aws-ec2-verification.md) identify this exact EC2 instance,
public IP, region, type and disk size. Those resource claims are now corroborated
by live AWS reads. The report's previously unverified networking and encryption
questions are resolved by the inventory above. Public port 443 permission does
not establish a working HTTPS listener or certificate.

The runbook documents Nginx serving the React/Vite production build from
`/var/www/campusshift`, proxying `/api/` to FastAPI/Uvicorn on loopback port 8000,
with systemd and a SQLite file on EC2 storage. The verification report observed
Nginx HTTP headers, SPA HTML delivery and FastAPI health/authentication responses.
The frontend package/Vite config and API client support React/Vite and same-origin
`/api` requests; Vite's development server is not drawn as a production process.
Backend settings and SQLAlchemy session code support SQLite, but a local default
is not proof of effective live configuration.

Accordingly, frontend implementation, Uvicorn/systemd, loopback binding and SQLite
are marked as documentation-supported software, not independently inspected host
state. No SSH session, database inspection or fresh HTTP probe was performed.
The deployed revision and exact SQLite filename remain unknown.

Infrastructure templates and runtime files describe separate proposed designs:
EC2/RDS/S3/CloudFront and Lambda/API Gateway/Aurora, with optional logging and
related IAM resources. They are not deployment evidence and are excluded. In
particular, the repository's TLS Nginx/runtime files must not be confused with
configuration read from this existing host. No application, configuration,
deployment, or infrastructure files were changed.

## Reproduce and visual validation

Install Graphviz and use an isolated Python environment with `diagrams==0.25.1`
and `graphviz==0.20.3`, then run:

```sh
python docs/architecture/campusshift_architecture.py
```

Source locates exports relative to itself. AWS icons come from diagrams' bundled
AWS assets; software components use plain boxes rather than incorrect AWS icons.
Labels were centered and boxes enlarged after inspecting the initial PNG. The
revised PNG was visually inspected at 1800 pixels wide: no overlapping labels or
clipped elements were observed. SVG was parsed successfully and its icon links
were checked for embedded data URLs. Only docs/architecture artifacts were added;
the pre-existing untracked .DS_Store was left untouched.
