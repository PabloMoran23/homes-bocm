"""Offline parser and traversal regression tests; no live network required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_pobla_llarga import (
    SOURCE, HOST, ROOT_DOCUMENTS, SECTIONS, LaPoblaLlargaAyuntamientoAdapter,
    build_record, parse_folder,
)
from municipio.manifest import load_manifest


def document(title, number):
    return (f'<a class="gIconLink" href="https://{HOST}/preview-document/'
            f'00000000-0000-0000-0000-{number:012d}">{title}</a>')


def folder(title, count, number):
    return (f'<a class="gIconLink exp" href="#" '
            f'onclick="wicketAjaxGet(\'../../?x={number}\')">{title} ( {count} )</a>')


def page(body):
    return '<div id="content"><table class="TransparencyListPanel">' + body + '</table></div>'


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.adapter = LaPoblaLlargaAyuntamientoAdapter('la-pobla-llarga')
        self.root = page(''.join(document(t, i) for i, t in enumerate(sorted(ROOT_DOCUMENTS))) +
                         ''.join(folder(t, 1, i + 10) for i, t in enumerate(sorted(SECTIONS))))

    def fetch(self, session, url):
        if url == SOURCE:
            return SOURCE, self.root
        number = int(url.rsplit('=', 1)[1])
        return SOURCE.replace('73d2c18c', f'{number:08d}'), page(document('Documento del PGOU', number))

    def test_manifest_and_interface(self):
        manifest = load_manifest('la-pobla-llarga')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertEqual(manifest.portal.adapter.rsplit(':', 1)[1], type(self.adapter).__name__)

    def test_group_all_sections_and_keep_provenance(self):
        with patch.object(self.adapter, '_fetch', side_effect=self.fetch) as fetch:
            rows = self.adapter.collect(None)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 9)
        self.assertEqual({d.get('seccion') for d in row['documentos']} - {None}, SECTIONS)
        self.assertEqual(fetch.call_count, 9)
        self.assertEqual(row['codigo_ine'], '46203')
        self.assertFalse(row['publication_ready'])
        for key in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon']:
            self.assertNotIn(key, row)
        self.assertTrue(all(d['inventory_url'].startswith('https://' + HOST) for d in row['documentos']))

    def test_missing_and_unrelated_inventory_rejected(self):
        with self.assertRaises(ValueError):
            parse_folder('<h1>Login</h1>', SOURCE)
        with self.assertRaises(ValueError):
            build_record([{'titulo': 'Solicitud de licencia', 'url': SOURCE}])
        self.root = page(document('Anuncio de licitación', 1))
        with patch.object(self.adapter, '_fetch', side_effect=self.fetch), self.assertRaises(ValueError):
            self.adapter.collect(None)

    def test_pagination_is_not_silently_truncated(self):
        for link in ['<div class="pagination"><a href="?page=2">2</a></div>',
                     '<a href="?page=2" rel="next">2</a>',
                     '<a href="#" onclick="more()">Veure\'n més</a>']:
            with self.subTest(link=link), self.assertRaises(ValueError):
                parse_folder(page(link), SOURCE)

    def test_missing_child_document_and_new_section_fail(self):
        self.root = self.root.replace('( 1 )', '( 2 )')
        with patch.object(self.adapter, '_fetch', side_effect=self.fetch), self.assertRaises(ValueError):
            self.adapter.collect(None)
        self.root = page(folder('5. NUEVO PLAN', 1, 90))
        with patch.object(self.adapter, '_fetch', side_effect=self.fetch), self.assertRaises(ValueError):
            self.adapter.collect(None)

    def test_external_documents_fail(self):
        with self.assertRaises(ValueError):
            parse_folder(page('<a class="gIconLink" href="https://example.org/a.pdf">PGOU</a>'), SOURCE)

    def test_failed_collection_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'proyectos.jsonl'
            output.write_text('prior\n')
            with patch.object(self.adapter, 'collect', side_effect=ValueError('incomplete')):
                with self.assertRaises(ValueError):
                    self.adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'prior\n')
            self.assertTrue(self.adapter.backfill_licencias(Path(temp) / 'licencias.jsonl')['disabled'])


if __name__ == '__main__':
    unittest.main()
