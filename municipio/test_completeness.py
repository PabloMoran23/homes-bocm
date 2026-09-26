"""Tests de scoring de completitud de scrapers municipales."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import TestCase

from municipio.completeness import (
    band_for,
    freshness,
    row_flags,
    score_from_fill,
    summarize_rows,
)

THIN = {
    "id": "a",
    "titulo": "Aprobación inicial PGOU",
    "fecha": "2024-03-01",
    "url": "https://example.es/anuncio",
    "source": "ayuntamiento",
}

RICH = {
    "id": "b",
    "titulo": "Plan parcial sector UA-07",
    "fecha": "2023-11-02",
    "url": "https://example.es/ua-07",
    "pdf_url": "https://example.es/ua-07.pdf",
    "expte": "UA-07/2023",
    "tipo": "plan parcial",
    "lat": 40.4,
    "lng": -3.7,
    "geom_geojson": {
        "type": "Polygon",
        "coordinates": [[[-3.7, 40.4], [-3.69, 40.4], [-3.69, 40.41], [-3.7, 40.41], [-3.7, 40.4]]],
    },
    "resumen": "El plan parcial ordena el sector UA-07 con 240 viviendas y cesiones de zonas verdes.",
    "num_viviendas": 240,
}


class CompletenessTest(TestCase):
    def test_thin_row_has_no_geometry_or_pdf(self) -> None:
        flags = row_flags(THIN)
        self.assertTrue(flags["titulo"])
        self.assertTrue(flags["fecha"])
        self.assertTrue(flags["url"])
        self.assertFalse(flags["geometry"])
        self.assertFalse(flags["pdf"])
        self.assertFalse(flags["resumen"])

    def test_rich_row_fills_core_fields(self) -> None:
        flags = row_flags(RICH)
        self.assertTrue(flags["geometry"])
        self.assertTrue(flags["pdf"])
        self.assertTrue(flags["expediente"])
        self.assertTrue(flags["coords"])
        self.assertTrue(flags["resumen"])
        self.assertTrue(flags["metrics"])

    def test_title_as_resumen_does_not_count(self) -> None:
        flags = row_flags({**THIN, "resumen": THIN["titulo"]})
        self.assertFalse(flags["resumen"])

    def test_score_rich_beats_thin(self) -> None:
        thin = summarize_rows([THIN])
        rich = summarize_rows([RICH])
        self.assertGreater(rich["score"], thin["score"])
        self.assertEqual(thin["band"], "basico")
        self.assertEqual(rich["band"], "rico")

    def test_empty_is_sin_datos(self) -> None:
        empty = summarize_rows([])
        self.assertEqual(empty["band"], "sin_datos")
        self.assertEqual(empty["score"], 0)

    def test_band_thresholds(self) -> None:
        self.assertEqual(band_for(70, n=1), "rico")
        self.assertEqual(band_for(45, n=1), "medio")
        self.assertEqual(band_for(22, n=1), "basico")
        self.assertEqual(band_for(10, n=1), "fino")
        self.assertEqual(band_for(90, n=0), "sin_datos")

    def test_score_from_fill_full_is_100(self) -> None:
        fill = {k: 1.0 for k in (
            "titulo", "fecha", "url", "coords", "geometry", "pdf",
            "expediente", "tipo", "resumen", "metrics", "visor",
        )}
        self.assertEqual(score_from_fill(fill), 100)

    def test_freshness(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        label, age = freshness(
            last_ingest_at=(now - timedelta(days=2)).isoformat(),
            last_output_at=None,
            status="done",
            has_adapter=True,
            now=now,
        )
        self.assertEqual(label, "fresh")
        self.assertIsNotNone(age)
        label, _ = freshness(
            last_ingest_at=(now - timedelta(days=30)).isoformat(),
            last_output_at=None,
            status="done",
            has_adapter=True,
            now=now,
        )
        self.assertEqual(label, "due")
        label, age = freshness(
            last_ingest_at=None,
            last_output_at=None,
            status="done",
            has_adapter=True,
            now=now,
        )
        self.assertEqual(label, "never")
        self.assertIsNone(age)
        label, _ = freshness(
            last_ingest_at=None,
            last_output_at=None,
            status="failed",
            has_adapter=True,
            now=now,
        )
        self.assertEqual(label, "error")
