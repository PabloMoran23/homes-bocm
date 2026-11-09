import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.noblejas import (
    NoblejasAyuntamientoAdapter, ORDENACION, URBANISMO, parse_inventory,
)
from municipio.manifest import load_manifest


def page(body, title='Urbanismo'):
    return f'<main><h1>{title}</h1>{body}</main>'


def document(title, name):
    return f'<h2>{title}</h2><a href="/wp-content/uploads/{name}.pdf">Descargar</a>'


class NoblejasTests(unittest.TestCase):
    def test_modification_groups_documents_and_keeps_distinct_dates(self):
        html = page('<h3>Modificación puntual Nº4 de las Normas Subsidiarias</h3>'
                    + document('APROBACION DEFINITIVA CPOTU 22-03-2023', 'mp4')
                    + document('DOCM 20-10-2023', 'notice')
                    + document('DOCM 20-10-2023', 'notice'))
        row, = parse_inventory(html, URBANISMO)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2023-03-22')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(row['fecha_aprob_fuente']['url'], 'https://noblejas.es/wp-content/uploads/mp4.pdf')
        self.assertEqual(row['codigo_ine'], '45115')

    def test_planning_inventory_is_one_instrument_not_one_per_pdf(self):
        html = page(document('Memoria', 'mem') + document('Planos', 'map'), 'Ordenación municipal')
        row, = parse_inventory(html, ORDENACION)
        self.assertEqual(len(row['documentos']), 2)
        self.assertIsNone(row['geometry'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertFalse(row['publication_ready'])

    def test_forms_bases_and_licence_applications_are_not_records(self):
        html = page('<h3>Obras y servicios</h3>' + document('Impresos licencia', 'form')
                    + '<h3>Bases para selección del Agente Urbanizador</h3>' + document('Bases', 'bases')
                    + '<h3>Calificación y licencia urbanística para industria</h3>' + document('Anuncio', 'notice'))
        with self.assertRaises(ValueError):
            parse_inventory(html, URBANISMO)

    def test_reparcelacion_group_and_identity_survive_document_reordering(self):
        heading = '<h3>13/04/2021. Proyecto de reparcelación ua-66 NN.SS. Noblejas</h3>'
        a = document('Resolución información pública', 'resolution')
        b = document('Proyecto parte 1', 'part1')
        first, = parse_inventory(page(heading + a + b), URBANISMO)
        second, = parse_inventory(page(heading + b + a), URBANISMO)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(first['documentos']), 2)
        self.assertIsNone(first['fecha_publicacion'])
        self.assertIsNone(first['fecha_aprob'])
        self.assertIn('información pública', first['fase'])

    def test_rejects_missing_content_and_pagination(self):
        for html in ('<h1>Login</h1>', page('<a href="/">Urbanismo</a>'),
                     page(document('Memoria', 'mem') + '<a rel="next" href="?page=2">Next</a>', 'Ordenación municipal')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, ORDENACION)

    def test_adapter_and_manifest_snapshot(self):
        manifest = load_manifest('noblejas')
        self.assertFalse(manifest.licencias.enabled)
        responses = [Mock(url=ORDENACION, text=page(document('Memoria', 'mem'), 'Ordenación municipal')),
                     Mock(url=URBANISMO, text=page('<h3>Modificación Puntual nº 5 de las Normas Subsidiarias</h3>'
                                                 + document('MP5 NNSS', 'mp5')))]
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.noblejas.requests.get', side_effect=responses):
            output = Path(directory) / 'projects.jsonl'
            result = NoblejasAyuntamientoAdapter('noblejas').update_proyectos(output, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len(rows), 2)
            self.assertNotEqual(rows[0]['id'], rows[1]['id'])


if __name__ == '__main__':
    unittest.main()
