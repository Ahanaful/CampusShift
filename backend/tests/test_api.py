"""Run from backend/: python -m unittest discover -s tests -v."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "http://localhost:5173"}):
            self.client = TestClient(create_app())
        self.addCleanup(self.client.close)

    def test_health_contract(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy", "application": "CampusShift"})

    def test_welcome(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Welcome to CampusShift!"})

    def test_allowed_frontend_origin(self):
        response = self.client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_other_origin_has_no_cors_permission(self):
        response = self.client.get("/api/health", headers={"Origin": "https://example.com"})
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
