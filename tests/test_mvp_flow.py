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

    @patch("app.main.is_pick_submission_locked", return_value=False)
    def test_full_season_flow(self, mock_locked):
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
        self.assertIn("max_points", leaderboard[0])
        self.assertIn("max_points_available", leaderboard[0])

        eliminations_response = self.client.get(f"/seasons/{season['id']}/eliminations")
        self.assertEqual(eliminations_response.status_code, 200)
        eliminations = eliminations_response.json()
        self.assertGreater(len(eliminations), 0)
        self.assertEqual(eliminations[0]["star_name"], first_elim)
        self.assertEqual(eliminations[0]["elimination_order"], 1)
        self.assertEqual(eliminations[0]["place_finished"], len(pairings))

    @patch("app.main.is_pick_submission_locked", return_value=False)
    def test_first_elimination_counts_as_last_place_pick(self, mock_locked):
        season_name = f"DWTS-Elim-{uuid4().hex[:8]}"
        season_response = self.client.post("/seasons/bootstrap", json={"name": season_name})
        self.assertEqual(season_response.status_code, 200)
        season_id = season_response.json()["id"]

        pairings_response = self.client.get(f"/seasons/{season_id}/pairings")
        self.assertEqual(pairings_response.status_code, 200)
        pairings = pairings_response.json()
        self.assertGreaterEqual(len(pairings), 3)

        first_elim = pairings[0]["star_name"]
        predictions = [pairing["star_name"] for pairing in pairings if pairing["star_name"] != first_elim]
        predictions.append(first_elim)

        submission_response = self.client.post(
            "/pick-sheets",
            json={
                "name": f"elimination-test-{uuid4().hex[:6]}",
                "season_id": season_id,
                "predictions": predictions,
            },
        )
        self.assertEqual(submission_response.status_code, 200)

        elimination_response = self.client.post(
            "/eliminations",
            json={"season_id": season_id, "star_name": first_elim},
            headers={"X-Admin-Key": "dwts-admin-dev-key"},
        )
        self.assertEqual(elimination_response.status_code, 200)

        leaderboard_response = self.client.get(f"/leaderboard/{season_id}")
        self.assertEqual(leaderboard_response.status_code, 200)
        leaderboard = leaderboard_response.json()
        self.assertEqual(leaderboard[0]["points"], 15)
        self.assertEqual(leaderboard[0]["exact"], 1)
        # 15 from first elimination + (len(pairings)-1)*15 from remaining = len(pairings)*15
        self.assertEqual(leaderboard[0]["max_points_available"], len(pairings) * 15)

    @patch("app.main.is_pick_submission_locked", return_value=False)
    def test_max_points_available_after_eliminations(self, mock_locked):
        season_name = f"DWTS-MaxPts-{uuid4().hex[:8]}"
        season_response = self.client.post("/seasons/bootstrap", json={"name": season_name})
        self.assertEqual(season_response.status_code, 200)
        season_id = season_response.json()["id"]

        pairings_response = self.client.get(f"/seasons/{season_id}/pairings")
        pairings = pairings_response.json()
        n = len(pairings)
        star_names = [p["star_name"] for p in pairings]

        # Sheet 1: predicts [0, 1, 2, ..., n-1] in 1st, 2nd, ..., nth place
        self.client.post(
            "/pick-sheets",
            json={"name": "PlayerForward", "season_id": season_id, "predictions": star_names},
        )
        # Sheet 2: predicts reverse [n-1, ..., 0]
        self.client.post(
            "/pick-sheets",
            json={"name": "PlayerReverse", "season_id": season_id, "predictions": list(reversed(star_names))},
        )

        # Before any eliminations: both players can potentially score n * 15 points
        lb_response = self.client.get(f"/leaderboard/{season_id}")
        lb = {row["player_name"]: row for row in lb_response.json()}
        self.assertEqual(lb["PlayerForward"]["points"], 0)
        self.assertEqual(lb["PlayerForward"]["max_points_available"], n * 15)
        self.assertEqual(lb["PlayerReverse"]["points"], 0)
        self.assertEqual(lb["PlayerReverse"]["max_points_available"], n * 15)

        # Eliminate star_names[0] (first eliminated = nth place)
        # PlayerForward predicted star_names[0] at position 1 (finished n-th, distance n-1 >= 3 => 0 pts).
        # PlayerReverse predicted star_names[0] at position n (finished n-th, distance 0 => 15 pts, Exact=1).
        self.client.post(
            "/eliminations",
            json={"season_id": season_id, "star_name": star_names[0]},
            headers={"X-Admin-Key": "dwts-admin-dev-key"},
        )

        lb_response = self.client.get(f"/leaderboard/{season_id}")
        lb = {row["player_name"]: row for row in lb_response.json()}

        # PlayerReverse got 15 points and can still get remaining (n-1)*15 => total n*15
        self.assertEqual(lb["PlayerReverse"]["points"], 15)
        self.assertEqual(lb["PlayerReverse"]["exact"], 1)
        self.assertEqual(lb["PlayerReverse"]["max_points_available"], n * 15)

        # PlayerForward got 0 points on star_names[0].
        # PlayerForward's remaining predictions are positions 2..n for stars 1..n-1.
        # But available ranks are 1..n-1. Rank n is gone!
        # PlayerForward's max available must be strictly less than n * 15.
        self.assertEqual(lb["PlayerForward"]["points"], 0)
        self.assertEqual(lb["PlayerForward"]["exact"], 0)
        self.assertLess(lb["PlayerForward"]["max_points_available"], n * 15)

    def test_pick_submission_is_rejected_after_deadline(self):
        season_response = self.client.post(
            "/seasons/bootstrap",
            json={"name": f"DWTS-Locked-{uuid4().hex[:8]}"},
        )
        self.assertEqual(season_response.status_code, 200)
        season_id = season_response.json()["id"]

        pairings_response = self.client.get(f"/seasons/{season_id}/pairings")
        self.assertEqual(pairings_response.status_code, 200)
        predictions = [pairing["star_name"] for pairing in pairings_response.json()]

        with patch("app.main.is_pick_submission_locked", return_value=True):
            response = self.client.post(
                "/pick-sheets",
                json={
                    "name": f"locked-test-{uuid4().hex[:6]}",
                    "season_id": season_id,
                    "predictions": predictions,
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn("deadline", response.json()["detail"].lower())

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
        self.assertIn("Emma's DWTS Picks Leaderboard", root_response.text)
        self.assertIn("<html", root_response.text.lower())

        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["message"], "DWTS Picks backend is running")


if __name__ == "__main__":
    unittest.main()
