"""Offline parser and pagination regression tests; no network or evidence required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alameda import (
    BASE, INVENTORIES, AlamedaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def document(number, title):
    return (f'<tr><td><a href="{BASE}/preview-document/'
            f'00000000-0000-0000-0000-{number:012d}">{title}</a></td></tr>')


def inventory(title, rows, more=False):
    return (f'<h1>{title}</h1><table class="TransparencyListPanel"><tbody>{rows}</tbody></table>'
            + ('<div class="more_results" id="more"><button onclick="wicketAjaxGet(\'../../?x=page2\')">Mostrar más</button></div>' if more else ''))


class AlamedaTests(unittest.TestCase):
    def test_group_technical_and_procedural_documents_without_invented_metadata(self):
        _, title, kind, required = INVENTORIES[0]
        html = inventory(title, document(1, 'PBOMA TOMO I') + document(2, 'PBOMA TOMO II')
                         + document(3, 'DECRETO 2025-0482 [CONSULTA AVANCE PBOM]'))
        row = parse_inventory(html, BASE + '/transparency/plan/', title, kind, required)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['codigo_ine'], '29001')
        self.assertEqual(row['provincia'], 'Málaga')
        for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])
        duplicate = html.replace('</tbody>', document(1, 'PBOMA TOMO I') + '</tbody>')
        self.assertEqual(len(parse_inventory(duplicate, BASE + '/transparency/plan/', title, kind, required)['documentos']), 3)

    def test_forms_empty_wrong_folder_and_incomplete_pages_rejected(self):
        _, title, kind, required = INVENTORIES[0]
        for html in (inventory(title, ''), inventory(title, document(1, 'Solicitud de licencia')),
                     inventory(title, document(1, 'DECRETO 2025-0482')),
                     inventory('Otra carpeta', document(1, 'PBOMA TOMO I')),
                     inventory(title, document(1, 'PBOMA TOMO I'), more=True)):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, BASE, title, kind, required)

    def test_foreign_document_rejected(self):
        _, title, kind, required = INVENTORIES[0]
        html = inventory(title, document(1, 'PBOMA TOMO I')).replace(BASE, 'https://example.org')
        with self.assertRaises(ValueError):
            parse_inventory(html, BASE, title, kind, required)

    def test_live_protocol_pagination_and_two_instruments_stay_separate(self):
        # Wicket appends rows via components and replaces the pagination region.
        pbom = inventory(INVENTORIES[0][1], document(1, 'PBOMA TOMO I'), more=True)
        housing = inventory(INVENTORIES[1][1], document(9, '1_TomoIMemoria.pdfTomoIMemoria'))
        xml = ('<ajax-response><component id="new" encoding="wicket1"><![CDATA['
               + document(2, 'DECRETO 2025-0482 [CONSULTA AVANCE PBOM]^')
               + ']]></component><component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>')
        adapter = AlamedaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get', side_effect=[pbom, xml, housing]) as get:
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(x) for x in output.read_text().splitlines()]
            self.assertEqual(result['live_records'], 2)
            self.assertEqual(result['document_count'], 3)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(len(rows[1]['documentos']), 1)
            self.assertEqual(rows[0]['documentos'][1]['titulo'], 'DECRETO 2025-0482 [CONSULTA AVANCE PBOM]')
            self.assertEqual(get.call_args_list[1].args[0], BASE + '/?x=page2')
            self.assertTrue(get.call_args_list[1].kwargs['ajax'])
            self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_stuck_pagination_fails_without_overwriting_previous_snapshot(self):
        pbom = inventory(INVENTORIES[0][1], document(1, 'PBOMA TOMO I'), more=True)
        # No replacement of the load-more control => repeat callback must fail.
        xml = '<ajax-response><component id="new"><![CDATA[' + document(2, 'PBOMA TOMO II') + ']]></component></ajax-response>'
        adapter = AlamedaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get', side_effect=[pbom, xml]):
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_malformed_ajax_rejected(self):
        pbom = inventory(INVENTORIES[0][1], document(1, 'PBOMA TOMO I'), more=True)
        adapter = AlamedaAyuntamientoAdapter()
        with patch.object(adapter, '_get', side_effect=[pbom, '<html>expired session</html>']):
            with self.assertRaises(ValueError):
                adapter._inventory(BASE + '/transparency/folder/')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('alameda')
        self.assertEqual(manifest.provincia, 'Málaga')
        self.assertTrue(manifest.proyectos.enabled)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = AlamedaAyuntamientoAdapter().backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
