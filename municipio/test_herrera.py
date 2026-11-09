import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.herrera import HerreraAyuntamientoAdapter, SOURCE_URL, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def gallery(number, names=('Memoria', 'Plano')):
    links = ''.join(
        f'<a href="/export/sites/herrera/es/transparencia/.galleries/IND-50-/'
        f'MODIFICACION-{number}-PGOU/{name}.pdf">{name}</a>' for name in names)
    return (f'<section class="gallery link-gallery"><h4 class="gallery-title">'
            f'{number}ª MODIFICACIÓN PGOU</h4>{links}</section>')


class HerreraTests(unittest.TestCase):
    def test_instrument_grouping_and_provenance(self):
        html = gallery(1, ('Memoria', 'Plano', 'Memoria')) + gallery(2, ('Anuncio', 'Memoria'))
        html += '<a href="/licencia.pdf">Solicitud de licencia</a>'
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for number, row in enumerate(rows, 1):
            self.assertEqual(row['codigo_ine'], '41050')
            self.assertFalse(row['publication_ready'])
            for doc in row['documentos']:
                self.assertIn(f'MODIFICACION-{number}-PGOU/', doc['url'])
                self.assertEqual(doc['source_url'], SOURCE_URL)
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(field, row)

    def test_fail_closed(self):
        for html in ('', '<h1>Error</h1>', gallery(1, ()),
                     gallery(1).replace('1ª MODIFICACIÓN PGOU', 'Solicitud licencia'),
                     gallery(1).replace('MODIFICACION-1-PGOU/', 'MODIFICACION-2-PGOU/'),
                     gallery(1) + gallery(1)):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_not_truncated(self):
        for pagination in ('<a rel="next" href="?page=2">Siguiente</a>',
                           '<a href="?page=2">Siguiente página</a>',
                           '<ul class="pagination"><li>2</li></ul>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(gallery(1) + pagination)

    def test_additional_instrument_is_not_truncated(self):
        rows = parse_inventory(''.join(gallery(n) for n in range(1, 8)))
        self.assertEqual(len(rows), 7)

    def test_manifest_and_live_method_contract(self):
        manifest = load_manifest('herrera')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41050')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertIsInstance(load_portal_adapter(manifest), HerreraAyuntamientoAdapter)
        response = Mock(url=SOURCE_URL, text=gallery(1))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            adapter = HerreraAyuntamientoAdapter('herrera')
            with patch('municipio.adapters.herrera.requests.get', return_value=response):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['live_records'], 1)
            self.assertEqual(json.loads(path.read_text())['id'], 'herrera-pgou-modificacion-1')
            with patch('municipio.adapters.herrera.requests.get', return_value=Mock(url=SOURCE_URL, text='error')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(json.loads(path.read_text())['id'], 'herrera-pgou-modificacion-1')
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
