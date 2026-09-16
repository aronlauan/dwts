import unittest
from app.models import PickEntry
from app.services import (
    compute_max_points_for_sheet,
    compute_score_for_distance,
    solve_max_weight_assignment,
)


class MaxPointsCalculationTests(unittest.TestCase):
    def test_score_for_distance(self):
        self.assertEqual(compute_score_for_distance(0), 15)
        self.assertEqual(compute_score_for_distance(1), 8)
        self.assertEqual(compute_score_for_distance(2), 4)
        self.assertEqual(compute_score_for_distance(3), 0)
        self.assertEqual(compute_score_for_distance(10), 0)

    def test_solve_max_weight_assignment_empty_and_trivial(self):
        self.assertEqual(solve_max_weight_assignment([]), 0)
        self.assertEqual(solve_max_weight_assignment([[15]]), 15)
        self.assertEqual(solve_max_weight_assignment([[0]]), 0)

    def test_solve_max_weight_assignment_optimal_choice(self):
        # 2x2 matrix where greedy choice might fail if not global
        # Row 0: [15, 8]
        # Row 1: [15, 4]
        # Greedy for row 0 might take col 0 (15), leaving row 1 with col 1 (4) -> total 19
        # Optimal matching is row 0 -> col 1 (8) and row 1 -> col 0 (15) -> total 23
        weights = [[15, 8], [15, 4]]
        self.assertEqual(solve_max_weight_assignment(weights), 23)

    def test_no_eliminations_gives_max_possible_points(self):
        # 5 pairings, none eliminated
        entries = [
            PickEntry(pairing_id=1, predicted_position=1),
            PickEntry(pairing_id=2, predicted_position=2),
            PickEntry(pairing_id=3, predicted_position=3),
            PickEntry(pairing_id=4, predicted_position=4),
            PickEntry(pairing_id=5, predicted_position=5),
        ]
        actual_ranks = {}
        total_pairings = 5
        points, exact, max_pts = compute_max_points_for_sheet(entries, actual_ranks, total_pairings)
        self.assertEqual(points, 0)
        self.assertEqual(exact, 0)
        self.assertEqual(max_pts, 5 * 15)

    def test_all_eliminations_max_equals_current(self):
        # 3 pairings, all eliminated
        # Pairing 1 predicted 1, finished 1 (Exact: 15)
        # Pairing 2 predicted 2, finished 3 (1 off: 8)
        # Pairing 3 predicted 3, finished 2 (1 off: 8)
        entries = [
            PickEntry(pairing_id=1, predicted_position=1),
            PickEntry(pairing_id=2, predicted_position=2),
            PickEntry(pairing_id=3, predicted_position=3),
        ]
        actual_ranks = {1: 1, 2: 3, 3: 2}
        total_pairings = 3
        points, exact, max_pts = compute_max_points_for_sheet(entries, actual_ranks, total_pairings)
        self.assertEqual(points, 15 + 8 + 8)
        self.assertEqual(exact, 1)
        self.assertEqual(max_pts, points)

    def test_partial_elimination_accounting_for_lost_exact_ranks(self):
        # 4 pairings (1, 2, 3, 4)
        # Pairing 1 predicted 1
        # Pairing 2 predicted 2
        # Pairing 3 predicted 3
        # Pairing 4 predicted 4
        # Pairing 1 was eliminated first, finishing in 4th place.
        # Fixed score for Pairing 1: |1 - 4| = 3 -> 0 pts
        # Eliminated ranks: {4}
        # Remaining available ranks: {1, 2, 3}
        # Active entries: Pairing 2 (pred 2), Pairing 3 (pred 3), Pairing 4 (pred 4)
        # For Pairing 2: can match rank 2 (15 pts)
        # For Pairing 3: can match rank 3 (15 pts)
        # For Pairing 4: rank 4 is taken! Can only take rank 1 (dist 3 -> 0 pts)
        # Total max points = 0 + (15 + 15 + 0) = 30
        entries = [
            PickEntry(pairing_id=1, predicted_position=1),
            PickEntry(pairing_id=2, predicted_position=2),
            PickEntry(pairing_id=3, predicted_position=3),
            PickEntry(pairing_id=4, predicted_position=4),
        ]
        actual_ranks = {1: 4}
        total_pairings = 4
        points, exact, max_pts = compute_max_points_for_sheet(entries, actual_ranks, total_pairings)
        self.assertEqual(points, 0)
        self.assertEqual(exact, 0)
        self.assertEqual(max_pts, 30)


if __name__ == "__main__":
    unittest.main()
