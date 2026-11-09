import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cabezon_de_la_sal import (
    API, DOWNLOAD, SOURCE, CabezonDeLaSalAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def folder(title, *nodes):
    return {'id': None, 'text': title, 'nodes': list(nodes)}


def doc(number, title='Memoria'):
    return {'id': number, 'text': title, 'nodes': None}


def inventory():
    return [folder('Actual', folder('Planeamiento general', folder(
        'Plan General de Ordenación Urbana de Cabezón de la Sal (CROTU 23/07/2020; BOC 23/09/2020)',
        folder('Aprobación definitiva', folder('Planos', doc(29525)),
               folder('Publicación en el BOC', *[doc(29063 + i, f'Parte {i + 1} de 4') for i in range(4)])),
        folder('Modificaciones puntuales', folder('Modificación Puntual - Ejemplo',
               folder('Memoria', doc(40000, 'Texto (Ayto. 20/11/2019; BOC 10/01/2020)')))),
    ))), folder('No Vigente', folder('Plan Parcial histórico', doc(1)))]


class ParserTests(unittest.TestCase):
    def test_grouping_dates_provenance_and_modification_isolation(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 2)
        plan, modification = rows
        self.assertEqual(len(plan['documentos']), 5)
        self.assertEqual([d['id_origen'] for d in modification['documentos']], [40000])
        self.assertEqual(modification['parent_id'], plan['id'])
        self.assertEqual(plan['fecha_acuerdo'], '2020-07-23')
        self.assertEqual(plan['fecha_publicacion'], '2020-09-23')
        self.assertEqual(plan['fase'], 'aprobación definitiva')
        self.assertIsNone(modification['fase'])
        self.assertIsNone(modification['fecha_publicacion'])
        self.assertIsNone(modification['fecha_acuerdo'])
        self.assertEqual(plan['documentos'][0]['url'], DOWNLOAD + '29525')
        self.assertEqual(plan['inventory_url'], API)
        self.assertEqual(plan['codigo_ine'], '39012')
        self.assertFalse(plan['publication_ready'])
        self.assertIsNone(plan['lat'])
        self.assertNotIn(1, [d['id_origen'] for r in rows for d in r['documentos']])

    def test_full_tree_not_limited_to_first_n_documents(self):
        tree = [folder('Actual', folder('Plan Parcial Domañanes',
                folder('Aprobación definitiva', *[doc(i) for i in range(1, 151)])))]
        self.assertEqual(len(parse_inventory(tree)[0]['documentos']), 150)

    def test_id_stable_across_dates_and_document_order(self):
        tree = inventory()
        key = parse_inventory(tree)[0]['id']
        plan = tree[0]['nodes'][0]['nodes'][0]
        plan['text'] = plan['text'].replace('23/07/2020', '24/07/2020')
        plan['nodes'][0]['nodes'].reverse()
        self.assertEqual(parse_inventory(tree)[0]['id'], key)

    def test_fail_closed_on_empty_unknown_or_paginated_sources(self):
        invalid = [[], {}, {'results': inventory(), 'next': 'page2'},
                   [folder('Actual', doc(1, 'Solicitud de licencia'))],
                   [folder('Actual', folder('Plan Parcial vacío'))],
                   [folder('Actual'), folder('Siguiente página')]]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_inventory(value)
        tree = inventory()
        tree[0]['nodes'] = {'page': 1}
        with self.assertRaises(ValueError):
            parse_inventory(tree)
        tree = inventory()
        tree[0]['nodes'][0]['nodes'].append(copy.deepcopy(tree[0]['nodes'][0]['nodes'][0]))
        with self.assertRaises(ValueError):
            parse_inventory(tree)

    def test_adapter_refresh_and_disabled_licences(self):
        manifest = load_manifest('cabezon-de-la-sal')
        adapter = CabezonDeLaSalAyuntamientoAdapter(manifest.slug, manifest.portal.config)
        class Response:
            content = f'<div class="entry-content"><a href="{SOURCE}">PGOU</a></div>'.encode()
            text = "<h1>Cabezón de la Sal</h1><script>idMunicipio: '12'</script>"
            def json(self):
                return inventory()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=Response()):
            output, state = Path(tmp) / 'projects.jsonl', Path(tmp) / 'state.json'
            state.write_text('untouched')
            result = adapter.update_proyectos(output, state)
            self.assertEqual(result['count'], 2)
            self.assertEqual(len([json.loads(x) for x in output.read_text().splitlines()]), 2)
            self.assertEqual(state.read_text(), 'untouched')
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
