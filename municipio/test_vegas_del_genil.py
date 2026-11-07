import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from bs4 import BeautifulSoup

from municipio.adapters.vegas_del_genil import (
    Inventory, SOURCE, VegasDelGenilAyuntamientoAdapter, ajax_components,
    build_records, document,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def anchor(text, **attrs):
    soup = BeautifulSoup('<a></a>', 'html.parser')
    a = soup.a
    a.string = text
    a.attrs.update(attrs)
    return a


def doc(name, uid):
    return document(anchor(name, href=SOURCE.replace('/transparency/', '/preview-document/') + uid), SOURCE)


D1 = doc('Memoria', '00000000-0000-0000-0000-000000000001')
D2 = doc('Planos', '00000000-0000-0000-0000-000000000002')


class ParserTests(unittest.TestCase):
    def test_grouping_documents_and_distinct_pue26(self):
        packages = [
            ('Aprobación estudio de detalle P-U.E-2', SOURCE+'a/', [D1]),
            ('GE 2845 PROYECTO URBANIZACION PUE2', SOURCE+'b/', [D2]),
            ('GE 3414 PROYECTO URBANIZACION PUE 26', SOURCE+'c/', [D1]),
            ('CONSULTAS PREVIAS EXP 825/2024 DOCUMENTO AVANCE P PP8', SOURCE+'d/', [D1]),
            ('GE 825/2024 A INICIAL JUNTA COMPENSACION P PP8', SOURCE+'e/', [D2]),
        ]
        rows = build_records(packages, [], SOURCE)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1, 2])
        for row in rows:
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])

    def test_exclusions_and_no_placeholder(self):
        for title in ['Solicitud licencia obras', 'Licitación proyecto de obra', 'Anuncio', 'GE 796 2026 CONSULTAS PUBLICAS']:
            with self.assertRaises(ValueError):
                build_records([(title, SOURCE, [D1])], [], SOURCE)
        with self.assertRaises(ValueError):
            build_records([('Proyecto urbanizacion PUE2', SOURCE, [])], [], SOURCE)

    def test_root_documents_grouped_without_exposing_title_attributes(self):
        notices = [anchor('Decreto inicial', href=D1['url'], title='Expediente 4916/2022 -- EXP. APROBACIÓN ESTUDIO DE DETALLE CALLE ENCINA --'),
                   anchor('Corrección de errata', href=D2['url'], title='EXP. APROBACIÓN ESTUDIO DE DETALLE CALLE ENCINA (corrección de errata)')]
        rows = build_records([], notices, SOURCE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertNotIn('title', rows[0]['documentos'][0])

    def test_pagination_consumes_all_pages(self):
        client = Inventory()
        first = '<table class="TransparencyListPanel"><a class="gIconLink">one</a></table><div class="more_results"><button onclick="wicketAjaxGet(\'/?x=next\',null)">Mostrar más</button></div>'
        second = '<ajax-response><component><![CDATA[<tr><td><a class="gIconLink">two</a></td></tr>]]></component><component><![CDATA[<div class="more_results"></div>]]></component></ajax-response>'
        client.get = Mock(side_effect=[Mock(text=first), Mock(text=second)])
        self.assertEqual([a.text for a in client.listing(SOURCE)], ['one', 'two'])
        self.assertEqual(client.get.call_count, 2)

    def test_hidden_pagination_end(self):
        client = Inventory()
        first = """<table class="TransparencyListPanel"><a class="gIconLink">one</a></table><div id="more" class="more_results"><button onclick="wicketAjaxGet('/?x=next',null)">Mostrar más</button></div>"""
        last = """<ajax-response><component><![CDATA[<a class="gIconLink">two</a>]]></component><component><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>"""
        client.get = Mock(side_effect=[Mock(text=first), Mock(text=last)])
        self.assertEqual(len(client.listing(SOURCE)), 2)

    def test_plan_parcial_and_document_identity(self):
        rows = build_records([('Instrumento Plan parcial de Ordenación Belicena B-PP-7', SOURCE, [D1])], [], SOURCE)
        self.assertEqual(rows[0]['source_entity_type'], 'documento')
        self.assertEqual(rows[0]['documentos'][0]['url'], D1['url'])

    def test_pagination_failures(self):
        with self.assertRaises(ValueError):
            ajax_components('<html>unexpected</html>')
        client = Inventory()
        client.get = Mock(return_value=Mock(text='<html>login</html>'))
        with self.assertRaises(ValueError):
            client.listing(SOURCE)
        with self.assertRaises(ValueError):
            document(anchor('Doc', href='https://example.com/doc.pdf'), SOURCE)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('vegas-del-genil')
        self.assertEqual(manifest.provincia, 'Granada')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), VegasDelGenilAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = load_portal_adapter(manifest).backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
