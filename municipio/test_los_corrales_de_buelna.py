"""Offline parser and pagination checks; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from municipio.adapters.los_corrales_de_buelna import (
    BASE, SOURCE, LosCorralesDeBuelnaAyuntamientoAdapter, ajax_html,
    group_projects, parse_inventory,
)


def doc(name, uid):
    return f'<tr><td class="class_name"><a class="gIconLink" href="{BASE}/preview-document/{uid}">{name}</a></td></tr>'


def more():
    return '<button onclick="wicketAjaxGet(\'../?x=more\')">Mostrar más</button>'


def xml(fragment):
    return '<ajax-response><component id="rows"><![CDATA[' + fragment + ']]></component></ajax-response>'


class LosCorralesParserTests(unittest.TestCase):
    def setUp(self):
        self.adapter = LosCorralesDeBuelnaAyuntamientoAdapter('los-corrales-de-buelna')
        self.entries = [
            {'titulo': '2019-95 Anuncio informe Ambiental Estratégico de la Modificación Puntual Número 1 del PGOU', 'url': BASE + '/preview-document/mp1'},
            {'titulo': 'Documento de alcance de Estudio ambiental estratégico del Plan Parcial del sector de suelo urbano no consolidado nº 10', 'url': BASE + '/preview-document/sunc10'},
            {'titulo': 'PUBLICACION EN EL BOC APROBACION DEFINITIVA PGOU 2015', 'count': 11, 'callback': BASE + '/?x=folder'},
        ]

    def test_folder_count_and_document_provenance(self):
        html = '<table>' + doc('Informe ambiental', 'one') + '''<tr><td class="class_name">
        <a class="gIconLink" onclick="wicketAjaxGet('../?x=folder')">PGOU<span class="linkExtraInfo"> ( 11 )</span></a>
        </td></tr></table>'''
        entries, next_url = parse_inventory(html, SOURCE)
        self.assertEqual(entries[1]['titulo'], 'PGOU')
        self.assertEqual(entries[1]['count'], 11)
        self.assertEqual(entries[0]['url'], BASE + '/preview-document/one')
        self.assertIsNone(next_url)

    def test_pagination_includes_eleventh_document(self):
        first = '<table>' + ''.join(doc('2015-1484', str(i)) for i in range(10)) + '</table>' + more()
        last = xml(doc('2015-1484 (10)', '10') + '<div style="display:none"></div>')
        self.adapter._get = Mock(side_effect=[SimpleNamespace(text=first), SimpleNamespace(text=last)])
        entries = self.adapter._inventory(SOURCE)
        self.assertEqual(len(entries), 11)
        self.assertEqual(entries[-1]['url'], BASE + '/preview-document/10')

    def test_pagination_loop_fails(self):
        self.adapter._get = Mock(side_effect=[SimpleNamespace(text='<table>' + doc('a', 'a') + '</table>' + more()), SimpleNamespace(text=xml(doc('b', 'b') + more()))])
        with self.assertRaisesRegex(ValueError, 'loop'):
            self.adapter._inventory(SOURCE)

    def test_empty_or_login_page_fails(self):
        self.adapter._get = Mock(return_value=SimpleNamespace(text='<h1>Identifícate</h1>'))
        with self.assertRaisesRegex(ValueError, 'Empty inventory'):
            self.adapter._inventory(SOURCE)

    def test_grouping_and_date_semantics(self):
        docs = [{'titulo': f'2015-1484 ({i})', 'url': BASE + '/preview-document/' + str(i)} for i in range(11)]
        rows = group_projects(self.entries, SOURCE + 'pgou/', docs)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[2]['documentos']), 11)
        self.assertEqual(rows[0]['fase'], 'informe ambiental estratégico')
        self.assertEqual(rows[1]['fase'], 'documento de alcance del estudio ambiental estratégico')
        self.assertEqual(rows[2]['fase'], 'aprobación definitiva')
        for row in rows:
            for key in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[key])
            self.assertEqual(row['codigo_ine'], '39025')

    def test_unrelated_documents_not_projects(self):
        for title in ['Solicitud de licencia de obra', 'Licitación de servicios', 'Fiestas patronales']:
            with self.assertRaisesRegex(ValueError, 'semantic review'):
                group_projects([{'titulo': title, 'url': SOURCE}], SOURCE, [])

    def test_external_document_and_invalid_ajax_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory('<td class="class_name"><a class="gIconLink" href="https://example.org/preview-document/1">Plan</a></td>', SOURCE)
        with self.assertRaises(ValueError):
            ajax_html('<ajax-response><redirect>login</redirect></ajax-response>')

    def test_count_mismatch_preserves_existing_output(self):
        self.adapter.source_urls = set()
        self.adapter._folder = Mock(side_effect=[SOURCE + 'urban/', SOURCE + 'pgou/'])
        self.adapter._inventory = Mock(side_effect=[
            [{'titulo': '9. URBANISMO', 'count': 13, 'callback': BASE + '/?x=a'}],
            self.entries,
            [{'titulo': '2015-1484', 'url': BASE + '/preview-document/one'}],
        ])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaisesRegex(ValueError, 'Incomplete PGOU'):
                self.adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = self.adapter.backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
