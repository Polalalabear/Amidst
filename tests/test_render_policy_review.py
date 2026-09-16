"""Tests for the review-only render-policy threshold proposal."""

from __future__ import annotations

import unittest

from scripts.finalize_render_policy_v0_1_1 import composition_proposal


def record(camera_id: str, occupancy: float, visible: int) -> dict:
    return {
        "camera_instance_id": camera_id,
        "composition": {
            "largest_single_object_occupancy_ratio": occupancy,
            "valid_visible_stable_id_object_count": visible,
        },
    }


class CompositionProposalTests(unittest.TestCase):
    def test_proposal_remains_non_authoritative_and_flags_either_clause(self) -> None:
        proposal = composition_proposal(
            [
                record("retained", 0.90, 3),
                record("occupancy", 0.96, 4),
                record("visible", 0.80, 2),
            ]
        )
        self.assertEqual(proposal["status"], "PROPOSED")
        self.assertEqual(proposal["decision_effect"], "NONE_UNTIL_HUMAN_CONFIRMATION")
        self.assertEqual(proposal["retained_camera_count"], 1)
        self.assertEqual(proposal["flagged_camera_ids"], ["occupancy", "visible"])


if __name__ == "__main__":
    unittest.main()
