from __future__ import annotations

import copy
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.los_molinos import LosMolinosAyuntamientoAdapter
from municipio.entity_policy import classify


POLYGON = {
    "type": "Polygon",
    "coordinates": [[[-4.08, 40.71], [-4.07, 40.71], [-4.07, 40.72], [-4.08, 40.71]]],
}
FEATURE = {
    "type": "Feature",
    "properties": {
        "DS_MUNICIPIO": "LOS MOLINOS",
        "CD_UNI": "PG_87_83415_AMB_0000007",
        "DS_NOMB_AMB": "UA-01 LA CERQUILLA",
        "CD_REUR": "83415",
        "FC_BOCM": "2013-04-10",
    },
    "geometry": POLYGON,
}


class LosMolinosSourcesTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.out = Path(directory.name) / "records.jsonl"
        self.state = Path(directory.name) / "state.json"
        self.adapter = LosMolinosAyuntamientoAdapter("los-molinos", {"request_delay_s": 0})
        self.catalogue = {"type": "FeatureCollection", "numberMatched": 1, "features": [copy.deepcopy(FEATURE)]}

    def fetch_during_outage(self, url, data=None):
        if url.startswith(self.adapter.wfs_url):
            return json.dumps(self.catalogue)
        raise urllib.error.URLError(TimeoutError("TCP connect timed out"))

    def test_municipal_outage_uses_sitcm_and_retains_prior_projects(self):
        old = {"id": "published-project", "titulo": "Historical document"}
        self.adapter._write_jsonl(self.out, [old])
        with patch.object(self.adapter, "_fetch", side_effect=self.fetch_during_outage) as fetch:
            result = self.adapter.update_proyectos(self.out, self.state)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["sitcm_ambitos"], 1)
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual({entry["source"] for entry in result["unavailable_sources"]}, {
            "tablon", "transparencia_planeamiento", "web_urbanismo",
        })
        self.assertEqual(json.loads(self.state.read_text())["status"], "partial")
        prior, sector = self.adapter._load_jsonl(self.out)
        self.assertEqual(prior, old)
        self.assertEqual(sector["source"], "sitcm")
        self.assertEqual(sector["exp_numero_original"], "REUR 83415 / PG_87_83415_AMB_0000007")
        self.assertTrue(classify(sector)["activity_eligible"])
        self.assertEqual(sector["geom_geojson"], POLYGON)
        self.assertEqual(sector["geometry_crs"], "EPSG:4326")
        self.assertIn("CQL_FILTER=DS_MUNICIPIO", sector["geometry_source_url"])

        self.catalogue["features"][0]["properties"]["DS_NOMB_AMB"] = "UA-01 LA CERQUILLA — actualizado"
        self.adapter = LosMolinosAyuntamientoAdapter("los-molinos", {"request_delay_s": 0})
        with patch.object(self.adapter, "_fetch", side_effect=self.fetch_during_outage):
            result = self.adapter.update_proyectos(self.out, self.state)
        self.assertEqual(result["added"], 0)
        self.assertEqual(self.adapter._load_jsonl(self.out)[1]["id"], sector["id"])

    def test_licence_outage_keeps_old_records_without_manufacturing_grants(self):
        old = {"id": "published-licence", "fecha_concesion": "2024-01-15"}
        self.adapter._write_jsonl(self.out, [old])
        with patch.object(self.adapter, "_fetch", side_effect=self.fetch_during_outage) as fetch:
            result = self.adapter.update_licencias(self.out, self.state)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["added"], 0)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual({entry["source"] for entry in result["unavailable_sources"]}, {
            "tablon", "web_urbanismo", "catalogo_tramites",
        })
        self.assertEqual(self.adapter._load_jsonl(self.out), [old])

    def test_incomplete_or_empty_sitcm_does_not_advance_prior_state(self):
        old = {"id": "published-project"}
        self.adapter._write_jsonl(self.out, [old])
        self.state.write_text("previous-state")
        for catalogue in (
            {"type": "FeatureCollection", "numberMatched": 2, "features": [FEATURE]},
            {"type": "FeatureCollection", "numberMatched": 0, "features": []},
            {"type": "FeatureCollection", "numberMatched": 1, "features": [None]},
        ):
            self.catalogue = catalogue
            with self.subTest(catalogue=catalogue):
                with patch.object(self.adapter, "_fetch", side_effect=self.fetch_during_outage):
                    with self.assertRaisesRegex(ValueError, "complete, nonempty SITCM catalogue"):
                        self.adapter.update_proyectos(self.out, self.state)
                self.assertEqual(self.adapter._load_jsonl(self.out), [old])
                self.assertEqual(self.state.read_text(), "previous-state")

    def test_outage_does_not_accept_wrong_municipality_or_non_polygon(self):
        for feature, message in (
            ({**FEATURE, "geometry": {"type": "Point", "coordinates": [-4.07, 40.71]}}, "Missing Los Molinos SITCM polygon"),
            ({**FEATURE, "properties": {**FEATURE["properties"], "DS_MUNICIPIO": "MADRID"}}, "Invalid Los Molinos SITCM sector identity"),
        ):
            self.catalogue["features"] = [feature]
            self.adapter = LosMolinosAyuntamientoAdapter("los-molinos", {"request_delay_s": 0})
            with self.subTest(feature=feature):
                with patch.object(self.adapter, "_fetch", side_effect=self.fetch_during_outage):
                    with self.assertRaisesRegex(ValueError, message):
                        self.adapter.backfill_proyectos(self.out)
                self.assertFalse(self.out.exists())

    def test_a_missing_wordpress_page_does_not_disable_the_rest_of_its_host(self):
        document = '<a href="/wp-content/uploads/2026/11/plan-parcial-los-molinos.pdf">Plan</a>'

        def fetch(url, data=None):
            if url.startswith(self.adapter.wfs_url):
                return json.dumps(self.catalogue)
            if "page_id=36668" in url:
                raise urllib.error.HTTPError(url, 404, "missing page", {}, None)
            if "p=40276" in url:
                return document
            return ""

        with patch.object(self.adapter, "_fetch", side_effect=fetch):
            result = self.adapter.backfill_proyectos(self.out)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["wp_docs"], 1)
        self.assertEqual(result["sitcm_ambitos"], 0)
        self.assertEqual(len(result["unavailable_sources"]), 1)
        self.assertEqual(self.adapter._load_jsonl(self.out)[0]["origen"], "urbanismo_wp")
