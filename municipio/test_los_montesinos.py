"""Offline semantic and traversal tests; live evidence is generated separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.los_montesinos import SOURCE, LosMontesinosAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(*links):
    return '<h1>Planeamiento urbanístico de Los Montesinos</h1><div class="entry-content">' + ''.join(
        f'<a href="{url}">{label}</a>' for label, url in links) + '</div>'


def doc(name):
    return '/wp-content/uploads/2018/07/' + name


class LosMontesinosTests(unittest.TestCase):
    def test_group_parts_and_duplicate_split_anchor(self):
        url = doc('NORMAS-SUBSIDIARIAS-parte-1.pdf')
        result = parse_inventory(page(('N', url), ('ORMAS SUBSIDIARIAS parte 1', url),
            ('NORMAS SUBSIDIARIAS parte 2', doc('NORMAS-SUBSIDIARIAS-parte-2.pdf')),
            ('Normas urbanísticas RES-1', doc('Normas-urban%C3%ADsticas-RES-1.pdf')),
            ('Plano 1', doc('Plano-1_clasificaci%C3%B3n-zona-norte.tif'))))
        self.assertEqual(len(result['records']), 2)
        first, second = result['records']
        self.assertEqual(len(first['documentos']), 2)
        self.assertEqual(len(second['documentos']), 1)
        self.assertEqual(len(result['unassigned_documents']), 1)
        self.assertIn('parte 1', first['documentos'][0]['titulo'])
        for row in result['records']:
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])

    def test_empty_wrong_municipality_and_unclassified_document_fail(self):
        for html in ('', page(), '<h1>Otro municipio</h1><div class="entry-content"></div>',
                     page(('Nuevo plan', doc('nuevo-plan.pdf')))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_documents_outside_inventory_are_excluded(self):
        result = parse_inventory(page(('RES-2', doc('Normas-urban%C3%ADsticas-RES-2.pdf'))) +
                                 '<footer><a href="/unrelated.pdf">Unrelated</a></footer>')
        self.assertEqual(len(result['records']), 1)

    def test_document_host_is_checked(self):
        with self.assertRaises(ValueError):
            parse_inventory(page(('RES-1', 'https://example.org/Normas-urbanisticas-RES-1.pdf')))

    def test_forms_and_unrelated_news_are_not_records(self):
        result = parse_inventory(page(('RES-1', doc('Normas-urban%C3%ADsticas-RES-1.pdf')),
                                      ('Solicitud licencia', '/solicitud/'), ('Noticias', '/noticias/')))
        self.assertEqual(len(result['records']), 1)

    def test_pagination_merged_without_duplicate_instruments(self):
        next_url = SOURCE + '?page=2'
        first = page(('Parte 1', doc('NORMAS-SUBSIDIARIAS-parte-1.pdf')), ('2', next_url))
        second = page(('Parte 2', doc('NORMAS-SUBSIDIARIAS-parte-2.pdf')), ('1', SOURCE))
        adapter = LosMontesinosAyuntamientoAdapter('los-montesinos')
        def fetch(url, document=False):
            if document:
                return b'%PDF-test'
            return {SOURCE: first, next_url: second}[url].encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fetch) as mock:
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['live_records'], 1)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(mock.call_count, 4)

    def test_failed_document_does_not_write_partial_output(self):
        adapter = LosMontesinosAyuntamientoAdapter('los-montesinos')
        html = page(('RES-1', doc('Normas-urban%C3%ADsticas-RES-1.pdf')))
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[html.encode(), ValueError('Unavailable')]):
            out = Path(tmp) / 'proyectos.jsonl'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertFalse(out.exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('los-montesinos')
        self.assertEqual(manifest.provincia, 'Alicante')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), LosMontesinosAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = LosMontesinosAyuntamientoAdapter('los-montesinos').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
