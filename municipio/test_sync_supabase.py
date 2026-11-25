from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import psycopg2

from municipio.sync_supabase import sync_manifest


class SyncManifestTest(TestCase):
    def test_retries_a_lost_connection_against_the_same_output(self):
        manifest = SimpleNamespace(slug="pajara")
        with (
            patch.dict("os.environ", {"SUPABASE_DB_URL": "test"}),
            patch(
                "municipio.sync_supabase.sync_municipio_output",
                side_effect=[psycopg2.OperationalError("SSL connection closed"), {"status": "ok"}],
            ) as sync,
            patch("municipio.sync_supabase.time.sleep"),
        ):
            self.assertEqual(sync_manifest(manifest), {"status": "ok"})
        self.assertEqual(sync.call_count, 2)
        sync.assert_called_with("pajara", dry_run=False, manifest=manifest)

    def test_propagates_data_errors_without_retrying(self):
        with (
            patch.dict("os.environ", {"SUPABASE_DB_URL": "test"}),
            patch(
                "municipio.sync_supabase.sync_municipio_output",
                side_effect=psycopg2.DataError("bad date"),
            ) as sync,
        ):
            with self.assertRaises(psycopg2.DataError):
                sync_manifest(SimpleNamespace(slug="pajara"))
        sync.assert_called_once()
