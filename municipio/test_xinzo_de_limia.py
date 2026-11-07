"""Offline parser/refresh tests; fixture follows the inspected Xunta HTML schema."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.xinzo_de_limia import (
    BASE, HEADERS, SOURCE, XinzoDeLimiaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def fixture(number='ROTPG/P/30/2023', title='ED GUNTIMIL, NO CONCELLO DE XINZO DE LIMIA', pager='', docs=True):
    values = ['Estudo de Detalle', 'Instrumentos', title, '22/05/2023', number,
              'Ourense', 'Municipal', '03/11/2022', '29/11/2022', '08/06/2023', '',
              '<a href="http://www.planeamentourbanistico.xunta.es/siotuga/rexistro/index.php?url=XINZO_DE_LIMIA_ED_GUNTIMIL_03.11.2022.zip">Descargar</a>' if docs else '']
    return ('<select name="provincia"><option selected value="32">Ourense</option></select>'
            '<select name="concello"><option selected value="696">Xinzo de Limia</option></select>'
            '<table id="edit-table"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in HEADERS) +
            '</tr></thead><tbody><tr>' + ''.join(f'<td>{v}</td>' for v in values) +
            '</tr></tbody></table>' + pager)


class XinzoTests(unittest.TestCase):
    def test_dates_provenance_and_missing_documents(self):
        rows, pages = parse_inventory(fixture())
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '32032')
        self.assertEqual(row['fecha_aprob'], '2022-11-03')
        self.assertEqual(row['fecha_inscripcion'], '2023-05-22')
        self.assertEqual(row['fecha_publicacion_dog'], '2022-11-29')
        self.assertEqual(row['fecha_publicacion_bop'], '2023-06-08')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertNotIn('fase', row)
        self.assertEqual(row['source'], 'xunta')
        self.assertEqual(row['documentos'][0]['registro'], row['registro'])
        self.assertFalse(pages)
        missing = parse_inventory(fixture(docs=False))[0][0]
        self.assertEqual(missing['documentos'], [])
        self.assertEqual(missing['document_status'], 'not_linked_in_register')

    def test_reject_wrong_municipality_schema_dates_and_empty_inventory(self):
        for html in [fixture().replace('value="696"', 'value="692"'),
                     fixture(title='ED NO CONCELLO DE VILAR DE BARRIO'),
                     fixture().replace('<td>Ourense</td>', '<td>Lugo</td>'),
                     fixture().replace('Fecha inscripción', 'Fecha'),
                     fixture().replace('03/11/2022', '31/02/2022'),
                     fixture().replace('<tbody><tr>', '<tbody>').replace('</tr></tbody>', '</tbody>')]:
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_complete_pagination_preserves_filters(self):
        pager = '<ul class="pagination"><li><a href="?page=1" rel="next">Siguiente</a></li></ul>'
        second = BASE + '?provincia=32&concello=696&page=1'
        adapter = XinzoDeLimiaAyuntamientoAdapter('xinzo-de-limia')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[fixture(pager=pager), fixture(number='RPG/00007/2018', title='ED EN BARONZÁS, NO CONCELLO DE XINZO DE LIMIA')]) as fetch:
            output = Path(tmp) / 'rows.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['rows'], 2)
            self.assertEqual([c.args[0] for c in fetch.call_args_list], [SOURCE, second])
            self.assertEqual(len(output.read_text().splitlines()), 2)

    def test_pagination_failure_preserves_previous_output(self):
        pager = '<ul class="pagination"><a href="?page=1">2</a></ul>'
        adapter = XinzoDeLimiaAyuntamientoAdapter('xinzo-de-limia')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=fixture(pager=pager)):
            output = Path(tmp) / 'rows.jsonl'
            output.write_text('previous snapshot\n')
            with self.assertRaisesRegex(ValueError, 'Repeated inventory page'):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')
        with self.assertRaisesRegex(ValueError, 'changes municipality'):
            parse_inventory(fixture(pager=pager.replace('?page=1', '?page=1&amp;concello=692')))

    def test_documents_grouped_by_register_number(self):
        pager = '<ul class="pagination"><a href="?page=1">2</a></ul>'
        second = fixture().replace('2022.zip', '2022_anexo.zip')
        # A second distinct instrument avoids an identical-page signature.
        extra = fixture(number='RPG/00007/2018', title='ED EN BARONZÁS, NO CONCELLO DE XINZO DE LIMIA')
        second = second.replace('</tbody>', extra.split('<tbody>')[1].split('</tbody>')[0] + '</tbody>')
        adapter = XinzoDeLimiaAyuntamientoAdapter('xinzo-de-limia')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[fixture(pager=pager), second]):
            output = Path(tmp) / 'rows.jsonl'
            adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(rows[0]['documentos']), 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('xinzo-de-limia')
        self.assertEqual(manifest.provincia, 'Ourense')
        self.assertFalse(manifest.licencias.enabled)
        adapter = XinzoDeLimiaAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
