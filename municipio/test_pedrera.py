import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.pedrera import PedreraAyuntamientoAdapter, SOURCES, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def fixture(kind):
    if kind == 'pgou':
        return '''<main><h1>PGOU</h1>
        <h3>DOCUMENTO DE APROBACIÓN PGOU SEPTIEMBRE DE 2015</h3>
        <a href="http://multimedia.dipusevilla.es/pedrera/ficheros/archivos/pgou_2015/normas.pdf">Normas</a>
        <a href="http://multimedia.dipusevilla.es/pedrera/ficheros/archivos/pgou_2015/plano.pdf">Plano</a>
        <a href="http://multimedia.dipusevilla.es/pedrera/ficheros/archivos/pgou_2015/normas.pdf">Normas</a>
        </main>'''
    return '''<main><h1>Plan Básico de Ordenación Municipal</h1>
    <p>PBOM FASE 3 AVANCE V2</p>
    <a href="/export/sites/pedrera/.galleries/pbom/memoria.pdf">Memoria</a>
    <a href="/export/sites/pedrera/.galleries/pbom/consulta.docx">Consulta pública</a>
    <a href="/es/noticias/">Noticias</a></main>'''


class PedreraTests(unittest.TestCase):
    def test_groups_documents_and_preserves_original_links(self):
        row = parse_inventory(fixture('pgou'), SOURCES['pgou'], 'pgou')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(row['documentos'][0]['url'].startswith('http://'))
        self.assertEqual(row['codigo_ine'], '41072')
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase'):
            self.assertIsNone(row[key])
        self.assertNotIn('lat', row)

    def test_avance_and_relative_documents(self):
        row = parse_inventory(fixture('pbom'), SOURCES['pbom'], 'pbom')
        self.assertEqual(row['fase'], 'avance')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['url'],
                         'https://www.pedrera.es/export/sites/pedrera/.galleries/pbom/consulta.docx')

    def test_fail_closed_on_empty_wrong_page_and_pagination(self):
        for html in ('<main><h1>Licencia de obras: formulario</h1></main>',
                     fixture('pbom').replace('PBOM FASE 3 AVANCE V2', ''),
                     fixture('pbom').replace('</main>', '<a rel="next" href="?page=2">Siguiente</a></main>'),
                     fixture('pbom').replace('</main>', '<div class="pagination">2</div></main>'),
                     '<h1>Plan Básico de Ordenación Municipal</h1>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCES['pbom'], 'pbom')

    def test_no_unreviewed_document_hosts(self):
        html = fixture('pgou').replace('multimedia.dipusevilla.es', 'example.org')
        with self.assertRaises(ValueError):
            parse_inventory(html, SOURCES['pgou'], 'pgou')

    def test_no_partial_output_when_second_inventory_fails(self):
        first = Mock(url=SOURCES['pgou'], text=fixture('pgou'), content=fixture('pgou').encode())
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            with patch('municipio.adapters.pedrera.requests.get', side_effect=[first, RuntimeError('offline')]):
                with self.assertRaises(RuntimeError):
                    PedreraAyuntamientoAdapter('pedrera').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_manifest_and_registry_and_snapshot_update(self):
        manifest = load_manifest('pedrera')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41072')
        self.assertEqual(manifest.provincia, 'Sevilla')
        for section, key in [('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')]:
            self.assertIs(raw[section][key], False)
        responses = [Mock(url=url, text=fixture(kind), content=fixture(kind).encode())
                     for kind, url in SOURCES.items()]
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            adapter = load_portal_adapter(manifest)
            with patch('municipio.adapters.pedrera.requests.get', side_effect=responses):
                result = adapter.update_proyectos(out, Path(folder) / 'state.json')
            self.assertEqual(result['count'], 2)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual({r['id'] for r in rows}, {'pedrera-pgou', 'pedrera-pbom'})
            with self.assertRaises(NotImplementedError):
                adapter.backfill_licencias(Path(folder) / 'licencias.jsonl')


if __name__ == '__main__':
    unittest.main()
