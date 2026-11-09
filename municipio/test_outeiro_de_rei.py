import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.outeiro_de_rei import (
    SOURCE, OuteiroDeReiAyuntamientoAdapter, parse_inventory, parse_package,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

INDEX = '''<nav><a href="/urbanismo/noise/">Modificación</a></nav>
<h2><a href="/urbanismo/cc1/">Plan de sectorización CC1-1: Modificación industrial</a></h2>
<h2><a href="/urbanismo/cartel/">Nucleo rural Cartel. Modificación normas subsidiarias</a></h2>
<h2><a href="/urbanismo/parque/">PARQUE EMPRESARIAL</a></h2>
<h2><a href="/impresos/">Solicitude de licenza</a></h2>
<h2><a href="https://example.org/urbanismo/plan/">Modificación</a></h2>'''


def package(*names):
    return ''.join(f'<p class="tdm-descr"><a href="/wp-content/uploads/docs/{n}.pdf">{n}</a></p>' for n in names)


class ParserTests(unittest.TestCase):
    def test_inventory_excludes_forms_navigation_and_general_presentation(self):
        entries = parse_inventory(INDEX + INDEX)
        self.assertEqual(len(entries), 2)
        self.assertIn('Cartel', entries[1]['titulo'])

    def test_groups_documents_and_retains_provenance_without_inferred_dates(self):
        first, second = parse_inventory(INDEX)
        a = parse_package(package('memoria', 'plano', 'memoria'), first)
        b = parse_package(package('cartel'), second)
        self.assertEqual(len(a['documentos']), 2)
        self.assertEqual(len(b['documentos']), 1)
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(a['documentos'][0]['source_url'], first['url'])
        self.assertEqual(a['codigo_ine'], '27039')
        self.assertFalse(any(k.startswith('fecha') or k in {'lat', 'lon', 'fase'} for k in a))
        self.assertFalse(a['publication_ready'])

    def test_fail_closed(self):
        for html in ('<h1>Access denied</h1>', INDEX + '<a rel="next" href="/page/2/">2</a>',
                     INDEX + '<div class="page-numbers">2</div>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_package('<a href="/form.pdf">Licence</a>', parse_inventory(INDEX)[0])

    def test_adapter_refresh_and_failure_preserves_previous_output(self):
        def response(html):
            r = Mock(text=html, url=SOURCE, content=html.encode(), status_code=200,
                     headers={'Content-Type': 'text/html'})
            return r
        adapter = OuteiroDeReiAyuntamientoAdapter('outeiro-de-rei')
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.outeiro_de_rei.requests.Session') as session:
            get = session.return_value.__enter__.return_value.get
            get.side_effect = [response(INDEX), response(package('a', 'b')), response(package('c'))]
            out = Path(d) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(d) / 'state.json')
            self.assertEqual(result['count'], 2)
            old = out.read_text()
            self.assertEqual(len([json.loads(line) for line in old.splitlines()]), 2)
            get.side_effect = [response(INDEX), response('broken')]
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), old)
            self.assertTrue(adapter.backfill_licencias(Path(d) / 'licencias.jsonl')['disabled'])

    def test_manifest_contract(self):
        manifest = load_manifest('outeiro-de-rei')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '27039')
        self.assertEqual(manifest.provincia, 'Lugo')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), OuteiroDeReiAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
