import importlib.util
from pathlib import Path
import unittest
import httpx

spec = importlib.util.spec_from_file_location("verify_deployment", Path(__file__).parents[1] / "verify_deployment.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RedirectTests(unittest.TestCase):
    def response(self, code, location=""):
        return httpx.Response(code, headers={"location": location},
                              request=httpx.Request("GET", "http://3.133.115.154/api/health"))

    def test_accepts_rejection_or_same_origin_https_redirect(self):
        for code in (301, 302, 307, 308):
            module.verify_plaintext_policy(self.response(code, "https://3.133.115.154/api/health"), "https://3.133.115.154")
        module.verify_plaintext_policy(self.response(403), "https://3.133.115.154")

    def test_rejects_http_cross_origin_or_missing_redirect(self):
        for code, target in [(200, ""), (301, ""), (301, "/api/health"),
                             (301, "https://other.example/api/health"),
                             (301, "https://3.133.115.154/other")]:
            with self.assertRaises(RuntimeError):
                module.verify_plaintext_policy(self.response(code, target), "https://3.133.115.154")
