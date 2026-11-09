import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.villanueva_de_los_infantes import (
    HEADERS, SOURCE, VillanuevaDeLosInfantesAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def table(rows):
    return '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in HEADERS) + '</tr></thead><tbody>' + rows + '</tbody></table>'


def row(title, date='-', docs=None, last='-'):
    docs = docs or '<a href="/wp-content/uploads/plan.pdf">Normativa</a>'
    return f'<tr><td>{title}</td><td>{date}</td><td>{docs}</td><td>{last}</td></tr>'


class PlanningTests(unittest.TestCase):
    def test_group_documents_and_exclude_nonprojects(self):
        html = table(row('M.P. Nº 1 NN.SS. El Cartabón', 'DOCM nº 52, 01/05/2001',
                         last='<a href="/wp-content/uploads/mapa.pdf">Planos</a>') +
                     row('Ordenanza municipal de edificación') + row('Solicitud licencia de obras') +
                     row('Declaración conjunto histórico artístico') + row('Fiestas locales'))
        records = parse_inventory(html)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]['documentos']), 2)
        self.assertEqual(records[0]['fecha_publicacion'], '2001-05-01')
        for field in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, records[0])

    def test_displaced_publication_and_document_dedup(self):
        link = '<a href="/wp-content/uploads/texto.pdf">Acceso texto refundido</a>'
        records = parse_inventory(table(row('Texto refundido y vigente de las NN.SS.', link, link, 'DOCM nº 164, 26/08/2022')))
        self.assertEqual(records[0]['fecha_publicacion'], '2022-08-26')
        self.assertEqual(len(records[0]['documentos']), 1)
        self.assertEqual(len(records[0]['documentos'][0]['referencias']), 2)

    def test_historical_version_and_multiple_publications(self):
        records = parse_inventory(table(
            row('Revisión normas subsidiarias (DEROGADA DOCM 26/08/2022)', 'DOCM nº 33, 26/07/1996') +
            row('M.P Nº 3 NN.SS. UE 24', 'DOCM nº 138, 12/07/2005 y nº 61, 30/04/2003') +
            row('Plan Parcial de Mejora del SAUI-11 QUIÑON INDUSTRIAL')))
        self.assertEqual(records[0]['vigencia_segun_inventario'], 'derogada')
        self.assertEqual(records[0]['fecha_publicacion'], '1996-07-26')
        self.assertEqual(records[1]['fechas_publicacion'], ['2003-04-30', '2005-07-12'])
        self.assertNotIn('fecha_publicacion', records[1])
        self.assertNotIn('fecha_publicacion', records[2])
        self.assertEqual(len({r['id'] for r in records}), 3)
        reordered = parse_inventory(table(row('Plan Parcial de Mejora del SAUI-11 QUIÑON INDUSTRIAL')))
        self.assertEqual(reordered[0]['id'], records[2]['id'])

    def test_fail_closed(self):
        valid = table(row('Plan Parcial de Mejora'))
        for html in ['<html>Unavailable</html>', table(row('Solicitud licencia')),
                     valid + '<a rel="next" href="?page=2">2</a>',
                     valid + '<div class="pagination">2</div>',
                     table(row('Plan Parcial', docs='<a href="https://example.org/a.pdf">x</a>')),
                     table('<tr><td>Plan Parcial</td></tr>'),
                     table(row('Plan Parcial', docs='sin enlaces'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_method_contract_and_manifest(self):
        manifest = load_manifest('villanueva-de-los-infantes')
        self.assertFalse(manifest.licencias.enabled)
        response = Mock(text=table(row('Plan Parcial de Mejora')), url=SOURCE)
        adapter = VillanuevaDeLosInfantesAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.villanueva_de_los_infantes.requests.get', return_value=response):
            output = Path(d) / 'out.jsonl'
            self.assertEqual(adapter.backfill_proyectos(output)['count'], 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '13093')
            original = output.read_text()
            adapter.update_proyectos(output, Path(d) / 'state.json')
            self.assertEqual(output.read_text(), original)
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
