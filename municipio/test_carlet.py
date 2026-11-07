"""Parser and traversal regressions; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from municipio.adapters.carlet import (
    CarletAyuntamientoAdapter, ORIGIN, PAI, PLANNING,
    action_url, make_record, merge_components, parse_entries,
)
from municipio.manifest import load_manifest


def page(content, more=''):
    return '<table class="TransparencyListPanel"><tbody>' + content + '</tbody></table>' + more


def folder(title, token):
    return f'''<tr><td><a class="exp" href="#" onclick="wicketAjaxGet('?x={token}',null)">{title}<span> ( 2 )</span></a></td></tr>'''


def doc(title, identifier):
    return f'<tr><td><a href="{ORIGIN}/preview-document/{identifier}">{title}</a></td></tr>'


class CarletTests(unittest.TestCase):
    def test_entries_exclude_generic_as_record_and_keep_provenance(self):
        html = page(folder('Expedient de modificació puntual del Pla General número 11', 'folder')
                    + doc('Certificat acord Ple 21-07-2022', 'doc')
                    + '<tr><td><a href="http://www.carlet.es/va/content/pla-general-dordenacio">Pla General</a></td></tr>')
        entries = parse_entries(BeautifulSoup(html, 'html.parser'), PLANNING)
        self.assertEqual([e['kind'] for e in entries], ['folder', 'document', 'external'])
        self.assertNotIn('( 2 )', entries[0]['titulo'])
        record = make_record(entries[0]['titulo'], PLANNING, [entries[1], entries[1]])
        self.assertEqual(len(record['documentos']), 1)
        self.assertEqual(record['documentos'][0]['titulo'], 'Certificat acord Ple 21-07-2022')
        for field in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, record)
        self.assertEqual(record['codigo_ine'], '46085')

    def test_reject_empty_and_unrelated(self):
        with self.assertRaises(ValueError):
            parse_entries(BeautifulSoup('<h1>Unavailable</h1>', 'html.parser'), PLANNING)
        for title in ['Sol·licitud llicència', 'Anunci licitació', 'Notícies', 'PLANEAMIENTO DE DESARROLLO']:
            with self.assertRaises(ValueError):
                make_record(title, PLANNING, [{'titulo': 'x', 'url': 'x'}])
        with self.assertRaises(ValueError):
            make_record('PP AUSIAS MARCH I', PLANNING, [])

    def test_navigation_host_guard(self):
        a = BeautifulSoup('''<a onclick="wicketAjaxGet('https://example.org/?x=y')"></a>''', 'html.parser').a
        with self.assertRaises(ValueError):
            action_url(a, PLANNING)

    def test_load_more_components(self):
        soup = BeautifulSoup(page(doc('first', 'one'), '<div class="more_results" id="more"><button onclick="wicketAjaxGet(\'?x=next\')">More</button></div>'), 'html.parser')
        xml = '''<?xml version="1.0"?><ajax-response><evaluate>ignored()</evaluate>
          <component id="row2"><![CDATA[<tr id="row2"><td><a href="/preview-document/two">second</a></td></tr>]]></component>
          <component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'''
        merge_components(soup, xml)
        self.assertEqual(len(parse_entries(soup, PLANNING)), 2)
        self.assertIsNone(soup.select_one('.more_results button'))

    def test_folder_follows_pagination(self):
        adapter = CarletAyuntamientoAdapter('carlet')
        more = '<div class="more_results" id="more"><button onclick="wicketAjaxGet(\'?x=next\')">More</button></div>'
        first = type('Response', (), {'url': PLANNING, 'text': page(doc('one', 'one'), more)})()
        second = type('Response', (), {'url': ORIGIN + '/?x=next', 'text': '''<?xml version="1.0"?><ajax-response>
          <component id="two"><![CDATA[<tr id="two"><td><a href="/preview-document/two">two</a></td></tr>]]></component>
          <component id="more"><![CDATA[<div id="more"></div>]]></component></ajax-response>'''})()
        with patch.object(adapter, '_fetch', side_effect=[first, second]) as fetch:
            _, entries = adapter._folder(None, PLANNING)
        self.assertEqual(len(entries), 2)
        self.assertEqual(fetch.call_count, 2)

    def test_traversal_groups_documents_and_skips_empty(self):
        adapter = CarletAyuntamientoAdapter('carlet')
        a = ORIGIN + '/transparency/398a1626-e2c6-4507-8e49-4fd15073faaa/'
        b = ORIGIN + '/transparency/c4627a6b-a285-455c-8efd-f684234edf5b/'
        def listing(session, url):
            return {
                PLANNING: (PLANNING, [{'kind': 'folder', 'titulo': 'PP AUSIAS MARCH II', 'url': a},
                                      {'kind': 'folder', 'titulo': 'PP AUSIAS MARCH I', 'url': b}]),
                a: (a, [{'kind': 'document', 'titulo': 'Plan', 'url': 'document-a'},
                         {'kind': 'document', 'titulo': 'Acuerdo', 'url': 'document-b'}]),
                b: (b, []),
                PAI: (PAI, [{'kind': 'document', 'titulo': 'Urbanización', 'url': 'document-c'}]),
            }[url]
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_folder', side_effect=listing):
            out = Path(directory) / 'proyectos.jsonl'
            report = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual(report['count'], 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[1]['documentos'][0]['url'], 'document-c')
        self.assertEqual(report['excluded'][0]['reason'], 'empty instrument folder')

    def test_failure_does_not_overwrite_output(self):
        adapter = CarletAyuntamientoAdapter('carlet')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_folder', side_effect=ValueError('unavailable')):
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('carlet')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.carlet:CarletAyuntamientoAdapter')
        with self.assertRaises(NotImplementedError):
            CarletAyuntamientoAdapter('carlet').backfill_licencias(Path('unused'))


if __name__ == '__main__':
    unittest.main()
