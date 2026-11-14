"""Consistent SQLite snapshots and non-overwriting restores (Python stdlib only).

Destinations must be private directories outside the checkout/web root. Source
connections are read-only; the backup API includes committed WAL contents.
"""
import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import shlex
import subprocess
import time
from uuid import uuid4

NAME = re.compile(r"campusshift-\d{8}T\d{12}Z-[0-9a-f]{32}\.sqlite3$")


def private_directory(path):
    path = Path(path).absolute()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Destination directory must be owned by this user with mode 0700")
    return path


@contextmanager
def directory_lock(directory):
    descriptor = os.open(directory / ".sqlite-backup.lock",
                         os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def verify(path):
    path = Path(path).resolve(strict=True)
    with path.open("rb") as handle:
        if handle.read(16) != b"SQLite format 3\x00":
            raise ValueError("Not an initialized SQLite database")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")


def snapshot(source, destination, max_seconds=120):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Refusing to overwrite a destination")
    if any(Path(str(destination) + suffix).exists() or Path(str(destination) + suffix).is_symlink()
           for suffix in ("-wal", "-shm", "-journal")):
        raise FileExistsError("Refusing a destination with existing SQLite sidecars")
    if max_seconds <= 0:
        raise ValueError("Backup deadline must be positive")
    temporary = destination.with_name("." + destination.name + "." + uuid4().hex + ".partial")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    deadline = time.monotonic() + max_seconds

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError("SQLite backup deadline exceeded")

    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(temporary)) as target:
                src.backup(target, pages=256, progress=progress, sleep=0.05)
        verify(temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        # Same-directory hard link publishes atomically and refuses an existing
        # destination, including a symlink introduced after the initial check.
        os.link(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def backup(source, directory, keep=14):
    if keep < 1:
        raise ValueError("Retain at least one backup")
    directory = private_directory(directory)
    with directory_lock(directory):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = snapshot(source, directory / f"campusshift-{stamp}-{uuid4().hex}.sqlite3")
        # Prune only this tool's completed, owned regular files after success.
        prune(directory, keep)
        return path


def prune(directory, keep):
    files = [p for p in directory.iterdir() if NAME.fullmatch(p.name)
             and stat.S_ISREG(p.lstat().st_mode) and p.lstat().st_uid == os.getuid()]
    for old in sorted(files, key=lambda p: p.name, reverse=True)[keep:]:
        old.unlink()


def pull(host, identity, remote_directory, directory, keep=30):
    """Pull the latest completed snapshot over verified SSH; never run a backup remotely."""
    if keep < 1 or not re.fullmatch(r"[a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+", host):
        raise ValueError("Invalid SSH host or retention")
    if not re.fullmatch(r"/[a-zA-Z0-9_./-]+", remote_directory):
        raise ValueError("Use an absolute remote directory without shell characters")
    directory = private_directory(directory)
    code = (
        "import pathlib,re,json,hashlib; "
        f"d=pathlib.Path({remote_directory!r}); "
        f"p=max((p for p in d.iterdir() if re.fullmatch({NAME.pattern!r},p.name) "
        "and p.is_file() and not p.is_symlink()),key=lambda p:p.name); "
        "print(json.dumps({'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))"
    )
    options = ["-i", str(identity), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10"]
    metadata = subprocess.run(["ssh", *options, host, "python3 -c " + shlex.quote(code)],
                              capture_output=True, text=True, check=True, timeout=30)
    data = json.loads(metadata.stdout)
    if not NAME.fullmatch(data["name"]) or not re.fullmatch(r"[0-9a-f]{64}", data["sha256"]):
        raise ValueError("Unexpected backup metadata")
    with directory_lock(directory):
        destination = directory / data["name"]
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or hashlib.sha256(destination.read_bytes()).hexdigest() != data["sha256"]:
                raise ValueError("Existing backup checksum mismatch")
            verify(destination)
            return destination
        temporary = directory / ("." + uuid4().hex + ".partial")
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            subprocess.run(["scp", *options, host + ":" + remote_directory + "/" + data["name"],
                            str(temporary)], check=True, capture_output=True, timeout=180)
            temporary.chmod(0o600)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != data["sha256"]:
                raise ValueError("Transferred backup checksum mismatch")
            verify(temporary)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.link(temporary, destination)
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            prune(directory, keep)
        finally:
            temporary.unlink(missing_ok=True)
        return destination


def restore(source, destination):
    destination = Path(destination).absolute()
    private_directory(destination.parent)
    with directory_lock(destination.parent):
        verify(source)
        return snapshot(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("backup")
    create.add_argument("--database", required=True, type=Path)
    create.add_argument("--directory", required=True, type=Path)
    create.add_argument("--keep", type=int, default=14, help="Keep last N successful snapshots")
    recover = sub.add_parser("restore")
    recover.add_argument("--backup", required=True, type=Path)
    recover.add_argument("--destination", required=True, type=Path,
                         help="New file only; never the existing live database")
    check = sub.add_parser("verify")
    check.add_argument("path", type=Path)
    fetch = sub.add_parser("pull", help="Download latest existing snapshot; no remote writes")
    fetch.add_argument("--host", required=True)
    fetch.add_argument("--identity", required=True, type=Path)
    fetch.add_argument("--remote-directory", default="/home/ubuntu/backups/campusshift")
    fetch.add_argument("--directory", required=True, type=Path)
    fetch.add_argument("--keep", type=int, default=30)
    args = parser.parse_args()
    try:
        if args.action == "backup":
            print(backup(args.database, args.directory, args.keep))
        elif args.action == "restore":
            print(restore(args.backup, args.destination))
        elif args.action == "pull":
            print(pull(args.host, args.identity, args.remote_directory, args.directory, args.keep))
        else:
            verify(args.path)
            print("SQLite integrity: ok")
    except (OSError, ValueError, KeyError, sqlite3.Error, TimeoutError, subprocess.SubprocessError):
        # Database error messages can include data; keep failures sanitized.
        parser.exit(1, "SQLite operation failed; check paths, permissions, integrity and deadline.\n")


if __name__ == "__main__":
    main()
