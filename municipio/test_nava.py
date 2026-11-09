"""Parser regressions use small synthetic fixtures, never the live network."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.nava import NavaAyuntamientoAdapter, SECTIONS, SOURCE, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    sections = []
    for i, name in enumerate(SECTIONS):
        sections.append(f'''<h3>{name}</h3><ul>
          <li><a href="/c/document_library/get_file?uuid=doc-{i}&amp;groupId=118304">Normativa</a></li>
          <li>Fichas<ul><li><a href="/documents/118304/123/plano.pdf/id-{i}?t=1770803001515">Plano</a></li></ul></li>
          </ul>''')
    return '<div class="journal-content-article"><div class="titulo"><h2>Urbanismo</h2></div><div class="detalle">' + ''.join(sections) + '</div></div>'


class NavaTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({r['id'] for r in rows}), 5)
        self.assertTrue(all(len(r['documentos']) == 2 for r in rows))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '33040')
            self.assertEqual(row['url'], SOURCE)
            self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
            self.assertEqual(row['documentos'][0]['seccion'], row['titulo_fuente'])
            self.assertIsNone(row['fecha_publicacion'])  # query t is not a date
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fase'])
            self.assertIsNone(row['geometry'])
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])

    def test_reject_empty_login_and_navigation(self):
        for html in ('', '<h1>Login</h1>', '<a href="/urbanismo-y-vivienda">Urbanismo</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_changed_missing_or_duplicate_sections(self):
        for html in (fixture().replace('PERMEUN', 'Nuevo plan'),
                     fixture().replace('<h3>PERMEUN</h3>', ''),
                     fixture().replace('PERMEUN', 'Normas Subsidiarias')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_pagination(self):
        for pagination in ('<a href="?page=2">Siguiente</a>',
                           '<a rel="next" href="?page=2">2</a>',
                           '<div class="pagination">1 2</div>'):
            with self.assertRaises(ValueError):
                parse_inventory(fixture().replace('</div></div>', pagination + '</div></div>'))

    def test_missing_documents_and_unexpected_targets(self):
        for html in (fixture().replace('href=', 'data-href='),
                     fixture().replace('/documents/118304/', 'https://example.org/'),
                     fixture().replace('groupId=118304', 'groupId=999')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_repeated_document_deduped_within_instrument(self):
        html = fixture().replace('</ul></li>', '</ul></li><li><a href="/c/document_library/get_file?uuid=doc-0&amp;groupId=118304">Duplicado</a></li>', 1)
        self.assertEqual(len(parse_inventory(html)[0]['documentos']), 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('nava')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '33040')
        self.assertEqual(manifest.provincia, 'Asturias')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, NavaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')

    def test_update_refreshes_whole_snapshot(self):
        adapter = NavaAyuntamientoAdapter('nava')
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'proyectos.jsonl'
            adapter._write(out, [{'id': 'obsolete'}])
            rows = parse_inventory(fixture())
            def backfill(path):
                adapter._write(path, rows)
                return {'rows': len(rows)}
            with patch.object(adapter, 'backfill_proyectos', side_effect=backfill) as fetch:
                self.assertEqual(adapter.update_proyectos(out, Path(d) / 'state.json')['rows'], 5)
                fetch.assert_called_once_with(out)
            self.assertEqual([json.loads(line)['id'] for line in out.read_text().splitlines()], [r['id'] for r in rows])


if __name__ == '__main__':
    unittest.main()
