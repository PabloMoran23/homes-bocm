"""Offline parser tests; representative AUCAN tree structure, no network needed."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.medio_cudeyo import (
    parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def folder(text, *children):
    return {'id': None, 'text': text, 'type': 'folder', 'nodes': list(children)}


def doc(id, text):
    return {'id': id, 'text': text, 'type': None, 'nodes': None}


def inventory():
    amendment = folder('Modificación Puntual nº 1 del PGOU (Ayto. 24/09/2015; BOC 28/10/2015)',
                       folder('Documentos', doc(22880, 'Memoria'), doc(22880, 'Memoria')),
                       folder('Cartografía', doc(22882, 'Planos')))
    plan = folder('PGOU de Medio Cudeyo (CROTU 16/11/2010; BOC 18/02/2011)',
                  folder('Aprobación definitiva', doc(22684, 'Memoria'),
                         doc(22759, 'ANULACIÓN Sector 22 (BOC 21/11/2017)')),
                  folder('Modificaciones puntuales', amendment))
    return [folder('Actual', folder('Planeamiento general', plan)),
            folder('No Vigente', folder('Planeamiento general',
                   folder('Old plan', doc(1, 'Historic document'))))]


class MedioCudeyoTests(unittest.TestCase):
    def test_grouping_dates_history_and_annulment(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 2)
        plan, amendment = rows
        self.assertEqual(plan['fecha_acuerdo'], '2010-11-16')
        self.assertEqual(plan['fecha_publicacion'], '2011-02-18')
        self.assertIsNone(plan['fecha'])
        self.assertEqual(amendment['fecha_acuerdo'], '2015-09-24')
        self.assertEqual(amendment['fecha_publicacion'], '2015-10-28')
        self.assertIsNone(amendment['fecha_aprob'])
        self.assertEqual(amendment['instrumento_padre_id'], plan['id'])
        self.assertEqual([d['id_documento'] for d in plan['documentos']], [22684, 22759])
        self.assertEqual(len(amendment['documentos']), 2)
        self.assertIn('ANULACIÓN', plan['advertencias_fuente'][0])
        self.assertTrue(all(d['url'].endswith(str(d['id_documento']))
                            for r in rows for d in r['documentos']))
        self.assertIsNone(plan['geometry'])

    def test_schema_pagination_empty_and_unsupported_rejected(self):
        for payload in ({'results': inventory(), 'next': 'page2'}, [],
                        [folder('Actual', folder('Unknown category'))]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_inventory(payload)
        for mutation in ('pagination', 'empty_docs', 'unknown_instrument', 'bad_id', 'unknown_date'):
            payload = inventory()
            plan = payload[0]['nodes'][0]['nodes'][0]
            if mutation == 'pagination':
                plan['nextPage'] = 2
            elif mutation == 'empty_docs':
                plan['nodes'] = []
            elif mutation == 'unknown_instrument':
                plan['text'] = 'Solicitud de licencia de obras'
            elif mutation == 'bad_id':
                plan['nodes'][0]['nodes'][0]['id'] = None
            else:
                plan['text'] = 'PGOU de Medio Cudeyo (2026)'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_all_documents_and_stable_id(self):
        payload = inventory()
        plan = payload[0]['nodes'][0]['nodes'][0]
        plan['nodes'][0]['nodes'] = [doc(i, f'Documento {i}') for i in range(100, 175)]
        first = parse_inventory(payload)[0]
        self.assertEqual(len(first['documentos']), 75)
        changed = copy.deepcopy(payload)
        changed[0]['nodes'][0]['nodes'][0]['text'] = plan['text'].replace('18/02/2011', '19/02/2011')
        self.assertEqual(first['id'], parse_inventory(changed)[0]['id'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('medio-cudeyo')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('39042', 'Medio Cudeyo', 'Cantabria'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            with patch('requests.Session.get', side_effect=AssertionError('Network forbidden')):
                result = adapter.backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
