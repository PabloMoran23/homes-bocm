import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from municipio.adapters.villa_de_otura import SOURCE, VillaDeOturaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


ROOT = "https://ayuntamientodeotura.es"
POU = "CONSULTA PREVIA DEL PLAN DE ORDENACIÓN URBANA DE LA VILLA DE OTURA"
PGOM = "CONSULTA PREVIA DEL PLAN GENERAL DE ORDENACIÓN MUNICIPAL DE LA VILLA DE OTURA"


def link(title, path):
    return f'<a href="{path}"><h2>{title}</h2></a>'


def page(body):
    return '<div class="post-content">' + body + '</div>'


class InventoryTests(unittest.TestCase):
    def test_grouping_links_and_exclusions(self):
        html = page(link(POU, "/pou.pdf") + link(POU, "/pou.pdf")
                    + link(POU + " - Anexo", "/pou-anexo.pdf") + link(PGOM, "/pgom.pdf")
                    + link("Solicitud Licencia Obra Mayor", "/solicitud.pdf")
                    + link("Noticias de fiestas", "/fiestas.pdf"))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r["documentos"]) for r in rows], [2, 1])
        self.assertEqual(rows[0]["documentos"][1]["url"], ROOT + "/pou-anexo.pdf")
        self.assertEqual(rows[1]["documentos"][0]["url"], ROOT + "/pgom.pdf")
        for row in rows:
            self.assertEqual(row["codigo_ine"], "18149")
            for key in ("fecha", "fecha_publicacion", "fecha_aprob", "fecha_acuerdo", "lat", "lon"):
                self.assertNotIn(key, row)

    def test_empty_changed_and_external_documents_fail(self):
        for html in ("blocked", page(""), page(link(POU, "https://example.org/p.pdf")), page(link(POU, "/form"))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails(self):
        for nav in ('<a rel="next" href="/2">Más</a>', '<a class="page-numbers" href="/2">2</a>',
                    '<a href="?paged=2">2</a>'):
            with self.subTest(nav=nav), self.assertRaises(ValueError):
                parse_inventory(page(link(POU, "/p.pdf")) + nav)

    def test_real_manifest_and_live_path_with_mock_transport(self):
        manifest = load_manifest("villa-de-otura")
        adapter = load_portal_adapter(manifest)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "proyectos.jsonl"
            with patch.object(adapter, "_fetch", side_effect=[
                SimpleNamespace(text=page(link(POU, "/p.pdf"))), SimpleNamespace(content=b"%PDF-1.7\n")
            ]) as fetch:
                result = adapter.update_proyectos(output, Path(folder) / "state.json")
            self.assertEqual(result["count"], 1)
            self.assertEqual(fetch.call_args_list[0].args, (SOURCE,))
            self.assertEqual(json.loads(output.read_text())["id"], "villa-de-otura-plan-pou")

    def test_bad_pdf_preserves_previous_output_and_licences_disabled(self):
        adapter = VillaDeOturaAyuntamientoAdapter("villa-de-otura")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "out.jsonl"
            output.write_text("previous\n")
            with patch.object(adapter, "_fetch", side_effect=[
                SimpleNamespace(text=page(link(POU, "/p.pdf"))), SimpleNamespace(content=b"<html>error</html>")
            ]), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), "previous\n")
            self.assertTrue(adapter.backfill_licencias(output)["disabled"])
            self.assertEqual(output.read_text(), "")


if __name__ == "__main__":
    unittest.main()
