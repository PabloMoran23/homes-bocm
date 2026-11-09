"""Offline parser regressions; tiny fixtures model AUCAN's documented tree shape."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cartes import CartesAyuntamientoAdapter, DOWNLOAD, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def folder(title, *children):
    return {'text': title, 'type': 'folder', 'id': None, 'nodes': list(children)}


def doc(number, title='Memoria (1984-03-30|1984-06-11)'):
    return {'text': title, 'type': None, 'id': number, 'nodes': None}


def fixture():
    return [folder('Actual', folder('Planeamiento general', folder(
        'Normas Subsidiarias Municipales de Cartes (CRU 30/03/1984; BOC 11/06/1984)',
        folder('Aprobación definitiva', folder('Memoria', doc(1)), folder('Planos', doc(2))),
        folder('Modificaciones puntuales', folder('Modificación Puntual - nº 2',
                                                folder('Memoria', doc(3), doc(4)))))))]


class CartesTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        base, modification = rows
        self.assertEqual([d['id'] for d in base['documentos']], [1, 2])
        self.assertEqual([d['id'] for d in modification['documentos']], [3, 4])
        self.assertEqual(base['fecha_acuerdo'], '1984-03-30')
        self.assertEqual(base['fecha_publicacion'], '1984-06-11')
        self.assertIsNone(base['fecha_aprob'])
        self.assertEqual(base['fase'], 'aprobación definitiva')
        self.assertIsNone(modification['fase'])
        self.assertIsNone(modification['fecha_publicacion'])
        self.assertIsNone(modification['fecha_acuerdo'])
        self.assertEqual(base['documentos'][0]['url'], DOWNLOAD + '1')
        self.assertIn('Aprobación definitiva', base['documentos'][0]['ruta'])
        self.assertIsNone(base['geometry'])
        self.assertFalse(base['publication_ready'])

    def test_all_classifications_and_stable_identity(self):
        tree = fixture()
        tree += [folder('No Vigente', folder('Planeamiento desarrollo', folder(
            'Plan Especial de Protección del Conjunto Histórico de Riocorvo',
            folder('Aprobación Definitiva', doc(5)))))]
        rows = parse_inventory(tree)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]['clasificacion_archivo'], 'No Vigente')
        previous = rows[0]['id']
        tree[0]['nodes'][0]['nodes'][0]['nodes'][0]['nodes'].reverse()
        self.assertEqual(parse_inventory(tree)[0]['id'], previous)

    def test_correction_attached_to_parent(self):
        tree = fixture()
        tree[0]['nodes'][0]['nodes'][0]['nodes'].append(folder(
            'Subsanación de errores', folder('Subsanación nº1 (BOC 01/03/2021)', doc(8))))
        rows = parse_inventory(tree)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['fecha_publicacion'], '1984-06-11')

    def test_pagination_and_empty_fail_closed(self):
        for tree in ([], {'results': fixture(), 'next': 'page2'}, [folder('Unexpected')]):
            with self.subTest(tree=tree), self.assertRaises(ValueError):
                parse_inventory(tree)
        tree = fixture()
        tree[0]['nextPage'] = 2
        with self.assertRaises(ValueError):
            parse_inventory(tree)

    def test_forms_and_invalid_documents_rejected(self):
        tree = [folder('Actual', folder('Otros documentos', folder('Solicitud de licencia', doc(9))))]
        with self.assertRaises(ValueError):
            parse_inventory(tree)
        for value in ('123', -1, None, True):
            bad = copy.deepcopy(fixture())
            bad[0]['nodes'][0]['nodes'][0]['nodes'][0]['nodes'][0]['nodes'][0]['id'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_inventory(bad)

    def test_disabled_licences_and_manifest(self):
        raw = load_yaml(Path('data/municipios/cartes/manifest.yaml'))
        self.assertEqual(raw['codigo_ine'], '39018')
        self.assertEqual(raw['provincia'], 'Cantabria')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        adapter = load_portal_adapter(load_manifest('cartes'))
        self.assertIsInstance(adapter, CartesAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            with patch('municipio.adapters.cartes.requests.get') as network:
                adapter.backfill_licencias(output)
                self.assertEqual(output.read_text(), '')
                network.assert_not_called()

    def test_network_failure_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with patch('municipio.adapters.cartes.requests.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    CartesAyuntamientoAdapter('cartes').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
