import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, Mock

from municipio.adapters.entrambasaguas import (
    EntrambasaguasAyuntamientoAdapter, PLAN, SOURCE, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def item(component, suffix, title=PLAN):
    return (f'<li class="view-list-item"><span class="views-field-title">'
            f'{title} – {component}</span><span class="views-field-field-archivo-normativa">'
            f'<a href="/sites/default/files/2022-02/NORMAS-SUBSIDIARIAS-DE-'
            f'PLANEAMIENTO-MUNICIPAL-{suffix}">{component}</a></span></li>')


def page(items, extra=''):
    return f'<div class="node--type-page"><div class="node__content">{items}{extra}</div></div>'


class EntrambasaguasTests(unittest.TestCase):
    def test_groups_attachments_and_excludes_unrelated_navigation(self):
        a = item('Memoria', 'Memoria.pdf')
        html = page(a + item('Planos', 'Planos.zip') + a)
        html += '<a href="formulario.pdf">Licencia de obras</a>'
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['codigo_ine'], '39028')
        for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon'):
            self.assertIsNone(rows[0][field])
        self.assertFalse(rows[0]['publication_ready'])

    def test_fails_on_pagination(self):
        for pager in ('<nav class="pager">2</nav>', '<a href="?page=1">2</a>',
                      '<a href="/more" rel="next">Más</a>'):
            with self.subTest(pager=pager), self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(page(item('Memoria', 'Memoria.pdf'), pager))

    def test_missing_changed_or_untrusted_inventory_fails(self):
        good = page(item('Memoria', 'Memoria.pdf'))
        for html in ('<html>error</html>', page(''),
                     page(item('Solicitud', 'Memoria.pdf', title='Licencia de obras')),
                     good.replace('/sites/default/files/', 'https://example.org/sites/default/files/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_adapter_write(self):
        manifest = load_manifest('entrambasaguas')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '39028')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = EntrambasaguasAyuntamientoAdapter('entrambasaguas')
        response = Mock(url=SOURCE, text=page(item('Memoria', 'Memoria.pdf')),
                        headers={'Content-Type': 'text/html'})
        with TemporaryDirectory() as directory, patch(
                'municipio.adapters.entrambasaguas.requests.get', return_value=response):
            out = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['titulo'], PLAN)
            response.url = 'https://example.org/normativa-urbanistica'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(json.loads(out.read_text())['titulo'], PLAN)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
