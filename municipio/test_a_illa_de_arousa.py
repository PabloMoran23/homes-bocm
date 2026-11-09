"""Parser regressions using reduced, genuine SIOTUGA response fragments."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.a_illa_de_arousa import (
    AIllaDeArousaAyuntamientoAdapter, DETAIL, QUERY, inventory_rows, parse_document,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


ROW = {
    "id": "22846", "docnome": "PLAN XERAL DE ORDENACIÓN MUNICIPAL",
    "figura": "Plan Xeral de Ordenación Municipal", "fechaaddef": "2002-02-14",
    "fechabop": "2002-03-07", "fechadog": "2002-02-27",
    "fechanormativabop": "2002-03-07",
}
DETAIL_DATA = {
    "datos_xerais": {
        "id": "22846", "denominacion": "PLAN XERAL DE ORDENACIÓN MUNICIPAL",
        "figura": "Plan Xeral de Ordenación Municipal", "fechaaddef": "2002-02-14",
        "fechabop": "2002-03-07", "fechadog": "2002-02-27",
        "fechanormativabop": "2002-03-07", "fechatextodef": None,
        "menutitle": "Illa de Arousa, A", "filesroot": "documentos/urbanismo/",
        "folder": "ILLADEAROUSA",
    },
    "incidencias_iuris": None,
    "elementos": [
        {"description": "MEMORIA", "componentes": [
            {"pathesperado": "0804me001.pdf", "id": "51054", "descripcion": "MEMORIA XUSTIFICATIVA (1)."},
            {"pathesperado": "0804me002.pdf", "id": "51056", "descripcion": "MEMORIA XUSTIFICATIVA (2)."},
        ]},
        {"description": "NORMATIVA", "componentes": [
            {"pathesperado": "0804no001.pdf", "id": "4079", "descripcion": "NORMATIVA BOP 07/03/2002."},
        ]},
    ],
}


class ParserTests(unittest.TestCase):
    def test_one_instrument_retains_all_components_and_date_roles(self):
        record = parse_document(ROW, DETAIL_DATA, 14)
        self.assertEqual(record["codigo_ine"], "36901")
        self.assertEqual(len(record["documentos"]), 3)
        self.assertEqual(record["fecha_aprob"], "2002-02-14")
        self.assertEqual(record["fecha_publicacion_dog"], "2002-02-27")
        self.assertEqual(record["fecha_publicacion_bop"], "2002-03-07")
        self.assertIsNone(record["fecha_publicacion"])
        self.assertIsNone(record["fecha_acuerdo"])
        self.assertIsNone(record["geometry"])
        self.assertIsNone(record["lat"])
        self.assertFalse(record["publication_ready"])
        self.assertEqual(record["documentos"][2]["url"],
                         "https://siotuga.xunta.gal/siotuga/documentos/urbanismo/ILLADEAROUSA/documents/0804no001.pdf")
        self.assertEqual(record["detail_source"]["iddoc"], "22846")

    def test_missing_dates_are_not_inferred_from_documents(self):
        row, detail = copy.deepcopy(ROW), copy.deepcopy(DETAIL_DATA)
        for field in ("fechaaddef", "fechadog", "fechabop", "fechanormativabop"):
            row[field] = detail["datos_xerais"][field] = None
        record = parse_document(row, detail, 14)
        self.assertIsNone(record["fecha_aprob"])
        self.assertIsNone(record["fecha_publicacion_bop"])

    def test_identity_mismatch_fails(self):
        for field, value in (("id", "999"), ("menutitle", "Vigo"), ("folder", "VIGO")):
            detail = copy.deepcopy(DETAIL_DATA)
            detail["datos_xerais"][field] = value
            with self.assertRaises(ValueError):
                parse_document(ROW, detail, 14)

    def test_missing_downloads_retain_instrument_with_explicit_limitation(self):
        for components in (None, []):
            detail = copy.deepcopy(DETAIL_DATA)
            detail["elementos"] = components
            record = parse_document(ROW, detail, 14)
            self.assertEqual(record["documentos"], [])
            self.assertEqual(record["document_status"], "no_components_in_source")
            self.assertEqual(record["id_origen"], "22846")

    def test_date_conflict_fails(self):
        detail = copy.deepcopy(DETAIL_DATA)
        detail["datos_xerais"]["fechaaddef"] = "2002-03-07"
        with self.assertRaises(ValueError):
            parse_document(ROW, detail, 14)

    def test_unexpected_document_host_fails(self):
        detail = copy.deepcopy(DETAIL_DATA)
        detail["datos_xerais"]["filesroot"] = "https://example.org/"
        with self.assertRaises(ValueError):
            parse_document(ROW, detail, 14)

    def test_complete_array_and_duplicate_handling(self):
        rows = [dict(ROW, id=str(i)) for i in range(25)]
        self.assertEqual(len(inventory_rows(rows)), 25)
        self.assertEqual(inventory_rows([ROW, ROW]), [ROW])
        self.assertEqual(inventory_rows(None), [])
        for invalid in ({"data": [ROW], "next": "page2"}, "login", [{}], [ROW, dict(ROW, docnome="other")]):
            with self.assertRaises(ValueError):
                inventory_rows(invalid)

    def test_full_refresh_consumes_both_sections_and_all_rows(self):
        class Response:
            def __init__(self, url, payload=None):
                self.url = url
                self.payload = payload
                self.content = (b'<select id="idconcello"><option value="36901">Illa de Arousa, A</option></select>'
                                b'<input id="token" value="public-fixture-field">')

            def raise_for_status(self):
                pass

            def json(self):
                return self.payload

        rows = [dict(ROW, id=str(i)) for i in range(25)]

        def post(url, data, timeout):
            if url == QUERY:
                return Response(url, rows if data["idclase"] == 14 else None)
            self.assertEqual(url, DETAIL)
            detail = copy.deepcopy(DETAIL_DATA)
            detail["datos_xerais"]["id"] = data["iddoc"]
            return Response(url, detail)

        with tempfile.TemporaryDirectory() as tmp, patch("municipio.adapters.a_illa_de_arousa.requests.Session") as factory:
            session = factory.return_value.__enter__.return_value
            session.get.side_effect = lambda url, timeout: Response(url)
            session.post.side_effect = post
            out = Path(tmp) / "proyectos.jsonl"
            adapter = AIllaDeArousaAyuntamientoAdapter("a-illa-de-arousa")
            result = adapter.update_proyectos(out, Path(tmp) / "unused-state.json")
            self.assertEqual(result["rows"], 25)
            self.assertEqual(result["class_counts"], {"14": 25, "13": 0})
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 25)
            self.assertEqual(session.post.call_count, 27)

    def test_manifest_loads_and_licences_are_disabled(self):
        manifest = load_manifest("a-illa-de-arousa")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "36901")
        self.assertEqual(manifest.provincia, "Pontevedra")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, AIllaDeArousaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "licencias.jsonl"
            self.assertEqual(adapter.backfill_licencias(out)["rows"], 0)
            self.assertEqual(out.read_text(), "")


if __name__ == "__main__":
    unittest.main()
