"""Pruebas del due-queue de scrapers (sin red ni DB)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import TestCase

from municipio.schedule import due_plan


NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


class DuePlanTest(TestCase):
    def test_never_ingested_comes_first(self) -> None:
        plan = due_plan(
            interval_days=15,
            limit=2,
            slugs=["mostoles", "getafe", "alcala-de-henares"],
            timestamps={
                "mostoles": NOW - timedelta(days=2),
                "getafe": NOW - timedelta(days=20),
            },
            now=NOW,
        )
        picked = [r["slug"] for r in plan["picked"]]
        self.assertEqual(picked, ["alcala-de-henares", "getafe"])
        self.assertEqual(plan["due_total"], 2)
        self.assertEqual(plan["fresh_total"], 1)
        self.assertTrue(any(s["slug"] == "madrid" for s in plan["skipped"]) or "madrid" not in picked)

    def test_madrid_skipped_unless_included(self) -> None:
        plan = due_plan(
            interval_days=15,
            limit=5,
            slugs=["madrid", "mostoles"],
            timestamps={},
            now=NOW,
        )
        self.assertNotIn("madrid", [r["slug"] for r in plan["picked"]])
        forced = due_plan(
            interval_days=15,
            limit=5,
            slugs=["madrid", "mostoles"],
            timestamps={},
            now=NOW,
            include_madrid=True,
        )
        self.assertIn("madrid", [r["slug"] for r in forced["picked"]])

    def test_fresh_not_picked(self) -> None:
        plan = due_plan(
            interval_days=15,
            limit=10,
            slugs=["mostoles"],
            timestamps={"mostoles": NOW - timedelta(days=1)},
            now=NOW,
        )
        self.assertEqual(plan["picked"], [])
        self.assertEqual(plan["fresh_total"], 1)

    def test_force_ignores_timestamp(self) -> None:
        plan = due_plan(
            interval_days=15,
            limit=10,
            slugs=["mostoles"],
            timestamps={"mostoles": NOW - timedelta(days=1)},
            now=NOW,
            force=True,
        )
        self.assertEqual([r["slug"] for r in plan["picked"]], ["mostoles"])
