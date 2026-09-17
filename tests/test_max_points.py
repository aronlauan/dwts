import unittest
from app.models import PickEntry
from app.services import (
    compute_max_points_for_sheet,
    compute_score_for_distance,
    solve_max_weight_assignment,
)


class MaxPointsCalculationTests(unittest.TestCase):
    def test_score_for_distance(self):
        # Default / places 7+ (1.0x)
        self.assertEqual(compute_score_for_distance(0, actual_rank=7), 15)
        self.assertEqual(compute_score_for_distance(1, actual_rank=8), 8)
        self.assertEqual(compute_score_for_distance(2, actual_rank=9), 4)
        self.assertEqual(compute_score_for_distance(3, actual_rank=10), 0)

        # Winner / 1st place (3.0x)
        self.assertEqual(compute_score_for_distance(0, actual_rank=1), 45)
        self.assertEqual(compute_score_for_distance(1, actual_rank=1), 24)
        self.assertEqual(compute_score_for_distance(2, actual_rank=1), 12)
        self.assertEqual(compute_score_for_distance(3, actual_rank=1), 0)

        # Podium places 2-3 (2.0x)
        self.assertEqual(compute_score_for_distance(0, actual_rank=2), 30)
        self.assertEqual(compute_score_for_distance(1, actual_rank=3), 16)
        self.assertEqual(compute_score_for_distance(2, actual_rank=2), 8)
        self.assertEqual(compute_score_for_distance(3, actual_rank=3), 0)

        # Semifinals places 4-6 (1.5x)
        self.assertEqual(compute_score_for_distance(0, actual_rank=4), 22)
        self.assertEqual(compute_score_for_distance(1, actual_rank=5), 12)
        self.assertEqual(compute_score_for_distance(2, actual_rank=6), 6)
        self.assertEqual(compute_score_for_distance(3, actual_rank=5), 0)

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
        # 5 pairings: place 1 @ 3.0x = 45, places 2-3 @ 2.0x = 30 each,
        # places 4-5 @ 1.5x = 22 each
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
        self.assertEqual(max_pts, 45 + (2 * 30) + (2 * 22))

    def test_all_eliminations_max_equals_current(self):
        # 3 pairings, all eliminated (place 1 @ 3.0x, places 2-3 @ 2.0x)
        # Pairing 1 predicted 1, finished 1 (Exact, rank 1: 45)
        # Pairing 2 predicted 2, finished 3 (1 off, rank 3: 16)
        # Pairing 3 predicted 3, finished 2 (1 off, rank 2: 16)
        entries = [
            PickEntry(pairing_id=1, predicted_position=1),
            PickEntry(pairing_id=2, predicted_position=2),
            PickEntry(pairing_id=3, predicted_position=3),
        ]
        actual_ranks = {1: 1, 2: 3, 3: 2}
        total_pairings = 3
        points, exact, max_pts = compute_max_points_for_sheet(entries, actual_ranks, total_pairings)
        self.assertEqual(points, 45 + 16 + 16)
        self.assertEqual(exact, 1)
        self.assertEqual(max_pts, points)

    def test_partial_elimination_accounting_for_lost_exact_ranks(self):
        # 4 pairings (1, 2, 3, 4)
        # Pairing 1 predicted 1
        # Pairing 2 predicted 2
        # Pairing 3 predicted 3
        # Pairing 4 predicted 4
        # Pairing 1 was eliminated first, finishing in 4th place.
        # Fixed score for Pairing 1: |1 - 4| = 3 -> 0 pts (regardless of multiplier)
        # Eliminated ranks: {4}
        # Remaining available ranks: {1 (3.0x), 2, 3 (2.0x each)}
        # Active entries: Pairing 2 (pred 2), Pairing 3 (pred 3), Pairing 4 (pred 4)
        #
        # Scoring each entry against each remaining rank:
        #   Pairing 2 (pred 2) -> rank1: 1-off @3.0x = 24 | rank2: exact @2.0x = 30 | rank3: 1-off @2.0x = 16
        #   Pairing 3 (pred 3) -> rank1: 2-off @3.0x = 12 | rank2: 1-off @2.0x = 16 | rank3: exact @2.0x = 30
        #   Pairing 4 (pred 4) -> rank1: 3-off = 0        | rank2: 2-off @2.0x = 8  | rank3: 1-off @2.0x = 16
        #
        # Optimal assignment: Pairing2->rank1 (24), Pairing3->rank3 (30), Pairing4->rank2 (8) = 62
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
        self.assertEqual(max_pts, 62)


if __name__ == "__main__":
    unittest.main()