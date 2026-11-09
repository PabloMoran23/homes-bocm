"""Offline tests for Wicket pagination, document grouping and fail-closed output."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup

from municipio.adapters.san_miguel_de_salinas import (
    HOST, SOURCE, SanMiguelDeSalinasAyuntamientoAdapter, apply_more, parse_entries,
)
from municipio.manifest import load_manifest, load_yaml

A = HOST + '/transparency/11111111-1111-1111-1111-111111111111/'
B = HOST + '/transparency/22222222-2222-2222-2222-222222222222/'
NESTED = HOST + '/transparency/33333333-3333-3333-3333-333333333333/'


def folder(title, count, token):
    return (f'<tr><td><a class="gIconLink exp" onclick="wicketAjaxGet(\'../../?x={token}\')">'
            f'{title}<span class="linkExtraInfo"> ( {count} )</span></a></td></tr>')


def document(title, number):
    return (f'<tr><td><a class="gIconLink" href="{HOST}/preview-document/'
            f'00000000-0000-0000-0000-{number:012d}">{title}</a></td></tr>')


def listing(rows, more=False):
    return ('<table class="TransparencyListPanel"><tbody>' + rows + '</tbody></table>'
            + ('<div class="more_results" id="more"><button onclick="wicketAjaxGet(\'../../?x=more\')">Mostrar más</button></div>' if more else ''))


class FakeAdapter(SanMiguelDeSalinasAyuntamientoAdapter):
    def __init__(self):
        super().__init__()
        second = folder('1.2. PLAN PARCIAL SECTOR “LO QUILEZ”', 1, 'b').replace('<tr>', '<tr id="new">', 1)
        self.pages = {
            SOURCE: listing(folder('1.1. NORMAS SUBSIDIARIAS DE PLANEAMIENTO', 2, 'a'), True),
            HOST + '/?x=more': ('<ajax-response><component id="new"><![CDATA[' + second
                + ']]></component><component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'),
            A: listing(folder('PLANOS', 2, 'nested')),
            NESTED: listing(document('Memoria NNSS', 1) + document('Planos NNSS', 2)),
            B: listing(document('Memoria Lo Quilez', 3)),
        }
        self.destinations = {'a': A, 'b': B, 'nested': NESTED}

    def _get(self, url, **kwargs):
        token = url.split('?x=')[-1]
        if token in self.destinations:
            return SimpleNamespace(headers={'Ajax-Location': self.destinations[token]}, text=' ')
        return SimpleNamespace(headers={}, text=self.pages[url])


class SanMiguelTests(unittest.TestCase):
    def test_manifest_identity_and_safety(self):
        manifest = load_manifest('san-miguel-de-salinas')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']),
                         ('San Miguel de Salinas', 'Alicante', '03120'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])

    def test_paginated_instruments_group_nested_documents(self):
        adapter = FakeAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['documents'], 3)
        self.assertEqual([d['titulo'] if 'titulo' in d else d['title'] for d in rows[0]['documentos']],
                         ['Memoria NNSS', 'Planos NNSS'])
        self.assertEqual(rows[1]['documentos'][0]['title'], 'Memoria Lo Quilez')
        self.assertEqual(rows[0]['documentos'][0]['inventory_url'], NESTED)
        for row in rows:
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '03120')
            for field in ('fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'fase', 'lat', 'lon'):
                self.assertNotIn(field, row)

    def test_count_mismatch_keeps_previous_snapshot(self):
        adapter = FakeAdapter()
        adapter.pages[NESTED] = listing(document('Memoria', 1))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with self.assertRaisesRegex(ValueError, 'count mismatch'):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_duplicate_documents_fail(self):
        adapter = FakeAdapter()
        adapter.pages[NESTED] = listing(document('Memoria', 1) * 2)
        with self.assertRaisesRegex(ValueError, 'Duplicate documents'):
            adapter._documents(NESTED, set())

    def test_nonadvancing_pagination_fails(self):
        adapter = FakeAdapter()
        adapter.pages[HOST + '/?x=more'] = ('<ajax-response><component id="more"><![CDATA['
            '<div class="more_results" id="more"><button onclick="wicketAjaxGet(\'../../?x=more\')">Mostrar más</button></div>'
            ']]></component></ajax-response>')
        with self.assertRaisesRegex(ValueError, 'did not advance'):
            adapter._listing(SOURCE)

    def test_missing_table_or_empty_inventory_fails(self):
        for html in ('<html>Login</html>', listing('')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_entries(BeautifulSoup(html, 'html.parser'), SOURCE)

    def test_external_documents_rejected(self):
        html = listing(document('Memoria', 1)).replace(HOST, 'https://example.org')
        with self.assertRaisesRegex(ValueError, 'Unexpected official source'):
            parse_entries(BeautifulSoup(html, 'html.parser'), SOURCE)

    def test_invalid_pagination_fails(self):
        with self.assertRaises(ValueError):
            apply_more(BeautifulSoup(listing(''), 'html.parser'), '<ajax-response/>')

    def test_form_not_promoted_to_instrument(self):
        adapter = FakeAdapter()
        adapter.pages[SOURCE] = listing(folder('Solicitud de licencia de obras', 1, 'a'))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'Unrecognized instrument'):
            adapter.backfill_proyectos(Path(tmp) / 'out.jsonl')

    def test_incremental_is_complete_snapshot_and_licences_disabled(self):
        adapter = FakeAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            path, state = Path(tmp) / 'out.jsonl', Path(tmp) / 'state.json'
            self.assertEqual(adapter.update_proyectos(path, state)['count'], 2)
            self.assertFalse(state.exists())
            self.assertTrue(adapter.update_licencias(path, state)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
