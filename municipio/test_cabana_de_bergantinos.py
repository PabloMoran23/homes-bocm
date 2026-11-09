import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.cabana_de_bergantinos import (
    BASE_URL, DOCUMENT_PATH, SOURCE_URL,
    CabanaDeBergantinosAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


PDF = DOCUMENT_PATH + "canduas.pdf"
TITLE = "Proxecto de expropiación dos bens necesarios para a execución da Estrada en CANDUAS."


def inventory(extra="", project=True):
    link = f'<a href="{PDF}">{TITLE}</a>' if project else '<a href="form.pdf">Solicitude de licenza</a>'
    return (f'<h1>Concello de Cabana de Bergantiños</h1><div id="fondoderecha">'
            f'<ul><li><strong>Información pública:</strong><ul><li>{link}{extra}'
            '</li></ul></li></ul></div>')


class CabanaTests(unittest.TestCase):
    def test_groups_documents_and_keeps_unknown_dates_and_geometry(self):
        html = inventory(f'<a href="{DOCUMENT_PATH}planos.pdf">{TITLE} Planos</a>'
                         '<span>[BOP] 14/04/2025</span>')
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["titulo"], TITLE)
        self.assertEqual(len(rows[0]["documentos"]), 2)
        self.assertEqual(rows[0]["fase"], "información pública")
        self.assertEqual(rows[0]["codigo_ine"], "15014")
        for field in ("fecha", "fecha_publicacion", "fecha_aprob", "fecha_acuerdo", "lat", "lon", "geometry"):
            self.assertIsNone(rows[0][field])

    def test_navigation_forms_and_empty_pages_rejected(self):
        for html in ("<h1>Login</h1>", inventory(project=False),
                     f'<a href="{PDF}">{TITLE}</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_never_silently_ignored(self):
        for extra in ('<a rel="next" href="?page=2">Next</a>',
                      '<div class="pagination">2</div>',
                      '<a href="?offset=20">Máis</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(inventory(extra))

    def test_untrusted_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace(PDF, "https://example.org/work.pdf"))

    def test_identity_stable_across_title_and_document_label_changes(self):
        first = parse_inventory(inventory())[0]
        second = parse_inventory(inventory().replace("CANDUAS", "Cánduas"))[0]
        self.assertEqual(first["id"], second["id"])

    def test_live_path_verifies_documents_before_writing(self):
        manifest = load_manifest("cabana-de-bergantinos")
        adapter = CabanaDeBergantinosAyuntamientoAdapter(manifest.slug, manifest.portal.config)
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "projects.jsonl"
            with patch.object(adapter, "_fetch", side_effect=[inventory().encode(), b"%PDF-test"]):
                result = adapter.update_proyectos(output, Path(tmp) / "state.json")
            row = json.loads(output.read_text())
            self.assertEqual(result["rows"], 1)
            self.assertEqual(result["source_urls"], [SOURCE_URL, BASE_URL + PDF])
            self.assertEqual(row["documentos"][0]["bytes"], 9)
            self.assertEqual(len(row["documentos"][0]["sha256"]), 64)
            with patch.object(adapter, "_fetch", side_effect=[inventory().encode(), ValueError("not PDF")]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(Path(tmp) / "failed.jsonl")
            self.assertFalse((Path(tmp) / "failed.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
