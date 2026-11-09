"""Parser and traversal regressions; fixtures contain public inventory labels."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from municipio.adapters.venta_de_banos import (
    BASE, VentaDeBanosAyuntamientoAdapter, ajax_html, build_records, parse_entries,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def document(number, title='Memoria'):
    return {'titulo': title, 'url': BASE + '/preview-document/' + f'{number:08d}-0000-0000-0000-000000000000'}


def listing(docs, more=False):
    links = ''.join(f'<a class="gIconLink" href="{d["url"]}">{d["titulo"]}</a>' for d in docs)
    return '<table class="TransparencyListPanel">' + links + '</table>' + (
        '<div class="more_results"><button onclick="wicketAjaxGet(\'../../?x=more\')">Mostrar más</button></div>' if more else '')


class VentaDeBanosTests(unittest.TestCase):
    def test_inventory_parser(self):
        html = '''<table class="TransparencyListPanel"><a class="gIconLink exp" href="#"
            onclick="wicketAjaxGet('?x=folder')">MODIFICACIÓN PGOU (EXPTE. 358/2017)
            <span class="linkExtraInfo"> ( 21 )</span></a></table>'''
        entries, more = parse_entries(html)
        self.assertEqual(entries[0]['titulo'], 'MODIFICACIÓN PGOU (EXPTE. 358/2017)')
        self.assertEqual(entries[0]['count'], 21)
        self.assertIsNone(more)
        with self.assertRaises(ValueError):
            parse_entries('<html>Service unavailable</html>')
        with self.assertRaises(ValueError):
            parse_entries(html.replace('( 21 )', '( unknown )'))

    def test_document_links_and_xml(self):
        doc = document(1)
        xml = '<ajax-response><component><![CDATA[' + listing([doc]) + ']]></component></ajax-response>'
        entries, _ = parse_entries(ajax_html(xml), initial=False)
        self.assertEqual(entries[0]['url'], doc['url'])
        with self.assertRaises(ValueError):
            ajax_html('<ajax-response><redirect>login</redirect></ajax-response>')
        with self.assertRaises(ValueError):
            parse_entries(listing([{'titulo': 'bad', 'url': 'https://example.com/file.pdf'}]))

    def test_all_pages_even_when_action_is_reused(self):
        adapter = VentaDeBanosAyuntamientoAdapter('venta-de-banos')
        adapter._get = Mock(return_value=Mock(text=listing([document(1)], more=True)))
        def response(docs, more):
            return Mock(text='<ajax-response><component><![CDATA[' + listing(docs, more) + ']]></component></ajax-response>')
        adapter._action = Mock(side_effect=[response([document(2)], True), response([document(3)], False)])
        rows = adapter._listing(BASE + '/transparency/folder/')
        self.assertEqual(len(rows), 3)
        self.assertEqual(adapter._action.call_count, 2)

    def test_pagination_stall_and_count_mismatch_fail(self):
        adapter = VentaDeBanosAyuntamientoAdapter('venta-de-banos')
        html = listing([document(1)], more=True)
        adapter._get = Mock(return_value=Mock(text=html))
        adapter._action = Mock(return_value=Mock(text='<ajax-response><component><![CDATA[' + html + ']]></component></ajax-response>'))
        with self.assertRaisesRegex(ValueError, 'no new entries'):
            adapter._listing(BASE + '/transparency/folder/')
        adapter._listing = Mock(return_value=[document(1)])
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            adapter._documents(BASE + '/transparency/folder/', 2, set())

    def test_group_versions_and_loose_plan_documents(self):
        groups = [
            ('ESTUDIO DE DETALLE EN LA ACTUACIÓN AISLADA AA-UN-18 DEL PGOU DE VENTA DE BAÑOS', BASE+'/one', [document(1)]),
            ('ESTUDIO DE DETALLE DILIGENCIADO EN LA ACTUACIÓN AISLADA AA-UN-18 DEL PGOU DE VENTA DE BAÑOS', BASE+'/two', [document(2)]),
            ('PLAN PARCIAL SUR-SE 07 "HUERTA DE LOS MARISTAS" (EXPT. 1075/2022)', BASE+'/three', [document(3)]),
            ('Plan Parcial SUR-SE 07', BASE+'/empty', []),
        ]
        rows = build_records(BASE, groups, [document(4, 'Planos Plan Parcial SUR-SE 07')])
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [2, 2])
        self.assertEqual(next(r for r in rows if r['expediente'])['expediente'], '1075/2022')
        self.assertEqual(len(next(r for r in rows if 'AA-UN-18' in r['titulo'])['urls_instrumento']), 2)
        with self.assertRaisesRegex(ValueError, 'Ungrouped'):
            build_records(BASE, groups, [document(5, 'Formulario de licencia')])

    def test_dates_not_inferred_from_documents(self):
        groups = [('Proyecto normalización y urbanización Av. Castilla y León', BASE+'/folder',
                   [document(1, 'BOCyL n.º 224, 18 de noviembre de 2024 - Castilla y Leon')])]
        row = build_records(BASE, groups, [])[0]
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        row = build_records(BASE, [], [document(2, 'Aprobación definitiva Estudio de Detalle Calle Casado del Alisal, 14')])[0]
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertIsNone(row['fecha_aprob'])

    def test_manifest_resolution_and_disabled_licences(self):
        manifest = load_manifest('venta-de-banos')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('34023', 'Palencia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, VentaDeBanosAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
