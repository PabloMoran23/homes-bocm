"""Parser contract tests with synthetic HTML; no live network in unit tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.amurrio import (
    AmurrioAyuntamientoAdapter, PGOU, PLANES, parse_pgou, parse_planes,
)
from municipio.manifest import load_manifest

PGOU_HTML = '''<main id="sp-component"><ul>
<li><a href="/images/approval.pdf">ANUNCIO BOTHA APROBACIÓN DEFINITIVA</a></li>
<li>PLANOS<ul><li><a href="/images/map a.pdf">Mapa</a></li></ul></li>
<li>MODIFICACIONES<br><ul><li>Plan especial Parque Fotovoltaico Ekiola</li>
<li><a href="/images/ekiola.pdf">Memoria</a></li>
<li><a href="/images/ekiola.pdf">Copia</a></li>
<li><a href="/images/ekiola-plan.pdf">Planos</a></li>
</ul></li></ul></main>'''
PLANES_HTML = '''<main id="sp-component"><ul>
<li>Ordenanzas municipales<ul><li><a href="/ordenanza.pdf">Ordenanza</a></li></ul></li>
<li><b>Modificación puntual estructural del Plan General de Ordenación Urbana</b>
<ul><li><a href="/memoria.pdf">Memoria</a></li>
<li><a href="/participacion.pdf">Proceso de participación</a></li></ul></li>
</ul><a href="/solicitud.pdf">Solicitud de licencia</a></main>'''


class AmurrioTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        general, special = parse_pgou(PGOU_HTML)
        self.assertEqual(len(general['documentos']), 2)
        self.assertEqual(len(special['documentos']), 2)
        self.assertEqual(general['fase'], 'aprobación definitiva')
        self.assertIsNone(special['fase'])
        self.assertIsNone(general['fecha_publicacion'])
        self.assertIsNone(general['fecha_acuerdo'])
        self.assertIsNone(general['geometry'])
        self.assertTrue(general['documentos'][1]['url'].endswith('map%20a.pdf'))
        self.assertTrue(all(d['source_url'] == PGOU for d in special['documentos']))
        # Adding a document must not change the instrument identity.
        changed = PGOU_HTML.replace('ekiola-plan.pdf', 'replacement.pdf')
        self.assertEqual(parse_pgou(changed)[1]['id'], special['id'])

    def test_forms_and_regulations_excluded(self):
        rows = parse_planes(PLANES_HTML)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['codigo_ine'], '01002')
        self.assertEqual(rows[0]['url'], PLANES)
        self.assertIsNone(rows[0]['fecha_aprob'])

    def test_fail_closed_on_pagination_or_changed_sources(self):
        for parser, html in ((parse_pgou, PGOU_HTML), (parse_planes, PLANES_HTML)):
            for link in ('<a href="?start=20">2</a>', '<a rel="next" href="/more">Más</a>'):
                with self.subTest(parser=parser.__name__, link=link), self.assertRaises(ValueError):
                    parser(html + link)
            with self.assertRaises(ValueError):
                parser('<main id="sp-component">No records</main>')
        with self.assertRaises(ValueError):
            parse_pgou(PGOU_HTML.replace('Plan especial Parque Fotovoltaico Ekiola', 'Noticias'))
        with self.assertRaises(ValueError):
            parse_planes(PLANES_HTML.replace('/memoria.pdf', 'https://other.example/memoria.pdf'))
        with self.assertRaises(ValueError):
            parse_pgou(PGOU_HTML.replace('<li>Plan especial Parque Fotovoltaico Ekiola</li>', ''))

    def test_adapter_snapshot_atomic_failure_and_disabled_licences(self):
        class Response:
            headers = {'Content-Type': 'text/html; charset=utf-8'}
            def __init__(self, url, text):
                self.url, self.text, self.content = url, text, text.encode()
            def raise_for_status(self):
                pass
        adapter = AmurrioAyuntamientoAdapter()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch('municipio.adapters.amurrio.requests.get', side_effect=[
                Response(PGOU, PGOU_HTML), Response(PLANES, PLANES_HTML)
            ]):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 3)
            before = path.read_bytes()
            with patch('municipio.adapters.amurrio.requests.get', side_effect=[
                Response(PGOU, PGOU_HTML), Response(PLANES, '<html>Unavailable</html>')
            ]), self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(before, path.read_bytes())
            with patch('municipio.adapters.amurrio.requests.get', side_effect=AssertionError('No network')):
                self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('amurrio')
        self.assertEqual(manifest.provincia, 'Álava')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.amurrio:AmurrioAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
