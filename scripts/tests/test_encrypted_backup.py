import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
try:
    import encrypted_backup as tool
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    tool = None


@unittest.skipIf(tool is None, "Install scripts/requirements-backup.txt in the backup environment")
class EncryptionTests(unittest.TestCase):
    def test_round_trip_and_tampering_or_wrong_key_rejected(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        original = b"fictional database bytes"
        encrypted = tool.seal(original, key)
        self.assertNotIn(original, encrypted)
        self.assertEqual(tool.unseal(encrypted, key), original)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(Exception):
            tool.unseal(encrypted, other)
        import json, base64
        data = json.loads(encrypted)
        content = bytearray(base64.b64decode(data["ciphertext"]))
        content[0] ^= 1
        data["ciphertext"] = base64.b64encode(content).decode()
        with self.assertRaises(Exception):
            tool.unseal(json.dumps(data).encode(), key)
