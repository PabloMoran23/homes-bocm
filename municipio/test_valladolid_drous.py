from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from municipio.adapters.valladolid import DEFAULT_DROUS_LAYERS, ValladolidAyuntamientoAdapter
from municipio.geography_control import normalize_record


class ValladolidDrousGeographyTest(unittest.TestCase):
    def setUp(self):
        self.adapter = ValladolidAyuntamientoAdapter("valladolid")

    def test_geojson_shape_declares_the_crs_requested_from_arcgis(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[-4.721, 41.642], [-4.720, 41.642], [-4.720, 41.643], [-4.721, 41.642]]],
        }
        boundary = {
            "type": "Polygon",
            "coordinates": [[[-4.8, 41.6], [-4.6, 41.6], [-4.6, 41.7], [-4.8, 41.7], [-4.8, 41.6]]],
        }
        for layer in DEFAULT_DROUS_LAYERS:
            with self.subTest(year=layer["year"]):
                url = self.adapter._drous_query_url(layer["url"], offset=0, count=1, geometry=True)
                params = parse_qs(urlsplit(url).query)
                self.assertEqual(params["f"], ["geojson"])
                self.assertEqual(params["outSR"], ["4326"])
                record = self.adapter._drous_feature_to_licencia(
                    {"properties": {"JOIN_NUMER": "12345"}, "geometry": geom},
                    layer_url=layer["url"], query_url=url, year=layer["year"],
                )
                self.assertEqual(record["geometry_crs"], "EPSG:4326")
                validated = normalize_record(
                    record, municipality="Valladolid",
                    cfg={"municipal_boundary": {"geometry": boundary, "crs": "EPSG:4326", "axis_order": "xy"}},
                )
                self.assertEqual(validated["geography_validation"]["status"], "valid")
                self.assertEqual(validated["geom_geojson"], geom)
                self.assertLess(validated["lon"], 0)
                self.assertGreater(validated["lat"], 40)

    def test_record_without_geometry_does_not_claim_a_crs(self):
        layer = DEFAULT_DROUS_LAYERS[0]
        url = self.adapter._drous_query_url(layer["url"], offset=0, count=1, geometry=True)
        record = self.adapter._drous_feature_to_licencia(
            {"properties": {"JOIN_NUMER": "12345"}},
            layer_url=layer["url"], query_url=url, year=layer["year"],
        )
        self.assertNotIn("geometry_crs", record)
        self.assertIsNone(record["lat"])
        self.assertIsNone(record["lon"])
