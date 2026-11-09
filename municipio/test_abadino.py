import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.abadino import AbadinoAyuntamientoAdapter, AREA, BASE, INDEX, canonical
from municipio.manifest import load_manifest, load_yaml


class AbadinoTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        root = AREA + '/Paginas/plan.aspx'
        child = AREA + '/Paginas/segunda.aspx'
        form = AREA + '/Paginas/licencia.aspx'
        numbered = child + '?page=1'
        doc = AREA + '/Documents/plano%20uno.pdf'
        pages = {root: 'Plan General de Ordenación Urbana', child: 'Segunda Aprobación Inicial', form: 'Obras'}
        html = {
            root: f'<main id="main-content"><a href="{child}">fase</a><a href="{doc}">Plano</a></main>',
            child: f'<main id="main-content"><a href="{numbered}">1</a><a href="{root}">volver</a><a href="{doc}">Plano repetido</a><a href="{AREA}/Documents/memoria.pdf">Memoria</a></main>',
            numbered: f'<main id="main-content"><a href="{AREA}/Documents/anexo.pdf">Anexo</a></main>',
        }
        adapter = AbadinoAyuntamientoAdapter()
        with patch.object(adapter, '_get', side_effect=lambda u: Mock(text=html[u])):
            rows = adapter.extract(pages)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertIn(numbered, row['paginas_fuente'])
        self.assertEqual(len(next(d for d in row['documentos'] if d['url'] == doc)['procedencias']), 2)
        self.assertEqual(row['fase'], 'segunda aprobación inicial')
        self.assertEqual(row['codigo_ine'], '48001')
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertIsNone(adapter.root_kind('Licencia de obras'))

    def test_inventory_pagination_and_cycle(self):
        adapter = AbadinoAyuntamientoAdapter()
        next_url = AREA + '/_api/next'
        def page(path, title, next_link=None):
            d = {'results': [{'Title': title, 'File': {'ServerRelativeUrl': '/es-ES/Servicios/Urbanismo/Paginas/' + path}}]}
            if next_link:
                d['__next'] = next_link
            return Mock(json=lambda: {'d': d})
        with patch.object(adapter, '_get', side_effect=[page('a.aspx', 'Plan General de Ordenación Urbana', next_url), page('b.aspx', 'Modif NNSS Murueta')]) as get:
            self.assertEqual(len(adapter.inventory()), 2)
            self.assertEqual(get.call_count, 2)
        with patch.object(adapter, '_get', return_value=page('a.aspx', 'Plan', INDEX)):
            with self.assertRaisesRegex(ValueError, 'continuation'):
                adapter.inventory()

    def test_fail_closed_and_only_content_documents(self):
        root = AREA + '/Paginas/plan.aspx'
        for html in ['<html>error</html>', '<main id="main-content"><a rel="next" href="p2">2</a></main>']:
            with self.assertRaises(ValueError):
                AbadinoAyuntamientoAdapter.parse_page(html, root)
        docs, children = AbadinoAyuntamientoAdapter.parse_page(
            '<a href="/nav.pdf">outside</a><main id="main-content"><a href="https://other.example/a.pdf">foreign</a></main>', root)
        self.assertEqual((docs, children), ([], set()))
        adapter = AbadinoAyuntamientoAdapter()
        with patch.object(adapter, '_get', return_value=Mock(text='<main id="main-content"></main>')):
            with self.assertRaisesRegex(ValueError, 'no source documents'):
                adapter.extract({root: 'Plan General de Ordenación Urbana'})
        with self.assertRaises(ValueError):
            canonical('https://other.example/plan.pdf')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('abadino')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '48001')
        self.assertEqual(manifest.provincia, 'Bizkaia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(AbadinoAyuntamientoAdapter().backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
