import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.montefrio import SOURCE, MontefrioAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


INTRO = '''<div align="justify">instrumento urbanístico <strong>P.G.O.U. de Montefrío,</strong>
con la APROBACIÓN DEFINITIVA de la Consejería de Obras Públicas y Vivienda
de fecha 28 de marzo de 2012 y del Pleno de la Corporación Municipal en sesión
de 2 de julio de 2012. No se incluyen la Memoria General y los Anexos.</div>'''
DOCS = '''<a class="wcBar2" href="../impresos/tii100.pdf">MEMORIA DE ORDENACIÓN</a>
<a class="wcBar2" href="../impresos/tiv2120.pdf">LOJILLA (Sin aprobar por la C.P.O.T.U.)</a>'''
HTML = INTRO + DOCS


class MontefrioTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        rows = parse_inventory(HTML + DOCS + '<a href="formulario.pdf">Licencia</a>')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], 'https://ayto-montefrio.es/impresos/tii100.pdf')
        self.assertIn('Sin aprobar', row['documentos'][1]['titulo'])
        self.assertEqual([a['fecha_acuerdo'] for a in row['acuerdos']], ['2012-03-28', '2012-07-02'])
        for key in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)

    def test_no_invented_agreements(self):
        row = parse_inventory(HTML.replace('28 de marzo de 2012', 'sin fecha').replace('2 de julio de 2012', 'sin fecha'))[0]
        self.assertEqual(row['acuerdos'], [])

    def test_missing_or_unrelated_inventory_fails(self):
        for html in ('<h1>Noticias</h1>', INTRO, HTML.replace('Montefrío', 'Otro municipio')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_and_external_documents_fail(self):
        for addition in ('<a href="?page=2" rel="next">2</a>',
                         '<a href="?page=2">Siguiente</a>',
                         '<a class="wcBar2" href="https://other.example/impresos/a.pdf">Otro</a>'):
            with self.subTest(addition=addition), self.assertRaises(ValueError):
                parse_inventory(HTML + addition)

    def test_manifest_and_live_contract(self):
        manifest = load_manifest('montefrio')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '18135')
        self.assertEqual(manifest.provincia, 'Granada')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(url=SOURCE, content=HTML.encode())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            with patch('municipio.adapters.montefrio.requests.get', return_value=response):
                adapter.backfill_proyectos(output)
                first = json.loads(output.read_text())
                adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(json.loads(output.read_text())['id'], first['id'])
            self.assertEqual(adapter.backfill_licencias(output)['count'], 0)
            self.assertEqual(output.read_text(), '')

    def test_redirect_does_not_overwrite_snapshot(self):
        adapter = MontefrioAyuntamientoAdapter('montefrio')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            output.write_text('previous')
            with patch('municipio.adapters.montefrio.requests.get', return_value=Mock(url='https://other.example/')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous')


if __name__ == '__main__':
    unittest.main()
