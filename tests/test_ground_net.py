"""Tests drive shipped ground_net.plan — no magic ANSWER constants."""
from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ground_net import Station, plan  # noqa: E402


class GroundNetPlanTests(unittest.TestCase):
    def test_plan_meets_capacity_with_eligible_stations(self) -> None:
        r = plan([Station("a", True, 10.0, 60.0)], 50.0)
        self.assertTrue(r["ok"])
        self.assertIn("a", r["stations"])
        self.assertGreaterEqual(r["mbps"], 50.0)

    def test_plan_fails_when_snr_below_threshold(self) -> None:
        r = plan([Station("a", True, 5.0, 100.0)], 50.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["stations"], [])

    def test_failover_lists_unused_eligible(self) -> None:
        r = plan(
            [
                Station("A", True, 12.0, 40.0),
                Station("B", True, 9.0, 30.0),
                Station("C", False, 20.0, 100.0),
            ],
            50.0,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["stations"], ["A", "B"])
        self.assertNotIn("C", r["stations"])


if __name__ == "__main__":
    unittest.main()
