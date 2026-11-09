import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.autol import AutolAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest


HTML = '''<div itemprop="articleBody">
<h1>ARQUITECTO MUNICIPAL</h1><a href="/form.pdf">Solicitud de licencia</a>
<div><h1>MODIFICACIÓN PUNTUAL Nº24 DEL PLAN GENERAL</h1></div>
<div><a href="/images/p24.pdf">PROYECTO</a><a href="/images/p24.pdf">duplicado</a>
<h2>APROBADO INICIALMENTE POR EL PLENO DEL DÍA 4 DE SEPTIEMBRE DE 2017.</h2>
<a href="http://ias1.larioja.org/boletin/visor?id=24">Publicado en el B.O.R. Nº104 de 8 de Septiembre de 2017.</a>
<p>Publicado en Diario La Rioja del día 6 de Septiembre de 2017.</p>
<p>PLAZO DE ALEGACIONES HASTA EL DÍA 9 DE OCTUBRE DE 2017.</p></div>
<div><h1>PLAN PARCIAL S-5</h1><a href="/images/s5.pdf">Memoria</a>
<h2>PLANOS</h2><a href="/images/s5.dwg">Plano</a>
<h1>MODIFICACIÓN PUNTUAL Nº27 DEL PLAN GENERAL</h1>
<a href="/images/p27.pdf">Proyecto UE-29</a>
<a href="/images/bor27.pdf">PUBLICADA EN EL B.O.R. DEL DÍA 30 DE DICIEMBRE DE 2024</a></div>
</div><aside><a href="/unrelated.pdf">Otro documento</a></aside>'''


class AutolTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_inventory(HTML)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 2])
        self.assertTrue(all(r['codigo_ine'] == '26021' for r in rows))
        self.assertIn('s5.dwg', rows[1]['documentos'][1]['url'])
        self.assertTrue(all(d['source_url'] == SOURCE for r in rows for d in r['documentos']))
        self.assertEqual(rows, parse_inventory(HTML))

    def test_dates_are_scoped_and_typed(self):
        rows = parse_inventory(HTML)
        self.assertEqual(rows[0]['fecha_acuerdo'], '2017-09-04')
        self.assertEqual(rows[0]['fecha_publicacion'], '2017-09-08')
        self.assertNotIn('fecha_publicacion', rows[1])
        self.assertEqual(rows[2]['fecha_publicacion'], '2024-12-30')
        self.assertNotIn('fecha_acuerdo', rows[2])
        self.assertTrue(all('lat' not in r and 'fecha_aprob' not in r for r in rows))

    def test_works_without_inferred_dates(self):
        rows = parse_inventory('<div itemprop="articleBody"><h1>PROYECTO DE REURBANIZACIÓN DE LA CALLE CARASOL.</h1><a href="/images/2019_03.pdf">Proyecto</a></div>')
        self.assertEqual(rows[0]['tipo'], 'obra_publica')
        self.assertNotIn('fecha_publicacion', rows[0])

    def test_pagination_and_source_drift_fail(self):
        for extra in ['<a rel="next" href="?page=2">2</a>', '<div class="pagination"><a href="?start=20">2</a></div>']:
            with self.assertRaises(ValueError):
                parse_inventory(HTML + extra)
        for bad in ['<p>error</p>', '<div itemprop="articleBody">Solicitud de licencia</div>', '<div itemprop="articleBody"><h1>PLAN PARCIAL S-5</h1></div>']:
            with self.assertRaises(ValueError):
                parse_inventory(bad)

    def test_adapter_live_path_and_disabled_licences(self):
        response = Mock(url=SOURCE, content=HTML.encode())
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.autol.requests.get', return_value=response):
            adapter = AutolAyuntamientoAdapter('autol')
            out = Path(tmp) / 'rows.jsonl'
            report = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(report['live_records'], 3)
            self.assertEqual(len([json.loads(x) for x in out.read_text().splitlines()]), 3)
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest(Path(__file__).resolve().parents[1] / 'data/municipios/autol/manifest.yaml')
        self.assertEqual(manifest.provincia, 'La Rioja')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.autol:AutolAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
