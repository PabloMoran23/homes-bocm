"""Offline contract tests; live captures are intentionally not test dependencies."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.malpica_de_bergantinos import (
    MalpicaDeBergantinosAyuntamientoAdapter, parse_inventory, parse_instrument,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    row = {"id": "123", "docnome": "UA de prueba", "figura": "Estudio de Detalle",
           "fechaaddef": "2003-02-21", "fechabop": "2003-03-19",
           "fechadog": None, "fechanormativabop": None}
    detail = {"datos_xerais": {**row, "denominacion": row["docnome"],
              "menutitle": "Malpica de Bergantiños", "filesroot": "documentos/urbanismo/",
              "folder": "MALPICADEBERGANTINOS", "fechatextodef": None},
              "incidencias_iuris": None,
              "elementos": [{"description": "MEMORIA", "componentes": [
                  {"id": "1", "pathesperado": "test.pdf", "descripcion": "Memoria"},
                  {"id": "2", "pathesperado": "test.jpg", "descripcion": "Plano"}]}]}
    return row, detail


class MalpicaTests(unittest.TestCase):
    def test_group_documents_dates_and_provenance(self):
        row, detail = fixture()
        record = parse_instrument(row, detail, 13)
        self.assertEqual(record["fecha_aprob"], "2003-02-21")
        self.assertEqual(record["fecha_publicacion_bop"], "2003-03-19")
        self.assertIsNone(record["fecha_publicacion"])
        self.assertIsNone(record["fecha_acuerdo"])
        self.assertEqual(len(record["documentos"]), 2)
        self.assertTrue(record["documentos"][0]["url"].endswith("/MALPICADEBERGANTINOS/documents/test.pdf"))
        self.assertIsNone(record["geometry"])
        self.assertFalse(record["historico"])
        self.assertEqual(record["detail_source"]["iddoc"], "123")

    def test_full_arrays_not_datatables_page_size(self):
        row, _ = fixture()
        payload = [{**row, "id": str(i)} for i in range(27)]
        self.assertEqual(len(parse_inventory(payload)), 27)
        self.assertEqual(len(parse_inventory(payload + payload)), 27)
        self.assertEqual(parse_inventory(None), [])
        for invalid in ({"data": payload, "recordsTotal": 100}, "error", [{}]):
            with self.assertRaises(ValueError):
                parse_inventory(invalid)
        with self.assertRaises(ValueError):
            parse_inventory([row, {**row, "docnome": "conflict"}])

    def test_explicit_missing_documents_and_historical_category(self):
        row, detail = fixture()
        detail["elementos"] = None
        record = parse_instrument(row, detail, 16)
        self.assertTrue(record["historico"])
        self.assertEqual(record["documentos"], [])
        self.assertEqual(record["documentos_status"], "sin_documentos_digitalizados_en_ficha")
        del detail["elementos"]
        with self.assertRaises(ValueError):
            parse_instrument(row, detail, 16)

    def test_reused_file_retains_distinct_catalogue_captions(self):
        row, detail = fixture()
        detail["elementos"][0]["componentes"].append(
            {"id": "3", "pathesperado": "test.pdf", "descripcion": "Another catalogue caption"})
        record = parse_instrument(row, detail, 16)
        self.assertEqual(len(record["documentos"]), 3)
        self.assertEqual(record["documentos"][2]["titulo"], "Another catalogue caption")

    def test_identity_date_and_document_safety(self):
        row, original = fixture()
        for key, value in [("id", "999"), ("menutitle", "Otro municipio"),
                           ("fechaaddef", "2004-01-01"), ("folder", "OTHER")]:
            detail = copy.deepcopy(original)
            detail["datos_xerais"][key] = value
            with self.assertRaises(ValueError):
                parse_instrument(row, detail, 13)
        original["elementos"][0]["componentes"][0]["pathesperado"] = "../other.pdf"
        with self.assertRaises(ValueError):
            parse_instrument(row, original, 13)
        with self.assertRaises(ValueError):
            parse_inventory([{**row, "fechaaddef": "2003-02-30"}])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("malpica-de-bergantinos")
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MalpicaDeBergantinosAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder, patch("requests.Session") as network:
            path = Path(folder) / "licencias.jsonl"
            self.assertEqual(adapter.backfill_licencias(path)["status"], "disabled")
            self.assertEqual(path.read_text(), "")
            network.assert_not_called()

    def test_failure_does_not_replace_previous_snapshot(self):
        adapter = MalpicaDeBergantinosAyuntamientoAdapter("malpica-de-bergantinos")
        with tempfile.TemporaryDirectory() as folder, patch("requests.Session") as session:
            path = Path(folder) / "proyectos.jsonl"
            path.write_text(json.dumps({"existing": True}))
            session.return_value.__enter__.return_value.get.side_effect = RuntimeError("network failure")
            with self.assertRaises(RuntimeError):
                adapter.backfill_proyectos(path)
            self.assertEqual(json.loads(path.read_text()), {"existing": True})


if __name__ == "__main__":
    unittest.main()
