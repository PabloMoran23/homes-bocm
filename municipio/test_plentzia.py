"""Offline parser/adapter regressions; live captures are kept separately in evidence/."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from municipio.adapters.plentzia import SOURCE, PlentziaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


HTML = """<html><head><title>PGOU Plentzia</title></head><body>
<p>Alcalde de Plentzia</p><p>Normas Subsidiarias aprobadas el 16 de julio de 2001</p>
<div id="fases"><h3>APROBACIÓN DEFINITIVA</h3>
<div class="eb-progressbar-title">FASE ACTUAL: 1</div></div>
<div id="documentos"><h4>DOCUMENTACIÓN</h4>
<a href="//otro-municipio.eus/plantilla.pdf"></a>
<div class="wp-block-file"><a href="/wp-content/uploads/2026/06/manual.pdf">MANUAL</a>
<a class="wp-block-file__button" download href="/wp-content/uploads/2026/06/manual.pdf">Descarga</a></div>
<div class="wp-block-file"><a href="/wp-content/uploads/2026/06/programa.pdf">PROGRAMA</a></div>
<div class="wp-block-file"><a href="/wp-content/uploads/2026/06/manual.pdf#page=1">MANUAL</a></div>
</div><a href="/noticia.pdf">Noticia fuera del inventario</a></body></html>"""


class PlentziaTests(unittest.TestCase):
    def test_grouping_identity_and_date_semantics(self):
        rows = parse_inventory(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["codigo_ine"], "48077")
        self.assertEqual(row["provincia"], "Bizkaia")
        self.assertEqual(len(row["documentos"]), 2)
        self.assertEqual(row["documentos"][0]["url"], SOURCE + "wp-content/uploads/2026/06/manual.pdf")
        self.assertEqual(row["fase"], "FASE ACTUAL: 1")
        for field in ("fecha_publicacion", "fecha_acuerdo", "fecha_aprob"):
            self.assertIsNone(row[field])
        self.assertNotIn("lat", row)
        self.assertFalse(row["publication_ready"])

    def test_current_phase_is_read_from_explicit_marker(self):
        row = parse_inventory(HTML.replace("FASE ACTUAL: 1", "FASE ACTUAL: 3"))[0]
        self.assertEqual(row["fase"], "FASE ACTUAL: 3")
        self.assertEqual(row["id"], parse_inventory(HTML)[0]["id"])

    def test_pagination_fails_loudly(self):
        for pagination in ('<a href="?paged=2">2</a>', '<link rel="next" href="/next/">',
                           '<div class="pagination"></div>', '<a href="/mas/">Siguiente</a>'):
            with self.subTest(pagination=pagination), self.assertRaisesRegex(ValueError, "pagination"):
                parse_inventory(HTML + pagination)

    def test_missing_or_changed_sources_fail(self):
        cases = [HTML.replace("PGOU Plentzia", "PGOU Otro"),
                 HTML.replace("Alcalde de Plentzia", ""),
                 HTML.replace('id="documentos"', 'id="missing"'),
                 HTML.replace("FASE ACTUAL: 1", "Próximas fases"),
                 HTML.replace('/wp-content/uploads/2026/06/programa.pdf', 'https://otro.eus/programa.pdf'),
                 HTML.replace('</h4>', '</h4><a href="/nuevo.pdf">Nuevo documento</a>'),
                 HTML.replace('<a class="wp-block-file__button" download href="/wp-content/uploads/2026/06/manual.pdf">',
                              '<a class="wp-block-file__button" download href="/different.pdf">')]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_inventory(HTML, "https://otro.eus/")

    @staticmethod
    def response(url, content):
        response = Mock()
        response.url = url
        response.content = content
        response.text = content.decode()
        return response

    def test_live_path_checks_downloads_and_preserves_output_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proyectos.jsonl"
            adapter = PlentziaAyuntamientoAdapter("plentzia", {"evidence_dir": tmp})
            calls = [self.response(SOURCE, HTML.encode())] + [
                self.response(d["url"], b"%PDF-1.4\nfixture") for d in parse_inventory(HTML)[0]["documentos"]]
            with patch("municipio.adapters.plentzia.requests.get", side_effect=calls) as get:
                result = adapter.backfill_proyectos(out)
            self.assertEqual(result["count"], 1)
            self.assertEqual(get.call_count, 3)
            original = out.read_text()
            row = json.loads(original)
            self.assertEqual(len(row["documentos"][0]["sha256"]), 64)
            with patch("municipio.adapters.plentzia.requests.get", side_effect=[
                self.response(SOURCE, HTML.encode()), self.response(SOURCE, b"<html>error</html>")
            ]), self.assertRaisesRegex(ValueError, "not a PDF"):
                adapter.update_proyectos(out, Path(tmp) / "state.json")
            self.assertEqual(out.read_text(), original)
            with patch("municipio.adapters.plentzia.requests.get", side_effect=requests.Timeout):
                with self.assertRaises(requests.Timeout):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), original)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("plentzia")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "48077")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, "municipio.adapters.plentzia:PlentziaAyuntamientoAdapter")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "licencias.jsonl"
            with patch("municipio.adapters.plentzia.requests.get") as get:
                result = PlentziaAyuntamientoAdapter("plentzia").backfill_licencias(out)
            get.assert_not_called()
            self.assertTrue(result["disabled"])
            self.assertEqual(out.read_text(), "")


if __name__ == "__main__":
    unittest.main()
