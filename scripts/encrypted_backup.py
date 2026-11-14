"""Encrypted off-server SQLite copies; requires scripts/requirements-backup.txt.

RSA-OAEP wraps a fresh AES-256-GCM key for each backup using the existing SSH
private key's public half. The private key never leaves this computer.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import tempfile
import sqlite_backup
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CONTEXT = b"CampusShift SQLite backup v1"


def key_from_file(path):
    raw = Path(path).read_bytes()
    try:
        key = serialization.load_pem_private_key(raw, password=None)
    except ValueError:
        key = serialization.load_ssh_private_key(raw, password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("An RSA SSH key of at least 2048 bits is required")
    return key


def seal(data, key):
    secret = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    wrapped = key.public_key().encrypt(secret, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=CONTEXT))
    encode = lambda value: base64.b64encode(value).decode("ascii")
    return json.dumps({"version": 1, "key": encode(wrapped), "nonce": encode(nonce),
                       "ciphertext": encode(AESGCM(secret).encrypt(nonce, data, CONTEXT))}).encode()


def unseal(data, key):
    document = json.loads(data)
    if document["version"] != 1:
        raise ValueError("Unknown encrypted backup format")
    decode = lambda value: base64.b64decode(value, validate=True)
    secret = key.decrypt(decode(document["key"]), padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=CONTEXT))
    return AESGCM(secret).decrypt(decode(document["nonce"]), decode(document["ciphertext"]), CONTEXT)


def pull(args):
    directory = sqlite_backup.private_directory(args.directory)
    key = key_from_file(args.identity)
    with sqlite_backup.directory_lock(directory), tempfile.TemporaryDirectory(prefix="campusshift-private-") as temporary:
        snapshot = sqlite_backup.pull(args.host, args.identity, args.remote_directory, Path(temporary), keep=1)
        destination = directory / (snapshot.name + ".enc")
        if destination.exists():
            if destination.is_symlink() or unseal(destination.read_bytes(), key) != snapshot.read_bytes():
                raise ValueError("Existing encrypted backup does not match source")
        else:
            encrypted = seal(snapshot.read_bytes(), key)
            # Verify authenticated decryption before publishing anything.
            if unseal(encrypted, key) != snapshot.read_bytes():
                raise ValueError("Encryption self-check failed")
            pending = directory / ("." + snapshot.name + ".partial")
            try:
                descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(encrypted)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.link(pending, destination)
            finally:
                pending.unlink(missing_ok=True)
        if args.keep < 1:
            raise ValueError("Retain at least one encrypted backup")
        files = [p for p in directory.iterdir() if re.fullmatch(sqlite_backup.NAME.pattern[:-1] + r"\.enc", p.name)
                 and p.is_file() and not p.is_symlink()]
        for old in sorted(files, key=lambda p: p.name, reverse=True)[args.keep:]:
            old.unlink()
        print(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    fetch = sub.add_parser("pull")
    fetch.add_argument("--host", default="ubuntu@3.133.115.154")
    fetch.add_argument("--remote-directory", default="/home/ubuntu/backups/campusshift")
    fetch.add_argument("--directory", type=Path, required=True)
    fetch.add_argument("--identity", type=Path, required=True)
    fetch.add_argument("--keep", type=int, default=30)
    recover = sub.add_parser("restore")
    recover.add_argument("--backup", type=Path, required=True)
    recover.add_argument("--identity", type=Path, required=True)
    recover.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "pull":
            if args.keep < 1:
                raise ValueError("Retain at least one backup")
            pull(args)
        else:
            with tempfile.TemporaryDirectory(prefix="campusshift-private-") as temporary:
                source = Path(temporary) / "decrypted.sqlite3"
                descriptor = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(unseal(args.backup.read_bytes(), key_from_file(args.identity)))
                print(sqlite_backup.restore(source, args.destination))
    except Exception:
        parser.exit(1, "Encrypted backup operation failed; check access, key and integrity.\n")


if __name__ == "__main__":
    main()
