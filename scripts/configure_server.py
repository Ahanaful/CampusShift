"""Run interactively as root on the NEW Amazon Linux host; never prints secrets.

Deliver the trusted origin TLS files and RDS CA first. Does not create AWS resources.
"""
import argparse
import getpass
import os
from pathlib import Path
import pwd
import re
import secrets
import sys
from urllib.parse import quote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-postgres", action="store_true")
    args = parser.parse_args()
    if os.name != "posix" or os.geteuid() != 0:
        parser.error("Run as root on the deployment host")
    if not sys.stdin.isatty():
        parser.error("An interactive terminal is required for private secret input")
    root = Path("/etc/campusshift")
    root.mkdir(mode=0o755, exist_ok=True)
    if (root / "application.env").exists() or (root / "pgpass").exists():
        parser.error("Configuration already exists; preserve it. Edit securely for an intentional rotation.")
    domain = input("API origin DNS name with trusted TLS certificate: ").strip()
    host = "127.0.0.1" if args.local_postgres else input("RDS endpoint from platform stack outputs: ").strip()
    user = input("PostgreSQL application user: ").strip()
    database = input("Database name [campusshift]: ").strip() or "campusshift"
    if not re.fullmatch(r"[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", domain):
        parser.error("A real DNS name is required; do not use an IP address")
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", host) or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value) for value in (user, database)):
        parser.error("Invalid database host, user or name")
    for path in (root / "tls/fullchain.pem", root / "tls/privkey.pem"):
        if not path.is_file():
            parser.error("Deliver the trusted TLS certificate and private key first")
    if not args.local_postgres and not (root / "rds-ca.pem").is_file():
        parser.error("Install the official RDS CA bundle first")
    password = getpass.getpass("Database password (not echoed): ")
    if not password or "\n" in password or "\r" in password:
        parser.error("A nonempty single-line password is required")
    owner = pwd.getpwnam("campusshift")

    def write(name, content, mode, uid=0):
        target = root / name
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        os.chown(target, uid, owner.pw_gid)

    escaped = password.replace("\\", "\\\\").replace(":", "\\:")
    write("pgpass", f"{host}:5432:{database}:{user}:{escaped}\n", 0o600, owner.pw_uid)
    query = "sslmode=disable" if args.local_postgres else "sslmode=verify-full&sslrootcert=/etc/campusshift/rds-ca.pem"
    url = f"postgresql+psycopg://{quote(user)}@{host}:5432/{quote(database)}?{query}&connect_timeout=5"
    write("application.env", f"APP_ENV=production\nDATABASE_URL='{url}'\nPGPASSFILE=/etc/campusshift/pgpass\nJWT_SECRET={secrets.token_urlsafe(48)}\nJWT_EXPIRE_MINUTES=30\nCORS_ORIGINS=\n", 0o640)
    source = Path(__file__).resolve().parents[1] / "infrastructure/runtime/nginx.conf"
    write("nginx.conf", source.read_text().replace("__API_DOMAIN__", domain), 0o644)
    print("Configuration saved with restricted permissions. No credentials were printed; application not started.")


if __name__ == "__main__":
    main()
