"""Read-only HTTPS checks, plus optional login/role checks with fictional accounts.

Does not create or modify application records. Never prints credentials/tokens/data.
"""
import argparse
import getpass
from urllib.parse import urljoin, urlsplit
import httpx


def verify_plaintext_policy(response, https_origin):
    """Accept rejection or an exact-origin HTTPS redirect, never a downgrade."""
    if response.status_code == 403:
        return
    expected = https_origin.rstrip("/") + "/api/health"
    location = urljoin(str(response.url), response.headers.get("location", ""))
    if response.status_code not in {301, 302, 307, 308} or location != expected:
        raise RuntimeError("Plaintext HTTP must reject requests or redirect to the same HTTPS origin/path")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Trusted HTTPS origin of the existing EC2 application")
    parser.add_argument("--accounts", action="store_true", help="Privately prompt for fictional student/supervisor credentials")
    args = parser.parse_args()
    parts = urlsplit(args.url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}:
        parser.error("Use an HTTPS origin URL without credentials or paths; TLS verification cannot be disabled")
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=30, follow_redirects=False, verify=True) as client:
        def check(path, code=200, headers=None, json_body=None):
            response = client.post(path, headers=headers, json=json_body) if json_body is not None else client.get(path, headers=headers)
            if response.status_code != code:
                raise RuntimeError(f"{path}: expected {code}, received {response.status_code}")
            print(f"PASS {path} ({code})")
            return response
        assert check("/api/health").json()["status"] == "healthy"
        assert check("/api/ready").json()["status"] == "ready"
        assert "text/html" in check("/").headers.get("content-type", "")
        assert "text/html" in check("/student/attendance").headers.get("content-type", "")
        check("/api/students/me/attendance", 401)
        check("/api/supervisor/employees", 401)
        missing = check("/api/not-a-route", 404)
        assert "text/html" not in missing.headers.get("content-type", "")
        with httpx.Client(timeout=15, follow_redirects=False) as plain:
            # No credentials are ever sent in this HTTP policy probe.
            response = plain.get("http://" + parts.netloc + "/api/health")
            verify_plaintext_policy(response, args.url)
        print("PASS plaintext HTTP rejected or redirected securely")
        if args.accounts:
            for role in ("student", "supervisor"):
                email = input(f"Fictional {role} email: ").strip()
                password = getpass.getpass(f"Fictional {role} password: ")
                token = check("/api/auth/login", json_body={"email": email, "password": password}).json()["access_token"]
                auth = {"Authorization": "Bearer " + token}
                assert check("/api/auth/me", headers=auth).json()["role"] == role
                if role == "student":
                    for path in ("/api/students/me/classes", "/api/students/me/availability", "/api/students/me/schedule", "/api/students/me/time-off", "/api/students/me/attendance"):
                        check(path, headers=auth)
                    check("/api/supervisor/employees", 403, headers=auth)
                    check("/api/supervisor/attendance/export.csv", 403, headers=auth)
                else:
                    for path in ("/api/supervisor/employees", "/api/supervisor/locations", "/api/supervisor/requirements", "/api/supervisor/schedules", "/api/supervisor/time-off", "/api/supervisor/attendance", "/api/supervisor/attendance/export.csv"):
                        check(path, headers=auth)
                    check("/api/students/me/attendance", 403, headers=auth)
    print("Read checks complete. Follow docs/aws-deployment.md for write workflows, reboot, restore and browser verification.")


if __name__ == "__main__":
    main()
