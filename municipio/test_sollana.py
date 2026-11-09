"""Offline parser/transport tests. All fixtures below are synthetic."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from municipio.adapters.sollana import (
    BASE, SollanaAyuntamientoAdapter, action_url, ajax_fragment, local_url,
    make_record, parse_listing,
)
from municipio.manifest import load_manifest, load_yaml

DOC = BASE + '/preview-document/00000000-0000-0000-0000-000000000001'
URL = BASE + '/transparency/00000000-0000-0000-0000-000000000002/'


def document(title='Synthetic plan sheet', url=DOC):
    return f'<a class="gIconLink" href="{url}">{title}</a>'


def listing(content):
    return '<table class="TransparencyListPanel">' + content + '</table>'


MORE = '<button onclick="wicketAjaxGet(\'../../?x=more\')">Mostrar más</button>'


class SollanaParserTests(unittest.TestCase):
    def test_scope_excludes_navigation(self):
        entries, more = parse_listing(document('Navigation') + listing(document()))
        self.assertEqual(entries, [{'titulo': 'Synthetic plan sheet', 'url': DOC}])
        self.assertIsNone(more)

    def test_folder_count_and_action(self):
        html = listing('<a class="gIconLink exp" href="#" onclick="wicketAjaxGet(\'../../?x=folder\')">'
                       'Instrument<span class="linkExtraInfo"> ( 14 )</span></a>')
        entries, _ = parse_listing(html)
        self.assertEqual(entries[0]['title'], 'Instrument')
        self.assertEqual(entries[0]['count'], 14)
        self.assertEqual(action_url(URL, entries[0]['element']), BASE + '/?x=folder')

    def test_missing_inventory_and_unknown_entries_fail(self):
        for html in ('<html>Login</html>', listing('<a class="gIconLink" href="/forms">Licence form</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_listing(html)

    def test_external_actions_rejected(self):
        with self.assertRaises(ValueError):
            local_url(BASE, 'https://other.example/inventory')

    def test_ajax_components_only(self):
        xml = '<ajax-response><evaluate><![CDATA[ignored javascript]]></evaluate>' \
              '<component id="row"><![CDATA[' + document() + ']]></component></ajax-response>'
        self.assertEqual(parse_listing(ajax_fragment(xml), fragment=True)[0][0]['url'], DOC)
        with self.assertRaises(ValueError):
            ajax_fragment('<html/>')

    def test_show_more_collects_remaining_documents(self):
        adapter = SollanaAyuntamientoAdapter()
        second = DOC[:-1] + '3'
        xml = '<ajax-response><component id="row"><![CDATA[' + document('Second sheet', second) + \
              ']]></component><component id="more"><![CDATA[<div style="display:none"></div>]]></component></ajax-response>'
        with patch.object(adapter, '_get', side_effect=[
            SimpleNamespace(text=listing(document()) + MORE), SimpleNamespace(text=xml)
        ]) as fetch:
            entries = adapter._listing(URL)
        self.assertEqual(len(entries), 2)
        self.assertEqual(fetch.call_args_list[1].kwargs, {'ajax': True})

    def test_pagination_duplicate_and_no_progress_fail(self):
        adapter = SollanaAyuntamientoAdapter()
        for fragment in (document(), '<div/>'):
            xml = '<ajax-response><component id="row"><![CDATA[' + fragment + ']]></component></ajax-response>'
            with patch.object(adapter, '_get', side_effect=[
                SimpleNamespace(text=listing(document()) + MORE), SimpleNamespace(text=xml)
            ]), self.assertRaises(ValueError):
                adapter._listing(URL)

    def test_count_mismatch_fails(self):
        adapter = SollanaAyuntamientoAdapter()
        with patch.object(adapter, '_listing', return_value=[{'titulo': 'Sheet', 'url': DOC}]), \
                self.assertRaisesRegex(ValueError, 'expected 14, found 1'):
            adapter._documents(URL, 14)

    def test_record_groups_documents_without_invented_semantics(self):
        docs = [{'titulo': 'Sheet', 'url': DOC}, {'titulo': 'Same sheet', 'url': DOC}]
        record = make_record('Synthetic instrument', URL, docs, [URL])
        self.assertEqual(len(record['documentos']), 1)
        self.assertEqual(record['codigo_ine'], '46233')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(record[field])
        self.assertEqual(record['id'], make_record('Renamed instrument', URL, docs, [URL])['id'])
        self.assertFalse(record['publication_ready'])

    def test_failed_snapshot_preserves_output(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'proyectos.jsonl'
            path.write_text('previous snapshot\n')
            adapter = SollanaAyuntamientoAdapter()
            with patch.object(adapter, '_child', side_effect=ValueError('Source unavailable')), self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('sollana')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Sollana', 'Valencia', '46233'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'licencias.jsonl'
            result = SollanaAyuntamientoAdapter().backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
