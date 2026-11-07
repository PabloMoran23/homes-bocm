import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from municipio.adapters.alguazas import AlguazasAyuntamientoAdapter, SOURCE_URL, parse_inventory
from municipio.manifest import load_manifest


def block(title, *links):
    return ('<div class="av_promobox"><div class="avia-promocontent">'
            + title + '</div>' + ''.join(f'<a href="{url}">Descargar</a>' for url in links) + '</div>')


ZIP = "/wp-content/uploads/2022/11/Normas-Subsidiarias-de-Alguazas.zip"
PDF = "/wp-content/uploads/2022/11/plano.pdf"


class AlguazasTests(unittest.TestCase):
    def test_group_documents_and_exclude_other_inventory_entries(self):
        html = (block("NORMAS SUBSIDIARIAS", ZIP, PDF)
                + block("NORMAS SUBSIDIARIAS", ZIP)
                + block("ORDENANZA DE LICENCIAS URBANÍSTICAS", "/tasa.pdf")
                + block("PLAN DE JUVENTUD", "/juventud.pdf")
                + block("MODIFICACION BORM Nº 302 DE 31-12-2008 (está oculta)", "/fiscal.pdf")
                + '<article>Adjudicación de obras y reunión del Plan General</article>')
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["documentos"]), 2)
        self.assertEqual(rows[0]["codigo_ine"], "30007")
        for key in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "fase"):
            self.assertNotIn(key, rows[0])

    def test_empty_or_documentless_inventory_fails(self):
        for html in ("", block("TASA DE LICENCIA", PDF), block("NORMAS SUBSIDIARIAS")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_external_or_non_document_links_fail(self):
        for url in ("https://example.org/plan.zip", "/solicitar-licencia", "javascript:alert(1)"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_inventory(block("NORMAS SUBSIDIARIAS", url))

    def test_pagination_is_not_silently_truncated(self):
        for control in ('<a rel="next" href="/page/2/">2</a>',
                        '<div class="pagination"><a href="?page=2">2</a></div>'):
            with self.assertRaises(ValueError):
                parse_inventory(block("NORMAS SUBSIDIARIAS", ZIP) + control)

    def test_manifest_and_live_method_contract(self):
        manifest = load_manifest("alguazas")
        self.assertEqual(manifest.provincia, "Murcia")
        self.assertFalse(manifest.licencias.enabled)
        adapter = AlguazasAyuntamientoAdapter("alguazas")
        response = Mock(url=SOURCE_URL, text=block("NORMAS SUBSIDIARIAS", ZIP))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proyectos.jsonl"
            with patch("municipio.adapters.alguazas.requests.get", return_value=response):
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / "state.json")["count"], 1)
            self.assertEqual(json.loads(path.read_text())["municipio"], "Alguazas")
            with patch("municipio.adapters.alguazas.requests.get", side_effect=requests.Timeout):
                with self.assertRaises(requests.Timeout):
                    adapter.backfill_proyectos(path)
            self.assertEqual(json.loads(path.read_text())["municipio"], "Alguazas")
            self.assertTrue(adapter.backfill_licencias(path)["disabled"])
            self.assertEqual(path.read_text(), "")


if __name__ == "__main__":
    unittest.main()
