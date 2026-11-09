import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.albuixech import (
    AlbuixechAyuntamientoAdapter, HOST, SOURCE, entries, fragment, project,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

DOC = f'https://{HOST}/preview-document/fe248cd1-b704-46d6-ac9e-839cfa81522a'


def html(body):
    return '<div id="content"><table class="TransparencyListPanel">' + body + '</table></div>'


def folder(title, count, token):
    return (f'<a class="gIconLink exp" onclick="wicketAjaxGet(\'?x={token}\')">'
            f'{title}<span class="linkExtraInfo"> ( {count} )</span></a>')


def document(url=DOC, title='46014-1000 1986-0085 ACUERDO'):
    return f'<a class="gIconLink" href="{url}">{title}</a>'


class AlbuixechTests(unittest.TestCase):
    def test_manifest_contract(self):
        m = load_manifest('albuixech')
        self.assertIsInstance(load_portal_adapter(m), AlbuixechAyuntamientoAdapter)
        raw = load_yaml(m.path)
        self.assertEqual((raw['codigo_ine'], m.provincia), ('46014', 'Valencia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(m.licencias.enabled)

    def test_dates_not_inferred_from_names_or_clock(self):
        docs, _, _ = entries(fragment(html(document())), SOURCE)
        row = project('NORMES SUBSIDIÀRIES', SOURCE, docs)
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertEqual(row['documentos'][0]['titulo'], '46014-1000 1986-0085 ACUERDO')

    def test_xml_components_and_duplicate_links(self):
        page = '<?xml version="1.0"?><ajax-response><component id="x"><![CDATA[' + document() * 2 + ']]></component></ajax-response>'
        docs, folders, more = entries(fragment(page), SOURCE)
        self.assertEqual(len(docs), 1)
        self.assertEqual(folders, [])
        self.assertIsNone(more)

    def test_reject_changed_or_login_markup(self):
        for page in ('<html>Identifícate</html>', '<?xml version="1.0"?><ajax-response><redirect>login</redirect></ajax-response>'):
            with self.assertRaises(ValueError):
                fragment(page)
        with self.assertRaises(ValueError):
            entries(fragment(html('<a>Siguiente</a>')), SOURCE)

    def test_external_links_are_not_documents(self):
        docs, _, _ = entries(fragment(html(document('https://visor.gva.es/visor/'))), SOURCE)
        self.assertEqual(docs, {})

    def test_complete_pagination_and_grouping(self):
        adapter = AlbuixechAyuntamientoAdapter('albuixech')
        more = '<button onclick="wicketAjaxGet(\'?x=more\')">Mostrar más</button>'
        second = DOC.rsplit('/', 1)[0] + '/5212bb44-c2ae-4751-a6db-a4d33945c96a'
        responses = [
            (SOURCE, html(folder('6.1.1. NORMES SUBSIDIÀRIES', 2, 'root'))),
            (SOURCE + 'root/', html(folder('NORMES SUBSIDIÀRIES', 2, 'instrument'))),
            (SOURCE + 'instrument/', html(document() + more)),
            (SOURCE, '<?xml version="1.0"?><ajax-response><component id="x"><![CDATA[' + document(second, 'MEMORIA') + ']]></component></ajax-response>'),
        ]
        with tempfile.TemporaryDirectory() as td, patch.object(adapter, '_fetch', side_effect=responses):
            out = Path(td) / 'rows.jsonl'
            result = adapter.backfill_proyectos(out)
            rows = [json.loads(x) for x in out.read_text().splitlines()]
            self.assertEqual(result['documents'], 2)
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]['documentos']), 2)

    def test_incomplete_inventory_preserves_previous_output(self):
        adapter = AlbuixechAyuntamientoAdapter('albuixech')
        responses = [(SOURCE, html(folder('6.1.1. NORMES SUBSIDIÀRIES', 2, 'r'))),
                     (SOURCE, html(folder('NORMES SUBSIDIÀRIES', 2, 'i'))),
                     (SOURCE, html(document()))]
        with tempfile.TemporaryDirectory() as td, patch.object(adapter, '_fetch', side_effect=responses):
            out = Path(td) / 'rows.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_empty_instrument_rejected(self):
        with self.assertRaises(ValueError):
            project('NORMES SUBSIDIÀRIES', SOURCE, {})


if __name__ == '__main__':
    unittest.main()
