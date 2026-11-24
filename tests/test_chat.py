import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import ADMIN_KEY
from app.main import app

ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


class LiveChatTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        main_module._last_chat_post_by_client.clear()
        # Remember the real on/off state so tests against the configured DB leave it as they found it.
        self.original_enabled = self.client.get("/chat").json()["enabled"]

    def tearDown(self):
        self.client.post("/admin/chat", json={"enabled": self.original_enabled}, headers=ADMIN_HEADERS)

    def post(self, name, body):
        main_module._last_chat_post_by_client.clear()
        return self.client.post("/chat", json={"name": name, "body": body})

    @patch("app.main.is_chat_window_open", return_value=False)
    def test_closed_outside_window(self, _):
        self.assertEqual(self.post("Aron", "hi").status_code, 403)
        state = self.client.get("/chat").json()
        self.assertFalse(state["open"])
        self.assertEqual(state["messages"], [])

    @patch("app.main.is_chat_window_open", return_value=True)
    def test_post_poll_shutdown_and_delete(self, _):
        self.client.post("/admin/chat", json={"enabled": True}, headers=ADMIN_HEADERS)
        name = f"Tester-{uuid4().hex[:6]}"

        created = self.post(name, "  Go Team!  ")
        self.assertEqual(created.status_code, 200)
        message = created.json()
        self.assertEqual(message["body"], "Go Team!")

        polled = self.client.get(f"/chat?after={message['id'] - 1}").json()
        self.assertIn(message["id"], [m["id"] for m in polled["messages"]])
        self.assertEqual(self.client.get(f"/chat?after={message['id']}").json()["messages"], [])

        # Validation and rate limiting
        self.assertEqual(self.post(name, "x" * 301).status_code, 400)
        self.assertEqual(self.post("", "hello").status_code, 422)
        self.assertEqual(self.client.post("/chat", json={"name": name, "body": "one"}).status_code, 200)
        self.assertEqual(self.client.post("/chat", json={"name": name, "body": "two"}).status_code, 429)

        # Admin-only controls
        self.assertEqual(self.client.post("/admin/chat", json={"enabled": False}).status_code, 401)
        self.assertEqual(self.client.delete(f"/chat/{message['id']}").status_code, 401)

        # Shutdown hides messages and blocks posting
        shut = self.client.post("/admin/chat", json={"enabled": False}, headers=ADMIN_HEADERS).json()
        self.assertFalse(shut["enabled"])
        self.assertEqual(self.client.get("/chat").json()["messages"], [])
        self.assertEqual(self.post(name, "still here?").status_code, 403)

        # Reopen, then delete bumps the version so clients reload
        self.client.post("/admin/chat", json={"enabled": True}, headers=ADMIN_HEADERS)
        version_before = self.client.get("/chat").json()["version"]
        self.assertEqual(self.client.delete(f"/chat/{message['id']}", headers=ADMIN_HEADERS).status_code, 200)
        after_delete = self.client.get("/chat").json()
        self.assertEqual(after_delete["version"], version_before + 1)
        self.assertNotIn(message["id"], [m["id"] for m in after_delete["messages"]])
        self.assertEqual(self.client.delete(f"/chat/{message['id']}", headers=ADMIN_HEADERS).status_code, 404)


if __name__ == "__main__":
    unittest.main()
