from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anuncios  # noqa: E402


def _rec(n: int, **extra) -> dict:
    return {
        "id": f"gestiona-{n}",
        "fuente": "gestiona",
        "sede": "x.sedelectronica.es",
        "titulo": f"Anuncio {n}",
        "fecha_publicacion": "2026-11-20",
        "clase": "otros",
        "clase_regla": None,
        "clase_version": 1,
        "celdas": {},
        **extra,
    }


@unittest.skipUnless(os.getenv("TEST_ANUNCIOS_DB_URL"), "requires isolated PostgreSQL")
class AnunciosPostgresTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = psycopg2.connect(os.environ["TEST_ANUNCIOS_DB_URL"])
        with self.conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS homes")
            cur.execute("DROP TABLE IF EXISTS homes.anuncio")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.rollback()
        self.conn.close()

    def test_upsert_is_idempotent_and_tracks_withdrawal(self) -> None:
        rows = [_rec(i) for i in range(3)]
        self.assertEqual(anuncios.save_anuncios("x", rows, complete=True, conn=self.conn),
                         {"anuncios": 3, "nuevos": 3, "retirados": 0})
        self.assertEqual(anuncios.save_anuncios("x", rows, complete=True, conn=self.conn),
                         {"anuncios": 3, "nuevos": 0, "retirados": 0})
        self.assertEqual(anuncios.save_anuncios("x", rows[1:], complete=True, conn=self.conn)["retirados"], 1)
        # Una lectura truncada no retira nada.
        self.assertEqual(anuncios.save_anuncios("x", rows[2:], complete=False, conn=self.conn)["retirados"], 0)
        anuncios.save_anuncios("x", rows, complete=False, conn=self.conn)
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM homes.anuncio WHERE retirado_at IS NULL")
            self.assertEqual(cur.fetchone()[0], 3)

    def test_manual_class_and_radar_flag_survive_refresh(self) -> None:
        anuncios.save_anuncios("x", [_rec(1)], complete=True, conn=self.conn)
        with self.conn.cursor() as cur:
            cur.execute("UPDATE homes.anuncio SET clase = 'planeamiento', clase_regla = 'manual', "
                        "visible_radar = true WHERE id = 'gestiona-1'")
        anuncios.save_anuncios("x", [_rec(1, titulo="Nuevo título")], complete=True, conn=self.conn)
        with self.conn.cursor() as cur:
            cur.execute("SELECT titulo, clase, clase_regla, visible_radar FROM homes.anuncio WHERE id = 'gestiona-1'")
            self.assertEqual(cur.fetchone(), ("Nuevo título", "planeamiento", "manual", True))


if __name__ == "__main__":
    unittest.main()
