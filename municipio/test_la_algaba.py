"""Offline parser/adapter contract tests; no network or external fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.la_algaba import SOURCE, LaAlgabaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def fixture(documents, extra=""):
    links = "".join(
        f'<tr><td><a href="https://laalgaba.sedelectronica.es/preview-document/'
        f'00000000-0000-0000-0000-{number:012d}">{title}</a></td></tr>'
        for number, title in documents
    )
    return ('<h2>7.1. PLANEAMIENTO URBANÍSTICO/PGOU</h2>'
            '<table class="TransparencyListPanel">' + links + '</table>' + extra)


DOCUMENTS = [
    (1, "NORMAS_URBANISTICAS"), (2, "Planos PGOU"), (3, "MEMORIA GENERAL"),
    (4, "Documento de Reformado de Modificacion Puntual del PGOU nº 3.Diligenciado"),
    (5, "Documento Reformado de Modificación Puntual nº 3 del PGOU"),
]


class LaAlgabaTests(unittest.TestCase):
    def test_groups_all_documents_by_instrument(self):
        rows = parse_inventory(fixture(DOCUMENTS + [DOCUMENTS[0]]))
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r["documentos"]) for r in rows], [3, 2])
        self.assertEqual(rows[1]["id"], "la-algaba-pgou-modificacion-3-reformado")
        for row in rows:
            self.assertEqual(row["codigo_ine"], "41007")
            self.assertEqual(row["provincia"], "Sevilla")
            self.assertEqual(row["inventory_url"], SOURCE)
            for field in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "fase"):
                self.assertNotIn(field, row)
            self.assertFalse(row["publication_ready"])

    def test_distinct_modification_is_not_folded_into_number_three(self):
        rows = parse_inventory(fixture(DOCUMENTS + [(6, "Documento Reformado de Modificación Puntual nº 4 del PGOU")]))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[-1]["documentos"]), 1)

    def test_reject_empty_wrong_folder_and_login(self):
        for html in (fixture([]), "<h1>Identifícate</h1>", fixture(DOCUMENTS).replace("/PGOU", "/OTRA")):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_never_silently_truncates_pagination(self):
        for control in ('<button>Mostrar más</button>', '<a rel="next">2</a>', '<input value="Siguiente">'):
            with self.subTest(control=control), self.assertRaises(ValueError):
                parse_inventory(fixture(DOCUMENTS, control))

    def test_unsupported_documents_require_review(self):
        for title in ("Solicitud licencia obras", "Licitación redacción PGOM", "Noticias", "ESTUDIO DE DETALLE"):
            with self.subTest(title=title), self.assertRaises(ValueError):
                parse_inventory(fixture(DOCUMENTS + [(7, title)]))
        with self.assertRaises(ValueError):
            parse_inventory(fixture(DOCUMENTS).replace("https://laalgaba.sedelectronica.es/preview-document/", "https://example.org/preview-document/"))

    def test_adapter_live_response_contract_and_atomic_failure(self):
        adapter = LaAlgabaAyuntamientoAdapter("la-algaba")
        response = Mock(url=SOURCE, text=fixture(DOCUMENTS))
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "proyectos.jsonl"
            with patch("municipio.adapters.la_algaba.requests.get", return_value=response):
                result = adapter.backfill_proyectos(output)
                self.assertEqual(result["count"], 2)
                self.assertEqual(result["documents"], 5)
                previous = output.read_text()
                self.assertEqual(len([json.loads(line) for line in previous.splitlines()]), 2)
                response.text = fixture(DOCUMENTS, "<button>Mostrar más</button>")
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(folder) / "state.json")
                self.assertEqual(output.read_text(), previous)
                response.text = fixture(DOCUMENTS)
                response.url = "https://example.org/"
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            licences = Path(folder) / "licencias.jsonl"
            self.assertTrue(adapter.backfill_licencias(licences)["disabled"])
            self.assertEqual(licences.read_text(), "")

    def test_manifest(self):
        manifest = load_manifest("la-algaba")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "41007")
        self.assertEqual(manifest.provincia, "Sevilla")
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertEqual(manifest.portal.adapter, "municipio.adapters.la_algaba:LaAlgabaAyuntamientoAdapter")


if __name__ == "__main__":
    unittest.main()
