import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from municipio.adapters.camarena import (
    CamarenaAyuntamientoAdapter, HOST, document_links, merge_ajax, parse_projects,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def link(number, title):
    return f'<a href="{HOST}/preview-document/00000000-0000-0000-0000-{number:012d}">{title}</a>'


class CamarenaTests(unittest.TestCase):
    def test_grouping_retains_documents_and_no_inferred_dates(self):
        soup = BeautifulSoup('<table>' + link(1, 'MEMORIA NORMAS SUBSIDIARIAS DE 1986') +
                             link(2, 'PLANO DE NORMAS SUBSIDIARIAS DE 1986') +
                             link(3, 'NORMAS URBANÍSTICAS MODIFICACIÓN DE 1990') + '</table>', 'html.parser')
        rows = parse_projects(list(document_links(soup).values()))
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[1]['anio_documental'], 1990)
        for row in rows:
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])

    def test_pagination_and_count_guard(self):
        initial = '<table>' + link(1, 'MEMORIA NORMAS SUBSIDIARIAS DE 1986') + '''</table>
        <div id="more"><button onclick="wicketAjaxGet('../../?x=example')">Mostrar más</button></div>'''
        xml = '<ajax-response><component id="new"><![CDATA[<tr>' + link(2, 'MODIFICACIÓN PUNTUAL DE NORMAS SUBSIDIARIAS DE 2000') + '</tr>]]></component><component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'
        merged = merge_ajax(BeautifulSoup(initial, 'html.parser'), xml)
        self.assertEqual(len(document_links(merged)), 2)
        self.assertIsNone(merged.find('button'))
        class Response:
            def __init__(self, text):
                self.content = text.encode()
                self.text = text
        for expected, fails in [(2, False), (3, True)]:
            parent = f'''<a onclick="callback">7.3. NORMATIVA URBANÍSTICA ( {expected} )</a>'''
            with tempfile.TemporaryDirectory() as tmp, patch.object(
                CamarenaAyuntamientoAdapter, '_get', side_effect=[Response(parent), Response('7.3. NORMATIVA URBANÍSTICA' + initial), Response(xml)]
            ):
                output = Path(tmp) / 'proyectos.jsonl'
                adapter = CamarenaAyuntamientoAdapter('camarena')
                if fails:
                    with self.assertRaisesRegex(ValueError, 'Incomplete inventory'):
                        adapter.backfill_proyectos(output)
                    self.assertFalse(output.exists())
                else:
                    self.assertEqual(adapter.backfill_proyectos(output)['count'], 2)
                    self.assertEqual(len([json.loads(l) for l in output.read_text().splitlines()]), 2)

    def test_reject_unrecognized_or_empty(self):
        for docs in [[], [{'titulo': 'SOLICITUD LICENCIA 1986', 'url': 'example'}],
                     [{'titulo': 'MODIFICACIÓN DE 2026', 'url': 'example'}]]:
            with self.assertRaises(ValueError):
                parse_projects(docs)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('camarena')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
