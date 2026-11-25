import json
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import URLError
from xml.etree import ElementTree as ET

from municipio.adapters.mislata import CATALOGO_TRAMITES, MUNICIPAL_URBANISMO, TABLON_RSS, MislataAyuntamientoAdapter


class MislataSourceCoverageTests(TestCase):
    def setUp(self) -> None:
        self.adapter = MislataAyuntamientoAdapter("mislata", {"request_delay_s": 0})

    def test_both_updates_preserve_history_and_report_only_missing_sede_sources(self) -> None:
        municipality_link = (
            '<a href="/es/administracion/oficina-virtual/urbanismo/obras-mayores">'
            "Solicitud de licencia de obras mayores</a>"
        )
        icv = {"url": "https://example.org/icv", "titulo": "Planeamiento", "origen": "icv_wfs"}
        drupal = {"url": "https://www.mislata.es/es/plan", "titulo": "Proyecto de urbanización", "origen": "drupal_transparencia"}
        previous = {"id": "previous-sede-notice", "origen": "tablon_rss", "url": TABLON_RSS}
        with (
            TemporaryDirectory() as directory,
            patch.object(self.adapter, "_fetch", return_value=municipality_link) as fetch,
            patch.object(self.adapter, "_attach_geometry"),
            patch.object(self.adapter, "_collect_icv_wfs", return_value=[icv]),
            patch.object(self.adapter, "_crawl_transparencia_pages", return_value=[drupal]),
            patch("municipio.adapters.mislata.read_response", side_effect=TimeoutError("hosted timeout")) as read,
        ):
            for kind, expected, gaps in (
                ("proyectos", {"icv_wfs", "drupal_transparencia"}, {TABLON_RSS}),
                ("licencias", {"drupal_tramite"}, {TABLON_RSS, CATALOGO_TRAMITES}),
            ):
                with self.subTest(kind=kind):
                    path = Path(directory) / f"{kind}.jsonl"
                    state = Path(directory) / f"{kind}.state.json"
                    self.adapter._write_jsonl(path, [previous])

                    result = getattr(self.adapter, f"update_{kind}")(path, state)
                    rows = self.adapter._load_jsonl(path)

                    self.assertIn(previous, rows)
                    self.assertEqual({row["origen"] for row in rows}, expected | {"tablon_rss"})
                    self.assertEqual(result["status"], "partial")
                    self.assertEqual({gap["url"] for gap in result["unavailable_sources"]}, gaps)
                    self.assertEqual(json.loads(state.read_text())["source_coverage"]["status"], "partial")
            fetch.assert_called_once_with(MUNICIPAL_URBANISMO)
            self.assertEqual(read.call_count, 3)
            self.assertTrue(all(c.kwargs == {"timeout": 15, "attempts": 2} for c in read.call_args_list))

    def test_mandatory_web_wfs_and_unlisted_urls_fail(self) -> None:
        with patch.object(self.adapter, "_fetch", side_effect=URLError("unavailable")):
            with self.assertRaises(URLError):
                self.adapter._collect_tramites()
            with self.assertRaises(URLError):
                self.adapter._crawl_transparencia_pages()
            with self.assertRaises(URLError):
                self.adapter._collect_icv_wfs()
        with patch("municipio.adapters.mislata.read_response", side_effect=TimeoutError("unavailable")):
            with self.assertRaises(TimeoutError):
                self.adapter._read_sede("https://example.org/unrelated-feed")

    def test_empty_regional_or_municipal_sources_are_not_complete(self) -> None:
        empty_wfs = '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"/>'
        with patch.object(self.adapter, "_fetch", return_value=empty_wfs):
            with self.assertRaisesRegex(ValueError, "No verifiable Mislata"):
                self.adapter._collect_icv_wfs()
            with self.assertRaisesRegex(ValueError, "No verifiable urban planning procedures"):
                self.adapter._collect_tramites()
        self.assertIsNone(self.adapter._wfs_cache)

    def test_rss_uses_xml_encoding_when_the_http_header_disagrees(self) -> None:
        payload = (
            '<?xml version="1.0" encoding="iso-8859-1"?>'
            "<rss><channel><item><title>Información pública</title>"
            "<link>https://example.org/notice</link></item></channel></rss>"
        ).encode("iso-8859-1")
        headers = Message()
        headers["Content-Type"] = "text/xml; charset=utf-8"
        with patch("municipio.adapters.mislata.read_response", return_value=(payload, headers)):
            rows, unavailable = self.adapter._collect_tablon_rss()
        self.assertEqual(unavailable, [])
        self.assertEqual(rows[0]["titulo"], "Información pública")

    def test_wfs_declares_normalized_longitude_latitude_coordinates(self) -> None:
        member = ET.fromstring(
            '<wfs:member xmlns:wfs="http://www.opengis.net/wfs/2.0" '
            'xmlns:ms="http://mapserver.gis.umn.edu/mapserver" xmlns:gml="http://www.opengis.net/gml">'
            '<ms:InventarioSuSuz><ms:cod_ine_mun>46169</ms:cod_ine_mun><ms:id>3951</ms:id>'
            '<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>'
            '39.47 -0.42 39.47 -0.421 39.471 -0.421 39.47 -0.42'
            '</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></ms:InventarioSuSuz></wfs:member>'
        )
        row = self.adapter._parse_wfs_member(member, layer="InventarioSuSuz")
        self.assertIsNotNone(row)
        assert row is not None
        record = self.adapter._to_proyecto(row)
        self.assertEqual(record["geom_geojson"]["coordinates"][0][0], [-0.42, 39.47])
        self.assertEqual(record["geometry_crs"], "EPSG:4326")
        self.assertEqual(record["coordinates_crs"], "EPSG:4326")
        self.assertEqual(record["geometry_axis_order"], "xy")
