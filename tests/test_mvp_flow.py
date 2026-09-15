import importlib
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import ADMIN_PASSWORD, ADMIN_USERNAME
from app.main import app


def reload_config_module():
    import app.config as config_module
    return importlib.reload(config_module)


class DWTSMVPFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_full_season_flow(self):
        season_name = f"DWTS-Test-{uuid4().hex[:8]}"
        season_response = self.client.post("/seasons/bootstrap", json={"name": season_name})
        self.assertEqual(season_response.status_code, 200)
        season = season_response.json()
        self.assertIn("id", season)

        player_name = f"Aron-{uuid4().hex[:8]}"

        admin_login_response = self.client.post(
            "/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        )
        self.assertEqual(admin_login_response.status_code, 200)

        pairings_response = self.client.get(f"/seasons/{season['id']}/pairings")
        self.assertEqual(pairings_response.status_code, 200)
        pairings = pairings_response.json()
        self.assertGreater(len(pairings), 0)

        predictions = [entry["star_name"] for entry in pairings]
        predictions = predictions[:]
        predictions.reverse()

        pick_response = self.client.post(
            "/pick-sheets",
            json={
                "name": player_name,
                "season_id": season["id"],
                "predictions": predictions,
            },
        )
        self.assertEqual(pick_response.status_code, 200)

        selection_view_response = self.client.get(f"/seasons/{season['id']}/pick-sheets")
        self.assertEqual(selection_view_response.status_code, 200)
        selections = selection_view_response.json()
        self.assertGreater(len(selections), 0)
        self.assertEqual(selections[0]["player_name"], player_name)
        self.assertEqual(len(selections[0]["predictions"]), len(pairings))

        duplicate_pick_response = self.client.post(
            "/pick-sheets",
            json={
                "name": player_name,
                "season_id": season["id"],
                "predictions": predictions,
            },
        )
        self.assertEqual(duplicate_pick_response.status_code, 400)

        first_elim = pairings[0]["star_name"]
        unauthorized_response = self.client.post(
            "/eliminations",
            json={"season_id": season["id"], "star_name": first_elim},
        )
        self.assertEqual(unauthorized_response.status_code, 401)

        authorized_response = self.client.post(
            "/eliminations",
            json={"season_id": season["id"], "star_name": first_elim},
            headers={"X-Admin-Key": "dwts-admin-dev-key"},
        )
        self.assertEqual(authorized_response.status_code, 200)

        selection_view_response = self.client.get(f"/seasons/{season['id']}/pick-sheets")
        self.assertEqual(selection_view_response.status_code, 200)
        selections = selection_view_response.json()
        self.assertTrue(selections)
        first_selection = selections[0]
        self.assertIn("prediction_rows", first_selection)
        eliminated_row = next(
            row for row in first_selection["prediction_rows"] if row["star_name"] == first_elim
        )
        self.assertTrue(eliminated_row["is_eliminated"])

        host_message_response = self.client.get("/site-message")
        self.assertEqual(host_message_response.status_code, 200)
        initial_message = host_message_response.json()["message"]
        self.assertIsInstance(initial_message, str)

        updated_message = "This week’s picks are live — keep it glam and keep it bold."
        update_response = self.client.post(
            "/site-message",
            json={"message": updated_message},
            headers={"X-Admin-Key": "dwts-admin-dev-key"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["message"], updated_message)

        leaderboard_response = self.client.get(f"/leaderboard/{season['id']}")
        self.assertEqual(leaderboard_response.status_code, 200)
        leaderboard = leaderboard_response.json()
        self.assertGreater(len(leaderboard), 0)
        self.assertEqual(leaderboard[0]["player_name"], player_name)
        self.assertGreaterEqual(leaderboard[0]["points"], 0)

        eliminations_response = self.client.get(f"/seasons/{season['id']}/eliminations")
        self.assertEqual(eliminations_response.status_code, 200)
        eliminations = eliminations_response.json()
        self.assertGreater(len(eliminations), 0)
        self.assertEqual(eliminations[0]["star_name"], first_elim)
        self.assertEqual(eliminations[0]["elimination_order"], 1)

    def test_database_url_override_uses_postgres(self):
        original_url = os.environ.get("DATABASE_URL")
        try:
            os.environ["DATABASE_URL"] = "postgresql://user:pass@host:5432/dwts"
            config_module = reload_config_module()
            self.assertEqual(config_module.SQLALCHEMY_DATABASE_URL, "postgresql://user:pass@host:5432/dwts")
        finally:
            if original_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original_url
            reload_config_module()

    def test_postgres_does_not_run_sqlite_legacy_migration(self):
        from app import db as db_module

        with patch.object(db_module.engine, "dialect") as mock_dialect, patch.object(db_module.Base.metadata, "create_all") as mock_create_all:
            mock_dialect.name = "postgresql"
            db_module.ensure_database_schema()
            mock_create_all.assert_called_once_with(bind=db_module.engine)

    def test_root_serves_frontend_and_health_endpoint(self):
        root_response = self.client.get("/")
        self.assertEqual(root_response.status_code, 200)
        self.assertIn("DWTS 2026 Picks", root_response.text)
        self.assertIn("<html", root_response.text.lower())

        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["message"], "DWTS Picks backend is running")


if __name__ == "__main__":
    unittest.main()
