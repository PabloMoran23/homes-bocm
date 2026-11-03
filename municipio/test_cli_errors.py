import contextlib
import io
import unittest
from unittest.mock import patch

from municipio.cli import main


class CliErrorsTest(unittest.TestCase):
    def test_failed_sync_returns_nonzero_for_github_actions(self):
        failed = {"steps": {"sync_supabase": {"error": "database unavailable"}}}
        with patch("municipio.cli.run", return_value=failed), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["run", "-m", "madrid", "--step", "sync_supabase"]), 1)

    def test_successful_sync_returns_zero(self):
        with patch("municipio.cli.run", return_value={"steps": {"sync_supabase": {"status": "ok"}}}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["run", "-m", "madrid", "--step", "sync_supabase"]), 0)

    def test_batch_failure_returns_nonzero(self):
        result = {"municipios": {"madrid": {"steps": {"licencias_update": {"error": "403"}}}}}
        with patch("municipio.cli.run_many", return_value=result), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["run", "-m", "madrid", "-m", "getafe"]), 1)
