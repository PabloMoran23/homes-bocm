import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.bujalance import (
    API_URL, INVENTORY_URL, BujalanceAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(html=None):
    return {'id': 7942, 'link': INVENTORY_URL, 'date': '2021-04-29T10:25:15',
            'content': {'rendered': html or '''
<h2>Ordenanzas</h2><a href="/licencias.pdf">Licencias Urbanísticas</a>
<h2>PGOU Bujalance y Morente – Texto Refundido Junio 2019</h2>
<strong>Aprobación definitiva a reserva de subsanación:</strong>
<a href="https://www.juntadeandalucia.es/boja/test.pdf">BOJA 8 febrero 2013</a>
<h3>Adjuntos general</h3><a href="/memoria.pdf">Memoria</a>
<a href="/nnuu.pdf">Normativa</a><a href="/memoria.pdf">Duplicado</a>
<strong>Corrección Ancha de Palomino</strong><a href="/correccion.pdf">Corrección</a>
<h2>Otras secciones</h2><a href="/contrato.pdf">Licitación</a>
'''}}


def response(data, pages=1, items=1):
    r = Mock()
    r.url = API_URL
    r.headers = {'X-WP-TotalPages': str(pages), 'X-WP-Total': str(items)}
    r.json.return_value = data
    r.content = json.dumps(data).encode()
    return r


class BujalanceTests(unittest.TestCase):
    def test_grouping_scope_and_semantics(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '14012')
        self.assertEqual(len(row['documentos']), 4)
        self.assertIn('Corrección', row['documentos'][-1]['contexto_fuente'])
        self.assertEqual(row['documentos'][0]['titulo'], 'BOJA 8 febrero 2013')
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], parse_inventory(inventory())[0]['id'])

    def test_reject_missing_or_unusable_section(self):
        for html in ('<h2>Ordenanzas</h2>', '<h2>PGOU Bujalance y Morente</h2>',
                     '<h2>PGOU Bujalance y Morente</h2><a href="https://example.org/memoria.pdf">Memoria</a>',
                     '<h2>PGOU Bujalance y Morente</h2><a rel="next" href="/page/2">Next</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(inventory(html))
        unrelated = inventory()
        unrelated['link'] = 'https://bujalance.es/noticia/'
        self.assertEqual(parse_inventory(unrelated), [])

    @patch('municipio.adapters.bujalance.requests.get')
    def test_all_api_pages_and_refresh(self, get):
        other = {'id': 2, 'link': 'https://bujalance.es/otra/'}
        get.side_effect = [response([other], 2, 2), response([inventory()], 2, 2)]
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            state = Path(tmp) / 'state.json'
            result = BujalanceAyuntamientoAdapter('bujalance').update_proyectos(out, state)
            self.assertEqual(result['count'], 1)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(get.call_args_list[1].args[0], API_URL + '&page=2')
            self.assertFalse(state.exists())
            self.assertEqual(len(out.read_text().splitlines()), 1)

    @patch('municipio.adapters.bujalance.requests.get')
    def test_pagination_failures_do_not_replace_output(self, get):
        scenarios = [
            [response([inventory()], 2, 2), response([], 2, 2)],
            [response([inventory()], 2, 2), response([inventory()], 2, 2)],
            [response([inventory()], 1, 2)],
            [response([inventory()], 2, 2), response([{'id': 2}], 3, 3)],
        ]
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous complete output')
            for scenario in scenarios:
                get.side_effect = scenario
                with self.assertRaises(ValueError):
                    BujalanceAyuntamientoAdapter('bujalance').backfill_proyectos(out)
                self.assertEqual(out.read_text(), 'previous complete output')

    def test_manifest_and_disabled_licences(self):
        raw = load_yaml(Path('data/municipios/bujalance/manifest.yaml'))
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('14012', 'Córdoba'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        adapter = load_portal_adapter(load_manifest('bujalance'))
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
