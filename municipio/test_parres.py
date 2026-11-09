"""Offline contract and parser tests; run with python -m unittest municipio.test_parres."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.parres import ParresAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def document(folder, name='MEMORIA', query='?t=1661171676269'):
    return f'<a href="/documents/188680/{folder}/{name}.pdf/uuid{query}">{name}</a>'


def inventory(body):
    return '<div class="journal-content-article"><div class="detalle"><h3>PLANEAMIENTO DE PARRES</h3>' + body + '</div></div>'


class ParresTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        html = inventory('<h4>2. Plan Parcial. Caxidi</h4>' + document(10) + document(10, 'PLANO') + document(10))
        row, = parse_inventory(html)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '33045')
        self.assertEqual(row['url'], SOURCE)
        self.assertIn('?t=', row['documentos'][0]['url'])
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_all_sections_and_exclusions(self):
        titles = ['0. NSP de los Suelos Urbanos y Aptos para Urbanizar', '1. NSP Suelo No Urbanizable',
                  '2. Plan Parcial. Caxidi', '3. Plan Parcial SAU-2. Santianes de Terrón',
                  '4. Plan Parcial SAU-3. Santianes de Terrón II', '5. Plan Parcial. Parque Empresarial de Prestín',
                  '6. PERI del Puente Romano', '7. Estudio Detalle. Castañera', '8. Estudio Detalle. Prestín',
                  '9. Estudio Implantación. Renovación red abastecimiento agua Bodes', 'a. CAU - Catalogo urbanístico']
        body = ''.join(f'<h4>{title}</h4>' + document(i) for i, title in enumerate(titles))
        body += '<h4>b. IPCA</h4>' + document(80)
        body += '<h4>Evaluación ambiental estratégica</h4>' + document(81)
        body += '<h4>PLAN DE ACTUACIÓN MUNICIPAL FRENTE A INUNDACIONES DEL CONCEJO DE PARRES</h4>' + document(82)
        self.assertEqual(len(parse_inventory(inventory(body))), 11)

    def test_id_independent_of_document_timestamp(self):
        a = parse_inventory(inventory('<h4>2. Plan Parcial. Caxidi</h4>' + document(10)))
        b = parse_inventory(inventory('<h4>9. Plan Parcial. Caxidi</h4>' + document(10, query='?t=999')))
        self.assertEqual(a[0]['id'], b[0]['id'])

    def test_labels_of_duplicate_urls_preserved(self):
        html = inventory('<h4>2. Plan Parcial. Caxidi</h4>' + document(10) + document(10).replace('>MEMORIA<', '>Otro título<'))
        self.assertEqual(parse_inventory(html)[0]['documentos'][0]['titulos_fuente'], ['MEMORIA', 'Otro título'])

    def test_fail_closed(self):
        for body in ['', '<h4>2. Plan Parcial. Caxidi</h4>', '<h4>Licencia de obras</h4>' + document(10),
                     '<h4>2. Plan Parcial. Caxidi</h4>' + document(10) + document(11),
                     '<h4>2. Plan Parcial. Caxidi</h4><a href="https://example.org/a.pdf">MEMORIA</a>',
                     '<h4>2. Plan Parcial. Caxidi</h4>' + document(10) + '<a rel="next" href="?page=2">Next</a>',
                     '<h4>2. Plan Parcial. Caxidi</h4>' + document(10) + '<h4>3. Plan Parcial. Otro</h4>' + document(10)]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_inventory(inventory(body))
        with self.assertRaises(ValueError):
            parse_inventory('<h4>2. Plan Parcial. Caxidi</h4>' + document(10))

    def test_manifest(self):
        manifest = load_manifest('parres')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '33045')
        self.assertEqual(manifest.provincia, 'Asturias')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])

    def test_adapter_refresh_and_disabled_licences(self):
        response = Mock(url=SOURCE, text=inventory('<h4>2. Plan Parcial. Caxidi</h4>' + document(10)))
        with TemporaryDirectory() as tmp, patch('municipio.adapters.parres.requests.get', return_value=response):
            adapter = ParresAyuntamientoAdapter()
            output = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(output, Path(tmp) / 'state.json')['rows'], 1)
            self.assertEqual(json.loads(output.read_text())['titulo'], 'Plan Parcial. Caxidi')
            self.assertFalse((Path(tmp) / 'state.json').exists())
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_unexpected_redirect(self):
        with TemporaryDirectory() as tmp, patch('municipio.adapters.parres.requests.get', return_value=Mock(url='https://example.org')):
            with self.assertRaises(ValueError):
                ParresAyuntamientoAdapter().backfill_proyectos(Path(tmp) / 'out')
