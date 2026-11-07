import tempfile
import unittest
from pathlib import Path

from municipio.adapters.penarroya_pueblonuevo import (
    PenarroyaPueblonuevoAyuntamientoAdapter, SOURCE, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def fixture(documents=None):
    documents = documents if documents is not None else (
        '<a href="/wp-content/uploads/2022/11/001.pdf">Metodología y Trabajo de Campo</a>'
        '<a href="/wp-content/uploads/2022/11/002.pdf">Diagnosis</a>'
        '<a href="/wp-content/uploads/2022/11/003.pdf">Propuesta de actuación</a>')
    return ('<div class="entry-content"><div class="et_pb_text_inner">'
            '<h2>Plan de movilidad urbana sostenible</h2>' + documents + '</div>'
            '<div class="et_pb_text_inner"><h2>Licitaciones</h2>'
            '<a href="/wp-content/uploads/2025/anuncio.pdf">Anuncio de licitación</a></div>'
            '<a href="/formulario">Solicitud de licencia de obras</a></div>')


class ParserTests(unittest.TestCase):
    def test_groups_documents_and_excludes_forms_tenders(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['codigo_ine'], '14052')
        self.assertEqual(rows[0]['url'], SOURCE)
        self.assertFalse(rows[0]['publication_ready'])
        self.assertFalse(set(rows[0]) & {'fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'})

    def test_dedup_and_stable_identity(self):
        a = '<a href="/wp-content/uploads/a.pdf">Diagnosis</a>'
        one = parse_inventory(fixture(a))[0]
        duplicate = parse_inventory(fixture(a + a))[0]
        self.assertEqual(one, duplicate)
        self.assertEqual(one['id'], parse_inventory(fixture())[0]['id'])

    def test_empty_and_missing_section_fail(self):
        for html in ['', '<div class="entry-content">Licitaciones</div>', fixture('')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_closed(self):
        for pagination in ['<a rel="next" href="/page/2">2</a>',
                           '<div class="page-links"><a href="/2">2</a></div>',
                           '<link rel="next" href="/2">']:
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                parse_inventory(fixture() + pagination)

    def test_unexpected_document_fails(self):
        for href in ['https://example.org/a.pdf', '/login', 'javascript:void(0)']:
            with self.subTest(href=href), self.assertRaises(ValueError):
                parse_inventory(fixture(f'<a href="{href}">Diagnosis</a>'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('penarroya-pueblonuevo')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '14052')
        self.assertEqual(manifest.provincia, 'Córdoba')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'licencias.jsonl'
            adapter = PenarroyaPueblonuevoAyuntamientoAdapter(manifest.slug)
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
