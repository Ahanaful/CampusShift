import importlib.util
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("sqlite_backup", Path(__file__).parents[1] / "sqlite_backup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "live.sqlite3"
        self.db = sqlite3.connect(self.source)
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE records (value TEXT)")
        self.db.execute("INSERT INTO records VALUES ('committed')")
        self.db.commit()

    def test_wal_snapshot_restore_preserves_committed_data_not_pending_writes(self):
        self.db.execute("INSERT INTO records VALUES ('pending')")
        backup = module.backup(self.source, self.root / "backups")
        restored = module.restore(backup, self.root / "recovery" / "restored.sqlite3")
        with closing(sqlite3.connect(restored)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM records").fetchall(), [("committed",)])
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(backup.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.db.execute("SELECT count(*) FROM records").fetchone()[0], 2)

    def test_retention_only_prunes_owned_completed_names(self):
        directory = module.private_directory(self.root / "backups")
        unrelated = directory / "manual.sqlite3"
        unrelated.write_text("keep")
        first = module.backup(self.source, directory, keep=2)
        module.backup(self.source, directory, keep=2)
        module.backup(self.source, directory, keep=2)
        self.assertFalse(first.exists())
        self.assertEqual(len(list(directory.glob("campusshift-*.sqlite3"))), 2)
        self.assertTrue(unrelated.exists())

    def test_never_overwrites_live_file_or_symlink(self):
        backup = module.backup(self.source, self.root / "backups")
        with self.assertRaises((FileExistsError, ValueError)):
            module.restore(backup, self.source)
        directory = module.private_directory(self.root / "restore")
        link = directory / "existing.sqlite3"
        link.symlink_to(self.source)
        with self.assertRaises(FileExistsError):
            module.restore(backup, link)
        destination = directory / "stale.sqlite3"
        Path(str(destination) + "-wal").touch()
        with self.assertRaises(FileExistsError):
            module.restore(backup, destination)

    def test_missing_source_and_corrupt_source_do_not_prune_good_backup(self):
        directory = self.root / "backups"
        good = module.backup(self.source, directory, keep=1)
        missing = self.root / "missing.sqlite3"
        with self.assertRaises(FileNotFoundError):
            module.backup(missing, directory, keep=1)
        self.assertFalse(missing.exists())
        corrupt = self.root / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a database")
        with self.assertRaises(sqlite3.Error):
            module.backup(corrupt, directory, keep=1)
        self.assertTrue(good.exists())
        self.assertFalse(list(directory.glob("*.partial")))

    def test_rejects_shared_backup_directory_and_invalid_retention(self):
        directory = self.root / "shared"
        directory.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            module.backup(self.source, directory)
        with self.assertRaises(ValueError):
            module.backup(self.source, self.root / "backups", keep=0)

    def test_timeout_does_not_publish_partial_backup(self):
        destination = self.root / "timeout.sqlite3"
        with patch.object(module.time, "monotonic", side_effect=[0, 121]):
            with self.assertRaises(TimeoutError):
                module.snapshot(self.source, destination)
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.root.glob("*.partial")))

    def test_empty_restore_input_is_rejected(self):
        empty = self.root / "empty.sqlite3"
        empty.touch()
        with self.assertRaises(ValueError):
            module.restore(empty, self.root / "recovery" / "restored.sqlite3")

    def test_pull_checks_transfer_hash_and_never_publishes_tampered_bytes(self):
        snapshot = module.backup(self.source, self.root / "remote")
        metadata = json.dumps({"name": snapshot.name,
                               "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()})

        def transfer(command, **kwargs):
            if command[0] == "ssh":
                self.assertIn("StrictHostKeyChecking=yes", command)
                return subprocess.CompletedProcess(command, 0, stdout=metadata)
            Path(command[-1]).write_bytes(b"tampered transfer")
            return subprocess.CompletedProcess(command, 0)

        with patch.object(module.subprocess, "run", side_effect=transfer):
            with self.assertRaises(ValueError):
                module.pull("ubuntu@3.133.115.154", self.root / "key.pem",
                            "/home/ubuntu/backups/campusshift", self.root / "offsite")
        self.assertFalse(list((self.root / "offsite").glob("*.sqlite3")))


if __name__ == "__main__":
    unittest.main()
