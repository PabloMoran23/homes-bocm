import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.lardero import INVENTORY_URL, LarderoAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def inventory(extra=""):
    return '''<h1>Plan General Municipal</h1><div data-elementor-type="wp-page">
    <a href="/Descargar/376/suelo-urbanizable-productivo/12044/sp-1.pdf">SP-1</a>
    <a href="/Descargar/376/suelo-urbanizable-productivo/12046/sp-1-graf.pdf">SP-1-GRAF</a>
    <a href="/Descargar/377/suelo-urbanizable-residencial/12073/sp-1.pdf">SP-1</a>
    <a href="/Descargar/376/suelo-urbanizable-productivo/12044/sp-1.pdf">SP-1</a>
    <a href="/wp-content/uploads/INSTANCIA_URBANISTICA.pdf">Solicitud de licencia</a>
    <a href="https://example.org/Descargar/1/x/2/unrelated.pdf">Ajeno</a>
    ''' + extra + '</div>'


class LarderoTests(unittest.TestCase):
    def test_group_documents_and_keep_sections(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["codigo_ine"], "26084")
        self.assertEqual(len(row["documentos"]), 3)
        self.assertNotEqual(row["documentos"][0]["seccion_fuente"], row["documentos"][2]["seccion_fuente"])
        self.assertTrue(all(d["source_url"] == INVENTORY_URL for d in row["documentos"]))
        self.assertFalse(row["publication_ready"])
        for field in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "geometry", "fase"):
            self.assertNotIn(field, row)

    def test_missing_inventory_fails(self):
        for html in ("", "<h1>Plan General Municipal</h1>", '<div data-elementor-type="wp-page"><h1>Plan General Municipal</h1></div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_and_unknown_documents_fail(self):
        for extra in ('<a rel="next" href="?page=2">Más</a>', '<div class="page-numbers">2</div>', '<a href="/Descargar/1/categoria/2/new.zip">Nuevo</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(inventory(extra))
        with self.assertRaises(ValueError):
            parse_inventory(inventory(), "https://example.org/plan-general-municipal/")

    @patch("municipio.adapters.lardero.requests.get")
    def test_live_path_refresh_and_failure(self, get):
        get.return_value = Mock(text=inventory(), url=INVENTORY_URL)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "proyectos.jsonl"
            adapter = LarderoAyuntamientoAdapter("lardero")
            self.assertEqual(adapter.update_proyectos(output, Path(tmp) / "state.json")["count"], 1)
            self.assertEqual(json.loads(output.read_text())["id"], "lardero-pgm")
            original = output.read_text()
            get.return_value.text = "server error"
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)
            self.assertTrue(adapter.backfill_licencias(Path(tmp) / "licencias.jsonl")["disabled"])

    def test_manifest(self):
        manifest = load_manifest("lardero")
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw["codigo_ine"]), ("Lardero", "La Rioja", "26084"))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])


if __name__ == "__main__":
    unittest.main()
