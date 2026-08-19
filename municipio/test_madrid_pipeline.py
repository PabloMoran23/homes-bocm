"""Pruebas locales del export/ingest de Madrid (sin red)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

POC_ROOT = Path(__file__).resolve().parents[1]
if str(POC_ROOT) not in sys.path:
    sys.path.insert(0, str(POC_ROOT))
if str(POC_ROOT / "db") not in sys.path:
    sys.path.insert(0, str(POC_ROOT / "db"))

from ingest import portal_proyecto_row  # noqa: E402
from municipio.madrid_export import _catalog_row, build_proyectos  # noqa: E402
from municipio.manifest import load_manifest  # noqa: E402


POLY = {
    "type": "Polygon",
    "coordinates": [
        [
            [-3.71, 40.41],
            [-3.70, 40.41],
            [-3.70, 40.42],
            [-3.71, 40.42],
            [-3.71, 40.41],
        ]
    ],
}


class MadridIngestMappingTest(unittest.TestCase):
    def test_sigma_fields_pass_through(self) -> None:
        mapped = portal_proyecto_row(
            {
                "id": "135/2018/00716",
                "titulo": "APE 08.20",
                "fuente": "sigma",
                "fase": "Aprobación inicial",
                "expediente_grupo": "135/2018/00716",
                "sigma_layer_kind": "tramitados_ad",
                "geom_geojson": POLY,
                "lat": 40.415,
                "lon": -3.705,
                "tramitacion": [{"fecha": "2020-01-01", "tramite": "Inicio"}],
            },
            slug="madrid",
            nombre="Madrid",
        )
        assert mapped is not None
        self.assertEqual(mapped["fuente"], "sigma")
        self.assertEqual(mapped["catalog_source"], "sigma")
        self.assertEqual(mapped["fase"], "Aprobación inicial")
        self.assertEqual(mapped["expediente_grupo"], "135/2018/00716")
        self.assertEqual(mapped["sigma_layer_kind"], "tramitados_ad")
        self.assertTrue(mapped["has_geometry"])
        self.assertEqual(mapped["_hijas"]["tramitacion"][0]["tramite"], "Inicio")


class MadridExportTest(unittest.TestCase):
    def test_catalog_row_normalizes_grupo(self) -> None:
        rec = _catalog_row(
            {
                "EXP_TX_NUMERO": "135/2018/716",
                "EXP_TX_DENOM": "APE 08.20",
                "FAS_TX_DENOM": "Aprobación inicial",
                "sigma_layer_kind": "tramitados_ad",
                "has_geometry": True,
            },
            "2026-08-19T00:00:00+00:00",
        )
        assert rec is not None
        self.assertEqual(rec["id"], "135/2018/00716")
        self.assertEqual(rec["fuente"], "sigma")
        self.assertEqual(rec["fase"], "Aprobación inicial")

    def test_export_from_index_and_geojson(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "madrid_ayto_expedientes_index.json"
            geo = root / "madrid_ayto_expedientes_ad.geojson"
            index.write_text(
                json.dumps(
                    {
                        "generatedAt": "2026-08-19T00:00:00+00:00",
                        "expedientes": [
                            {
                                "EXP_TX_NUMERO": "135/2018/00716",
                                "EXP_TX_DENOM": "APE 08.20",
                                "FAS_TX_DENOM": "Aprobación inicial",
                                "sigma_layer_kind": "tramitados_ad",
                                "Enlace": "https://example.test/sigma",
                                "has_geometry": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            geo.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {"EXP_TX_NUMERO": "135/2018/00716"},
                                "geometry": POLY,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch("municipio.madrid_export.SIGMA_INDEX", index),
                patch("municipio.madrid_export.VISOR_JSON", root / "missing.json"),
                patch("municipio.madrid_export.SIGMA_METRICS", root / "missing-metrics.json"),
                patch("municipio.madrid_export.LINKS_JSONL", root / "missing-links.jsonl"),
                patch("municipio.madrid_export.BOCM_CSV", root / "missing.csv"),
                patch("municipio.madrid_export.GEOJSON_SOURCES", (geo,)),
            ):
                rows = build_proyectos()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], "135/2018/00716")
            self.assertEqual(rows[0]["coord_source"], "sigma_ambito")
            self.assertIn("geom_geojson", rows[0])
            self.assertIsNotNone(rows[0].get("lat"))

    def test_manifest_loads(self) -> None:
        m = load_manifest("madrid")
        self.assertEqual(m.slug, "madrid")
        self.assertIn("madrid:MadridAyuntamientoAdapter", m.portal.adapter or "")
        self.assertEqual(m.proyectos.source, "ayuntamiento")


if __name__ == "__main__":
    unittest.main()
