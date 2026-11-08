import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.dolores import DoloresAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def inventory():
    return '''<article><div class="entry-content"><div class="et_pb_text_inner">
    <h2>PGOU</h2><a href="/impresos/pgou/pgou.zip">PLAN GENERAL DE ORDENACIÓN URBANA (Descarga Completa)</a>
    <a href="/impresos/pgou/1.indice.pdf">1. ÍNDICE</a>
    <a href="/impresos/pgou/3.normativa.pdf">3. NORMATIVA</a>
    <a href="/impresos/pgou/2.memoria.pdf">2. MEMORIA</a>
    </div></div></article>'''


class DoloresTests(unittest.TestCase):
    def test_grouping_provenance_and_unknown_semantics(self):
        html = inventory() + '<nav><a href="/form.pdf">Licencia de obra</a></nav>'
        row, = parse_inventory(html)
        self.assertEqual(row['codigo_ine'], '03064')
        self.assertEqual(len(row['documentos']), 4)
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        self.assertTrue(all(d['url'].startswith('https://www.dolores.es/') for d in row['documentos']))
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_fail_closed(self):
        cases = [inventory().replace('2. MEMORIA', 'Solicitud de licencia'),
                 inventory().replace('3. NORMATIVA', '4. NORMATIVA'),
                 inventory().replace('/impresos/pgou/2.memoria.pdf', 'https://example.org/form.pdf'),
                 inventory() + '<a rel="next" href="?page=2">Next</a>',
                 '<h2>PGOU</h2>', '<p>Noticia sobre urbanismo</p>',
                 inventory().replace('PGOU</h2>', 'Otro plan</h2>')]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_deduplicate_links(self):
        html = inventory().replace('</h2>', '</h2><a href="/impresos/pgou/1.indice.pdf">1. ÍNDICE</a>')
        self.assertEqual(len(parse_inventory(html)[0]['documentos']), 4)

    def test_snapshot_and_disabled_licences(self):
        response = Mock(url=SOURCE, text=inventory(), content=inventory().encode())
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.dolores.requests.get', return_value=response):
            adapter = DoloresAyuntamientoAdapter()
            output = Path(tmp) / 'projects.jsonl'
            adapter.backfill_proyectos(output)
            before = output.read_text()
            adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_text(), before)
            self.assertEqual(json.loads(before)['id'], 'dolores-pgou')
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('dolores')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '03064')
        self.assertEqual(manifest.provincia, 'Alicante')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
