"""Parser contract tests; synthetic trees mirror the reviewed AUCAN response."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.marina_de_cudeyo import (
    DOWNLOAD, INVENTORY, SOURCE, MarinaDeCudeyoAyuntamientoAdapter, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def folder(text, *nodes):
    return {'id': None, 'text': text, 'type': 'folder', 'selectable': False, 'nodes': list(nodes)}


def doc(identifier, text='Documento completo'):
    return {'id': identifier, 'text': text, 'type': None, 'selectable': True, 'nodes': None}


def inventory():
    return [folder('Actual', folder('Otros documentos', folder(
        'Catálogo de Edificaciones en Suelo Rústico de Marina de Cudeyo (Ayto. 25/08/2014; BOC 10/09/2014)',
        folder('Aprobación definitiva', doc(31147)),
        folder('Modificaciones puntuales', folder(
            'MP nº1 del CESR de Marina de Cudeyo - Inclusión de dos edificaciones. Fichas 148 y 149 (Ayto. 20/12/2022; BOC 03/01/2023)',
            doc(31884), doc(31864, 'Certificado del Pleno (20/12/22)'),
        )),
    )))]


class MarinaDeCudeyoTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 2)
        parent, child = rows
        self.assertEqual(parent['fecha_acuerdo'], '2014-08-25')
        self.assertEqual(parent['fecha_publicacion'], '2014-09-10')
        self.assertIsNone(parent['fecha'])
        self.assertNotIn('fecha_aprob', parent)
        self.assertEqual([d['id_origen'] for d in parent['documentos']], [31147])
        self.assertEqual(len(child['documentos']), 2)
        self.assertEqual(child['instrumento_padre'], parent['id'])
        self.assertEqual(child['documentos'][0]['url'], DOWNLOAD + '31884')
        self.assertEqual(parent['codigo_ine'], '39040')
        self.assertIsNone(parent['geometry'])

    def test_multiple_dates_and_discrepancies_preserved(self):
        tree = [folder('Actual', folder(
            'Modificación Puntual - nº 3 - Varias modificaciones (CRU 28/07/1993 - 29/11/1993; BOC 09/09/1993 - 07/03/1994)',
            doc(25390, 'MOD PUN Nº 3 (1993-07-28|1993-09-03)'),
        ))]
        row, = parse_inventory(tree)
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIn('09/09/1993', row['fechas_fuente']['publicacion_boc'])
        self.assertIn('1993-09-03', row['documentos'][0]['titulo'])

    def test_all_branches_no_fixed_record_limit_and_document_deduplication(self):
        tree = inventory()
        tree[0]['nodes'][0]['nodes'][0]['nodes'][0]['nodes'].append(doc(31147))
        tree.append(folder('No Vigente', folder(
            'Plan General de Ordenación Urbana de Marina de Cudeyo (CRU 21/05/1984; BOC 13/06/1984)',
            *(doc(i) for i in range(40000, 40130)),
        )))
        rows = parse_inventory(tree)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(len(rows[0]['documentos'][0]['rutas_fuente']), 2)
        self.assertEqual(len(rows[-1]['documentos']), 130)
        self.assertEqual(rows[-1]['estado_fuente'], 'No Vigente')
        self.assertEqual(parse_inventory(list(reversed(tree)))[-1]['id'], rows[1]['id'])

    def test_changed_or_incomplete_response_fails(self):
        bad_responses = [[], {'results': inventory(), 'next': 'page2'},
                         [folder('Actual', doc(1))],
                         [folder('Actual', folder('Catálogo de Edificaciones (Ayto. 25/08/2014; BOC 10/09/2014)'))],
                         [folder('Actual', folder('Nuevo tipo (CRU 01/01/2020; BOC 02/01/2020)', doc(1)))]]
        lazy = inventory()
        lazy[0]['nodes'] = '/next-page'
        bad_responses.append(lazy)
        for response in bad_responses:
            with self.subTest(response=response), self.assertRaises(ValueError):
                parse_inventory(response)

    def test_snapshot_refresh_and_failure_preserves_previous_output(self):
        adapter = MarinaDeCudeyoAyuntamientoAdapter('marina-de-cudeyo')
        html = b"<h1>Marina de Cudeyo</h1><script>idMunicipio: '40'</script>"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[html, json.dumps(inventory()).encode()]):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 2)
            previous = output.read_bytes()
            with patch.object(adapter, '_fetch', return_value=b'<h1>Medio Cudeyo</h1>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)
            lic = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(lic)['status'], 'disabled')
            self.assertEqual(lic.read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('marina-de-cudeyo')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), MarinaDeCudeyoAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
