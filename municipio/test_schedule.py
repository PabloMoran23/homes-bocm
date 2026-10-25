"""Pruebas del due-queue de scrapers (sin red ni DB)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import multiprocessing
import os
import signal
import time
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from municipio.schedule import _run_bounded, due_plan, run_due


NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


class DuePlanTest(TestCase):
    def test_failed_refresh_remains_partial_and_next_municipio_runs(self) -> None:
        plan = due_plan(slugs=["oviedo", "leon"], timestamps={}, dead_letters=set(), now=NOW)
        error = "https://example.org/urbanismo: timeout after 3 attempts"
        with patch("municipio.schedule.due_plan", return_value=plan), patch(
            "municipio.schedule.load_manifest"
        ), patch("municipio.schedule._run_bounded", side_effect=[
            {"steps": {"proyectos_update": {"error": error, "type": "TimeoutError"}}},
            {"steps": {"proyectos_update": {"rows": 1}}},
        ]), patch("ingest.release_dead_letter"):
            result = run_due()
        self.assertEqual(result["status"], "partial")
        self.assertEqual((result["ok"], result["failed"]), (1, 1))
        self.assertEqual(result["results"][0]["steps"]["proyectos_update"]["error"], error)
        self.assertTrue(result["results"][1]["ok"])

    def test_real_timeout_stops_worker_parks_municipio_and_continues(self) -> None:
        plan = due_plan(slugs=["oviedo", "leon"], timestamps={}, dead_letters=set(), now=NOW)
        children = {child.pid for child in multiprocessing.active_children()}

        def runner(manifest, step):
            if manifest.slug == "oviedo":
                time.sleep(60)
            return {"steps": {"proyectos_update": {"rows": 1}}}

        with patch("municipio.schedule.due_plan", return_value=plan), patch(
            "municipio.schedule.load_manifest", side_effect=lambda slug: SimpleNamespace(slug=slug)
        ), patch("municipio.schedule.run", side_effect=runner), patch(
            "ingest.park_dead_letter"
        ) as park, patch("ingest.release_dead_letter") as release:
            result = run_due(timeout_seconds=.2)
        park.assert_called_once()
        self.assertEqual(park.call_args.args, ("oviedo",))
        self.assertEqual(park.call_args.kwargs["step"], "schedule_timeout")
        self.assertIn("0.2 seconds", park.call_args.kwargs["error"])
        self.assertEqual(result["results"][0]["retry"], "dead_letter")
        self.assertEqual((result["ok"], result["failed"], result["status"]), (1, 1, "partial"))
        release.assert_called_once_with("leon")
        self.assertEqual({child.pid for child in multiprocessing.active_children()}, children)

    def test_worker_ignoring_termination_is_killed(self) -> None:
        def stubborn(*args):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(60)
        with patch("municipio.schedule.load_manifest"), patch("municipio.schedule.run", side_effect=stubborn):
            with self.assertRaisesRegex(TimeoutError, "municipio_timeout"):
                _run_bounded("oviedo", "update", .2)

    def test_worker_crash_does_not_report_success(self) -> None:
        with patch("municipio.schedule.load_manifest"), patch(
            "municipio.schedule.run", side_effect=lambda *args: os._exit(7)
        ):
            with self.assertRaisesRegex(RuntimeError, "municipio_worker_exit: oviedo: 7"):
                _run_bounded("oviedo", "update", 5)

    def test_dlq_failure_is_reported_and_next_municipio_runs(self) -> None:
        plan = due_plan(slugs=["oviedo", "leon"], timestamps={}, dead_letters=set(), now=NOW)
        with patch("municipio.schedule.due_plan", return_value=plan), patch(
            "municipio.schedule._run_bounded", side_effect=[TimeoutError("municipio_timeout"), {"steps": {}}]
        ), patch("ingest.park_dead_letter", side_effect=RuntimeError("DB unavailable")), patch("ingest.release_dead_letter"):
            result = run_due()
        self.assertEqual(result["results"][0]["dead_letter_error"], "DB unavailable")
        self.assertNotIn("retry", result["results"][0])
        self.assertEqual((result["ok"], result["failed"]), (1, 1))

    def test_invalid_timeout_rejected_before_planning(self) -> None:
        for value in (0, -1, float("inf"), float("nan")):
            with self.subTest(value=value), patch("municipio.schedule.due_plan") as plan:
                with self.assertRaises(ValueError):
                    run_due(timeout_seconds=value)
                plan.assert_not_called()

    def test_cli_converts_timeout_minutes_to_seconds(self) -> None:
        from municipio.cli import main
        with patch("municipio.schedule.run_due", return_value={"failed": 0}) as runner:
            self.assertEqual(main(["schedule", "run", "--timeout-minutes", "12.5", "--dry-run"]), 0)
        self.assertEqual(runner.call_args.kwargs["timeout_seconds"], 750)

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
            dead_letters=set(),
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
            dead_letters=set(),
        )
        self.assertNotIn("madrid", [r["slug"] for r in plan["picked"]])
        forced = due_plan(
            interval_days=15,
            limit=5,
            slugs=["madrid", "mostoles"],
            timestamps={},
            now=NOW,
            include_madrid=True,
            dead_letters=set(),
        )
        self.assertIn("madrid", [r["slug"] for r in forced["picked"]])

    def test_fresh_not_picked(self) -> None:
        plan = due_plan(
            interval_days=15,
            limit=10,
            slugs=["mostoles"],
            timestamps={"mostoles": NOW - timedelta(days=1)},
            now=NOW,
            dead_letters=set(),
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
            dead_letters=set(),
        )
        self.assertEqual([r["slug"] for r in plan["picked"]], ["mostoles"])

    def test_dead_letter_is_not_picked_unless_forced(self) -> None:
        plan = due_plan(
            interval_days=15,
            limit=5,
            slugs=["oviedo", "leon"],
            timestamps={},
            now=NOW,
            dead_letters={"oviedo"},
        )
        self.assertEqual([r["slug"] for r in plan["picked"]], ["leon"])
        self.assertEqual(plan["skipped"][0]["reason"], "dead_letter")
        forced = due_plan(
            interval_days=15,
            limit=5,
            slugs=["oviedo"],
            timestamps={},
            now=NOW,
            force=True,
            dead_letters={"oviedo"},
        )
        self.assertEqual([r["slug"] for r in forced["picked"]], ["oviedo"])
