"""Offline parser/contract tests; no network and no dependency on local evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.a_rua import (
    ARuaAyuntamientoAdapter, CLASSES, parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter
from municipio.entity_policy import classify


def fixture(key="28523"):
    item = {"id": key, "docnome": "ED DA RÚA PIREIRA", "figura": "Estudio de Detalle",
            "fechaaddef": "2022-09-05", "fechabop": "2022-12-12",
            "fechadog": "2022-09-21", "fechanormativabop": "2022-12-12",
            "incidencias_iuris": None}
    detail = {"datos_xerais": {**item, "folder": "ARUA", "menutitle": "Rúa, A",
                              "filesroot": "documentos/urbanismo/"},
              "incidencias_iuris": None,
              "elementos": [{"description": "MEMORIA", "componentes": [
                  {"id": "1", "descripcion": "MEMORIA", "pathesperado": key + "me001.pdf"},
                  {"id": "2", "descripcion": "ANEXO", "pathesperado": key + "me002.pdf"}]}]}
    return item, detail


class ParserTests(unittest.TestCase):
    def test_groups_documents_and_preserves_date_meanings(self):
        item, detail = fixture()
        row = parse_instrument(item, detail, CLASSES[13])
        self.assertEqual(row["fecha_aprob"], "2022-09-05")
        self.assertEqual(row["fecha_publicacion_dog"], "2022-09-21")
        self.assertEqual(row["fecha_publicacion_bop"], "2022-12-12")
        self.assertEqual(len(row["documentos"]), 2)
        self.assertEqual(classify(row)["entity_type"], "documento")
        self.assertFalse(classify(row)["activity_eligible"])
        self.assertIn("/ARUA/documents/28523me001.pdf", row["documentos"][0]["url"])
        for field in ("fecha", "fecha_acuerdo", "lat", "lon", "fase"):
            self.assertNotIn(field, row)

    def test_documents_do_not_leak_between_instruments(self):
        a, da = fixture()
        b, db = fixture("27865")
        first = parse_instrument(a, da, CLASSES[13])
        second = parse_instrument(b, db, CLASSES[13])
        self.assertNotEqual(first["id"], second["id"])
        self.assertFalse({d["url"] for d in first["documentos"]} &
                         {d["url"] for d in second["documentos"]})

    def test_null_documents_and_legal_incidents(self):
        item, detail = fixture()
        item["incidencias_iuris"] = "DENEGADA APROBACION MODIFICACION 1"
        detail["incidencias_iuris"] = [{"descripcion": item["incidencias_iuris"]}]
        detail["elementos"] = None
        row = parse_instrument(item, detail, CLASSES[16])
        self.assertEqual(row["documentos"], [])
        self.assertEqual(row["documentacion_status"], "sin_documentos_en_plataforma")
        self.assertIn("DENEGADA", row["incidencias_inventario"])
        self.assertFalse(row["vigencia_verificada"])

    def test_complete_arrays_no_truncation(self):
        items = [fixture(str(i))[0] for i in range(150)]
        self.assertEqual(len(parse_inventory(items)), 150)
        self.assertEqual(parse_inventory(None), [])
        for payload in ({"data": items, "next": "page2"}, "error", [{}]):
            with self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_reject_other_municipality_or_detail(self):
        item, original = fixture()
        for field, value in (("id", "12"), ("folder", "OTRO"), ("menutitle", "Petín")):
            detail = copy.deepcopy(original)
            detail["datos_xerais"][field] = value
            with self.assertRaises(ValueError):
                parse_instrument(item, detail, CLASSES[13])

    def test_reject_invalid_date_and_document_origin(self):
        item, detail = fixture()
        item["fechaaddef"] = "2022-02-30"
        with self.assertRaises(ValueError):
            parse_instrument(item, detail, CLASSES[13])
        item, detail = fixture()
        detail["datos_xerais"]["filesroot"] = "https://example.org/"
        with self.assertRaises(ValueError):
            parse_instrument(item, detail, CLASSES[13])

    def test_conflicting_duplicates_fail(self):
        item, _ = fixture()
        self.assertEqual(len(parse_inventory([item, item])), 1)
        other = {**item, "docnome": "Different title"}
        with self.assertRaises(ValueError):
            parse_inventory([item, other])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("a-rua")
        raw = load_yaml(manifest.path)
        self.assertEqual((raw["codigo_ine"], raw["nombre"], raw["provincia"]),
                         ("32072", "A Rúa", "Ourense"))
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, ARuaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("requests.Session", side_effect=AssertionError("No licence requests")):
                out = Path(tmp) / "licencias.jsonl"
                adapter.backfill_licencias(out)
                self.assertEqual(out.read_text(), "")

    def test_failed_extraction_preserves_previous_output(self):
        adapter = ARuaAyuntamientoAdapter("a-rua")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proyectos.jsonl"
            out.write_text(json.dumps({"id": "previous"}) + "\n")
            with patch("requests.Session") as session:
                session.return_value.__enter__.return_value.get.side_effect = ValueError("source unavailable")
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(json.loads(out.read_text())["id"], "previous")


if __name__ == "__main__":
    unittest.main()
