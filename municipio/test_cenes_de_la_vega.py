"""Offline parser/coverage tests; live verification is recorded separately in evidence/."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from municipio.adapters.cenes_de_la_vega import (
    BASE, SOURCES, CenesDeLaVegaAyuntamientoAdapter, parse_entries, parse_more,
)
from municipio.manifest import load_manifest, load_yaml

PAGE = BASE + '/transparency/11111111-1111-1111-1111-111111111111/'
DOC = BASE + '/preview-document/22222222-2222-2222-2222-222222222222'


def document(title='MEMORIA', target=DOC):
    return f'<tr><td><a class="gIconLink" href="{target}">{title}</a></td></tr>'


def folder(title='PGOU. ADAPTACIÓN PARCIAL A LA LOUA DE LAS NNSS', count=1):
    return f'''<tr><td><a class="gIconLink exp" href="#" onclick="wicketAjaxGet('../../?x=folder',null)">{title}<span class="linkExtraInfo"> ( {count} )</span></a></td></tr>'''


def more():
    return '''<div class="more_results" id="more"><button onclick="wicketAjaxGet('../../?x=more',null)">Mostrar más</button></div>'''


def listing(rows, control=''):
    return '<table class="TransparencyListPanel">' + rows + '</table>' + control


def ajax(rows='', control='<div id="more" style="display:none"></div>'):
    return f'<ajax-response><component id="row"><![CDATA[{rows}]]></component><component id="more"><![CDATA[{control}]]></component></ajax-response>'


class CenesParserTests(unittest.TestCase):
    def test_table_scope_and_folder_identity(self):
        entries, next_url = parse_entries(document('navigation') + listing(folder(count=13)), PAGE)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['title'], 'PGOU. ADAPTACIÓN PARCIAL A LA LOUA DE LAS NNSS')
        self.assertEqual(entries[0]['count'], 13)
        self.assertIsNone(next_url)

    def test_missing_and_offsite_sources_fail(self):
        for text in ('<h1>Error</h1>', listing(document(target='https://example.org/document'))):
            with self.assertRaises(ValueError):
                parse_entries(text, PAGE)

    def test_ajax_rows_and_explicit_terminal(self):
        entries, next_url = parse_more(ajax(document()), PAGE, 'more')
        self.assertEqual(entries[0]['url'], DOC)
        self.assertIsNone(next_url)
        self.assertEqual(parse_more(ajax(), PAGE, 'more'), ([], None))
        for xml in ('<ajax-response/>', ajax(control='<div id="more"></div>'), ajax(control=more())):
            with self.assertRaises(ValueError):
                parse_more(xml, PAGE, 'more')

    def test_all_pages_even_when_action_url_is_reused(self):
        adapter = CenesDeLaVegaAyuntamientoAdapter('cenes-de-la-vega')
        doc2 = DOC.replace('22222222-', '33333333-', 1)
        adapter._get = Mock(side_effect=[
            SimpleNamespace(url=PAGE, text=listing(document(), more())),
            SimpleNamespace(url=BASE + '/?x=more', text=ajax(document('PLANO', doc2), more())),
            SimpleNamespace(url=BASE + '/?x=more', text=ajax()),
        ])
        _, entries = adapter._listing(PAGE)
        self.assertEqual(len(entries), 2)
        self.assertEqual(adapter._get.call_count, 3)
        headers = adapter._get.call_args.kwargs['headers']
        self.assertEqual(headers['Wicket-Ajax'], 'true')

    def test_repeated_page_fails(self):
        adapter = CenesDeLaVegaAyuntamientoAdapter('cenes-de-la-vega')
        adapter._get = Mock(side_effect=[SimpleNamespace(url=PAGE, text=listing(document(), more())),
                                       SimpleNamespace(url=BASE, text=ajax(document(), more()))])
        with self.assertRaisesRegex(ValueError, 'repeated'):
            adapter._listing(PAGE)

    def test_document_count_mismatch_fails(self):
        adapter = CenesDeLaVegaAyuntamientoAdapter('cenes-de-la-vega')
        adapter.visited = set()
        adapter._listing = Mock(return_value=(PAGE, [{'kind': 'document', 'title': 'Memoria', 'url': DOC}]))
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            adapter._documents(PAGE, 2)

    def test_group_annexes_and_exclude_non_instruments(self):
        adapter = CenesDeLaVegaAyuntamientoAdapter('cenes-de-la-vega')
        adapter.visited, adapter.rows = set(), []
        adapter._listing = Mock(return_value=(PAGE, [
            {'kind': 'folder', 'title': 'Innovación del PGOU en el Sector Cerro del Oro', 'count': 2, 'action': PAGE},
            {'kind': 'folder', 'title': 'Solicitud de licencia de obra', 'count': 1, 'action': 'excluded'},
            {'kind': 'folder', 'title': 'Licitación servicio de redacción PGOM', 'count': 1, 'action': 'excluded'},
            {'kind': 'folder', 'title': 'Información fiscal', 'count': 1, 'action': 'excluded'},
        ]))
        docs = [{'titulo': 'Memoria', 'url': DOC}, {'titulo': 'Plano', 'url': DOC + '-other'}]
        adapter._documents = Mock(return_value=(PAGE, docs))
        adapter._discover(PAGE, SOURCES[1])
        self.assertEqual(len(adapter.rows), 1)
        row = adapter.rows[0]
        self.assertEqual(row['documentos'], docs)
        self.assertEqual(row['codigo_ine'], '18047')
        self.assertFalse(row['publication_ready'])
        for key in ('lat', 'lon', 'fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'fase'):
            self.assertNotIn(key, row)

    def test_nested_documents_retain_provenance(self):
        adapter = CenesDeLaVegaAyuntamientoAdapter('cenes-de-la-vega')
        adapter.visited = set()
        child = PAGE.replace('11111111-', '44444444-', 1)
        adapter._listing = Mock(side_effect=[
            (PAGE, [{'kind': 'folder', 'title': '01. INNOVACIÓN', 'count': 1, 'action': child}]),
            (child, [{'kind': 'document', 'title': 'Memoria', 'url': DOC}]),
        ])
        _, docs = adapter._documents(PAGE, 1)
        self.assertEqual(docs[0]['inventory_url'], child)
        self.assertEqual(docs[0]['carpeta'], ['01. INNOVACIÓN'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cenes-de-la-vega')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('18047', 'Granada'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'licencias.jsonl'
            result = CenesDeLaVegaAyuntamientoAdapter(manifest.slug).backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
