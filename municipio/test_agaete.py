"""Offline parser/adapter checks; fixture documents represent separate real instruments."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.agaete import (
    API, AgaeteAyuntamientoAdapter, parse_document_index, parse_inventory,
)


PLAN = 'Aprobación Definitiva de Plan Parcial del SUSNO-1 Las Candelarias de Agaete'
JUDGMENT = ('Aprobación Definitiva de la Sentencia del Tribunal Supremo de 7 de enero de 2014 '
            'por la que se anula el Plan Parcial del Sector SUSNO-1 Las Candelarias, Agaete')
PGO = ('Aprobación Definitiva de Adaptación Básica de Plan General de Ordenación '
       'de Agaete por Pleno COTMAC el 28/07/2005')
ROOT = 'https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/'


def fixture():
    resources = []
    for n, title, desc in [('727', PLAN, PLAN + ', publicado el 06/04/2005 en el BOP 045/05'),
                           ('728', JUDGMENT, JUDGMENT),
                           ('655', PGO, PGO + ', publicado el 16/09/2005 en el BOC 183/05')]:
        resources.append({'id': n, 'name': title, 'description': desc,
                          'url': ROOT + n + '/indice.html', 'format': 'PDF', 'mimetype': 'text/html',
                          'created': '2025-01-01', 'last_modified': '2026-01-01'})
    return {'success': True, 'result': {'name': 'planeamiento-urbanistico-de-agaete',
            'title': 'Planeamiento urbanístico de Agaete', 'num_resources': len(resources),
            'resources': resources}}


class AgaeteTests(unittest.TestCase):
    def test_group_judgment_with_original_plan_and_separate_other_instrument(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual([d['resource_id'] for d in rows[0]['documentos']], ['727', '728'])
        self.assertIn('anula', rows[0]['advertencia_vigencia'])
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertEqual(rows[0]['url'], ROOT + '727/indice.html')

    def test_dates_have_explicit_meaning(self):
        rows = parse_inventory(fixture())
        self.assertEqual(rows[0]['fecha_publicacion'], '2005-04-06')
        self.assertNotIn('fecha_acuerdo', rows[0])
        self.assertEqual(rows[1]['fecha_acuerdo'], '2005-07-28')
        self.assertEqual(rows[1]['fecha_publicacion'], '2005-09-16')
        for row in rows:
            for forbidden in ('fecha', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(forbidden, row)
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '35001')

    def test_all_formats_preserved_and_stable_id(self):
        data = fixture()
        resource = copy.deepcopy(data['result']['resources'][0])
        resource.update(id='zip', url='https://opendata.sitcan.es/download/file.zip', format='SIPU')
        data['result']['resources'].append(resource)
        data['result']['num_resources'] += 1
        row = parse_inventory(data)[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['id'], parse_inventory(fixture())[0]['id'])

    def test_reject_partial_empty_wrong_and_unmatched_judgment(self):
        cases = []
        data = fixture();data['result']['num_resources'] += 1;cases.append(data)
        data = fixture();data['result']['title'] = 'Otro municipio';cases.append(data)
        data = fixture();data['result']['resources'] = [];data['result']['num_resources'] = 0;cases.append(data)
        data = fixture();data['result']['resources'].pop(0);data['result']['num_resources'] -= 1;cases.append(data)
        data = fixture();data['success'] = False;cases.append(data)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_inventory(data)

    def test_index_links_deduplicated_and_provenance_retained(self):
        url = ROOT + '655/indice.html'
        docs = parse_document_index('<a href="TIP/m.pdf">Memoria</a><a href="TIP/m.pdf">Otra</a>', url)
        self.assertEqual(docs, [{'titulo': 'Memoria', 'url': ROOT + '655/TIP/m.pdf',
                                 'source_url': url, 'formato': 'PDF'}])

    def test_index_fail_closed(self):
        for html in ('<p>Sin documentos</p>', '<a rel="next" href="p2">2</a>',
                     '<a href="../727/plan.pdf">Otro plan</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_document_index(html, ROOT + '655/indice.html')

    def test_failed_extraction_preserves_previous_output(self):
        adapter = AgaeteAyuntamientoAdapter('agaete')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl';out.write_text('previous\n')
            with patch.object(adapter, '_fetch', side_effect=ValueError('bad source')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')

    def test_licences_disabled_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            with patch('municipio.adapters.agaete.requests.get') as get:
                result = AgaeteAyuntamientoAdapter('agaete').backfill_licencias(out)
                get.assert_not_called()
            self.assertTrue(result['disabled']);self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
