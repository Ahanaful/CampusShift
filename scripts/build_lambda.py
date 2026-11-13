"""Build Linux/Python 3.12 x86_64 Lambda ZIP locally; no AWS account operations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import urllib.request
import ssl
import zipfile

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "public.ecr.aws/lambda/python:3.12@sha256:9294b703452e74023eb6fa39a254de942f059cd1812653b1aa819429036e68b1"
CA_URL = "https://truststore.pki.rds.amazonaws.com/us-east-2/us-east-2-bundle.pem"


def main():
    destination = ROOT / ".local/serverless"
    build = destination / ("build-" + uuid4().hex[:12])
    build.mkdir(parents=True)
    ca = build / "rds-us-east-2.pem"
    with urllib.request.urlopen(CA_URL, timeout=30) as response:
        ca.write_bytes(response.read())
    ssl.create_default_context(cadata=ca.read_text())
    # Bind source read-only. Only this new ignored build directory is writable.
    command = "python -m pip install --disable-pip-version-check --no-compile --only-binary=:all: -r /src/backend/requirements.txt -c /src/backend/requirements-lambda.lock --target /out/package"
    subprocess.run(["docker", "run", "--rm", "--platform", "linux/amd64", "--entrypoint", "/bin/sh",
                    "--mount", f"type=bind,source={ROOT},target=/src,readonly",
                    "--mount", f"type=bind,source={build},target=/out", IMAGE, "-c", command], check=True)
    package = build / "package"
    # Source-only allowlist; no .env, credentials, DBs, tests, git or local tools.
    sources = [(ROOT / "backend/app", "app"), (ROOT / "backend/alembic", "alembic"), (ROOT / "scheduler", "scheduler")]
    target = destination / "backend.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file() and not {"__pycache__", "tests"}.intersection(path.parts) and not path.is_symlink():
                archive.write(path, path.relative_to(package).as_posix())
        for source, prefix in sources:
            for path in sorted(source.rglob("*")):
                if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and "tests" not in path.parts and path.suffix in {".py", ".mako"}:
                    archive.write(path, prefix + "/" + path.relative_to(source).as_posix())
        for name in ("main.py", "lambda_handler.py", "lambda_jobs.py", "alembic.ini"):
            archive.write(ROOT / "backend" / name, name)
        archive.write(ca, "certs/rds-us-east-2.pem")
    with zipfile.ZipFile(target) as archive:
        unpacked = sum(item.file_size for item in archive.infolist())
    if unpacked >= 250 * 1024 * 1024:
        raise RuntimeError("ZIP exceeds Lambda's uncompressed 250 MiB quota")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    metadata = {"zip": "backend.zip", "sha256": digest, "code_key": f"backend/{digest}.zip",
                "compressed_bytes": target.stat().st_size, "uncompressed_bytes": unpacked,
                "platform": "linux/amd64", "python": "3.12", "ca_source": CA_URL,
                "ca_sha256": hashlib.sha256(ca.read_bytes()).hexdigest(), "build_image": IMAGE}
    (destination / "backend.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))
    print("Local package built. Nothing uploaded or provisioned.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Lambda packaging failed: {error}", file=sys.stderr)
        sys.exit(1)
