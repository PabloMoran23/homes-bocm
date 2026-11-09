import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.santillana_del_mar import (
    HOST, SOURCE, SantillanaDelMarAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


TITLES = ["20240520_TOMO_I_MEMORIA_INFORMACION _AVANCE_signed",
          "20240520_TOMO_II_PLANOS_ORDENACION_firmados", "20240520_TOMO_III_DIE_firmados",
          "PUBLICACIÓN ANUNCIO AVANCE BOC Nº 133 10.07.24", "BANDO REVISION PLAN GENERAL",
          "CONSULTAS REVISION PGOU"]


def fixture(titles=TITLES):
    rows = "".join(f'<tr><td class="class_name"><a href="https://{HOST}/preview-document/'
                   f'00000000-0000-0000-0000-{i:012d}">{title}</a></td></tr>'
                   for i, title in enumerate(titles))
    return ('<div id="content"><h2>7. REVISION PGOU SANTILLANA DEL MAR</h2>'
            '<table class="TransparencyListPanel">' + rows + '</table></div>')


class SantillanaTests(unittest.TestCase):
    def test_grouping_dates_and_no_inferred_geometry(self):
        row, = parse_inventory(fixture())
        self.assertEqual(len(row["documentos"]), 6)
        self.assertEqual(row["fecha_publicacion"], "2024-07-10")
        self.assertIn("000000000003", row["fecha_publicacion_fuente"])
        for key in ("fecha", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "geometry"):
            self.assertIsNone(row[key])
        self.assertEqual(row["codigo_ine"], "39076")
        self.assertFalse(row["publication_ready"])

    def test_missing_date_is_not_filename_or_crawl_date(self):
        titles = [t.replace(" 10.07.24", "") for t in TITLES]
        self.assertIsNone(parse_inventory(fixture(titles))[0]["fecha_publicacion"])

    def test_reject_shell_and_incomplete_volumes(self):
        for html in ("<h1>Identifícate</h1>", fixture(TITLES[1:]),
                     fixture(["Solicitud licencia de obras"])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_pagination_folders_and_external_links(self):
        for html in (fixture().replace('</div>', '<a rel="next">2</a></div>'),
                     fixture().replace('</div>', '<div class="pagination">1 2</div></div>'),
                     fixture().replace('href="https://' + HOST, 'href="https://example.org', 1),
                     fixture().replace('</table>', '<tr><td class="class_name"><a href="#">Folder (2)</a></td></tr></table>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_update_snapshot_and_preview_failure_preserves_output(self):
        adapter = SantillanaDelMarAyuntamientoAdapter("santillana-del-mar")
        def fetch(session, url, name):
            if url == SOURCE:
                return fixture()
            title = TITLES[int(url.rsplit('-', 1)[-1])]
            return '<div id="validationPageInfoDocument">' + title + '</div>'
        with TemporaryDirectory() as directory:
            output = Path(directory) / "proyectos.jsonl"
            with patch.object(adapter, "_fetch", side_effect=fetch):
                self.assertEqual(adapter.backfill_proyectos(output)["count"], 1)
                original = output.read_text()
                adapter.update_proyectos(output, Path(directory) / "state.json")
                self.assertEqual(original, output.read_text())
                self.assertEqual(len(json.loads(original)["documentos"]), 6)
            with patch.object(adapter, "_fetch", side_effect=[fixture(), '<h1>Identifícate</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(original, output.read_text())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("santillana-del-mar")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "39076")
        self.assertEqual(manifest.provincia, "Cantabria")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            output = Path(directory) / "licencias.jsonl"
            result = SantillanaDelMarAyuntamientoAdapter(manifest.slug).backfill_licencias(output)
            self.assertTrue(result["disabled"])
            self.assertEqual(output.read_text(), "")


if __name__ == "__main__":
    unittest.main()
