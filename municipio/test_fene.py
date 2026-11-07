import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.fene import FeneAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(extra=''):
    entries = [('Memoria', 'Memoria2002.pdf'), ('Normas Urbanísiticas 1', 'normas.pdf'),
               ('Estudo Económico Financeiro', 'economico.pdf')]
    links = ''.join(f'<h3 class="entry-title"><a href="../../media/../media/documentos/{name}">{title}</a></h3>'
                    for title, name in entries)
    return ('<div id="Subheader"><h1 class="title">PXOM</h1></div>'
            '<div id="Content"><div class="sections_group">' + links + extra + '</div></div>')


class FeneTests(unittest.TestCase):
    def test_grouping_provenance_and_unknown_semantics(self):
        rows = parse_inventory(inventory('<a href="/licenza.pdf">Formulario de licenza</a>'))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '15035')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][0]['url'], 'https://www.fene.gal/media/documentos/Memoria2002.pdf')
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])  # 2002 in a filename is not an approval date.
        self.assertFalse(row['publication_ready'])

    def test_no_document_limit_and_duplicate_links(self):
        extra = ''.join(f'<h3 class="entry-title"><a href="/media/documentos/{i}.zip">Anexo {i}</a></h3>'
                        for i in range(60))
        duplicate = '<h3 class="entry-title"><a href="/media/documentos/Memoria2002.pdf">Memoria</a></h3>'
        self.assertEqual(len(parse_inventory(inventory(extra + duplicate))[0]['documentos']), 63)

    def test_live_latin1_encoding(self):
        raw = ('<meta charset="iso-8859-1">' + inventory()).encode('iso-8859-1')
        self.assertEqual(parse_inventory(raw)[0]['documentos'][2]['titulo'], 'Estudo Económico Financeiro')

    def test_reject_pagination(self):
        for extra in ('<a rel="next" href="?page=2">2</a>', '<div class="pager_wrapper">2</div>',
                      '<a href="?page=2">Seguinte</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(inventory(extra))
        self.assertEqual(len(parse_inventory(inventory('<div class="pager"><!-- empty --></div>'))), 1)

    def test_reject_missing_or_changed_documents(self):
        for html in ('<h1>Login</h1>', inventory().replace('Memoria</a>', 'Formulario</a>'),
                     inventory().replace('../../media/../media/documentos/Memoria2002.pdf', 'https://example.org/form.pdf'),
                     inventory().replace('class="entry-title"', 'class="changed"')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        raw = load_yaml(Path('data/municipios/fene/manifest.yaml'))
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('15035', 'A Coruña'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        adapter = load_portal_adapter(load_manifest('fene'))
        self.assertIsInstance(adapter, FeneAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            with patch('municipio.adapters.fene.requests.get', side_effect=AssertionError('network')):
                result = adapter.backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')

    def test_live_path_and_snapshot_update(self):
        class Response:
            url = SOURCE
            headers = {'Content-Type': 'text/html; charset=utf-8'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield inventory().encode()

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            adapter = FeneAyuntamientoAdapter('fene', {'capture_dir': tmp})
            with patch('municipio.adapters.fene.requests.get', return_value=Response()):
                adapter.backfill_proyectos(out)
                adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(len(out.read_text().splitlines()), 1)
            self.assertEqual(json.loads(out.read_text())['id'], 'fene-pxom')
            self.assertTrue((Path(tmp) / 'pxom.html').exists())


if __name__ == '__main__':
    unittest.main()
