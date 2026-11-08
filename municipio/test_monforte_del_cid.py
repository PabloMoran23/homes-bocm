import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.monforte_del_cid import (
    INDEX, SOURCE, HOST, MonforteDelCidAyuntamientoAdapter, ajax_fragment, parse_fragment,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def doc(number, title):
    return f'<a class="gIconLink" href="{HOST}/preview-document/00000000-0000-0000-0000-{number:012d}">{title}</a>'


def more():
    return '<button onclick="wicketAjaxGet(\'../../?x=more\',null)">Mostrar más</button>'


INDEX_HTML = '<table class="TransparencyListPanel"><a class="gIconLink exp">PLAN GENERAL - (CTU 19-09-2008) ( 4 )</a></table>'
FIRST = '<h1>PLAN GENERAL - (CTU 19-09-2008)</h1><table class="TransparencyListPanel">' + doc(1, 'MEMORIA JUSTIFICATIVA') + '</table>' + more()
LAST = '<ajax-response><component><![CDATA[' + doc(2, 'PLANO') + '<a class="gIconLink exp" href="#">MODIFICACIONES ( 2 )</a>]]></component></ajax-response>'


class MonforteTests(unittest.TestCase):
    def run_snapshot(self, responses):
        adapter = MonforteDelCidAyuntamientoAdapter('monforte-del-cid')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_get', side_effect=responses):
                result = adapter.backfill_proyectos(path)
            return result, json.loads(path.read_text())

    def test_groups_documents_and_preserves_date_meaning(self):
        result, row = self.run_snapshot([INDEX_HTML, FIRST, LAST])
        self.assertEqual(result['rows'], 1)
        self.assertEqual(result['inventory_pages'], 2)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_referencia_ctu'], '2008-09-19')
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(row['subcarpetas_excluidas'][0]['document_count'], 2)

    def test_multiple_load_more_responses(self):
        middle = '<ajax-response><component><![CDATA[' + doc(3, 'NORMAS') + more() + ']]></component></ajax-response>'
        result, row = self.run_snapshot([INDEX_HTML.replace('( 4 )', '( 5 )'), FIRST, middle, LAST])
        self.assertEqual(result['inventory_pages'], 3)
        self.assertEqual(len(row['documentos']), 3)

    def test_terminal_ajax_hides_more_without_new_documents(self):
        terminal = '<ajax-response><component><![CDATA[<div style="display:none"></div>]]></component></ajax-response>'
        result, row = self.run_snapshot([INDEX_HTML, FIRST, LAST.replace(']]>', more() + ']]>'), terminal])
        self.assertEqual(result['inventory_pages'], 3)
        self.assertEqual(len(row['documentos']), 2)

    def test_missing_records_fail_instead_of_truncation(self):
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            self.run_snapshot([INDEX_HTML, FIRST.replace(more(), '')])

    def test_repeated_page_fails(self):
        repeated = '<ajax-response><component><![CDATA[' + doc(1, 'MEMORIA JUSTIFICATIVA') + more() + ']]></component></ajax-response>'
        with self.assertRaisesRegex(ValueError, 'no progress'):
            self.run_snapshot([INDEX_HTML, FIRST, repeated])

    def test_forms_navigation_login_not_records(self):
        self.assertEqual(parse_fragment('<a href="/licencia.pdf">Solicitud licencia</a>')[0], {})
        with self.assertRaises(ValueError):
            self.run_snapshot(['<h1>Identifícate</h1>'])
        with self.assertRaises(ValueError):
            ajax_fragment('<ajax-response><redirect>/login</redirect></ajax-response>')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('monforte-del-cid')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MonforteDelCidAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.update_licencias(path, Path(tmp) / 'state.json')['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
