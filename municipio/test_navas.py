import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.navas import NavasAyuntamientoAdapter, SOURCES, parse_inventory
from municipio.manifest import load_manifest


def fixture(key='poum', narrative=None):
    title = ('Pla d’Ordenació Urbanística Municipal (POUM)' if key == 'poum' else
             'Pla especial urbanístic de protecció del patrimoni de Navàs')
    if narrative is None:
        narrative = "Text Refòs del Pla de Navàs aprovat definitivament el mes d'abril de 2019"
    return f'''<main><h1>{title}</h1><article class="page-interior">
    <article class="content"><p>{narrative}</p></article>
    <article class="file-block"><h2 class="title">Normes</h2>
    <a href="/wp-content/uploads/2021/01/normes.pdf">Descarregar</a></article>
    <article class="file-block"><h2 class="title">Plànols</h2>
    <a href="/wp-content/uploads/2021/01/planols.pdf">Descarregar</a></article>
    </article></main>'''


class NavasTests(unittest.TestCase):
    def test_groups_documents_and_keeps_partial_date(self):
        row = parse_inventory(fixture(), 'poum')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob_mes'], '2019-04')
        for name in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[name])
        self.assertEqual(row['codigo_ine'], '08141')

    def test_catalog_does_not_invent_phase_or_dates_from_upload_path(self):
        row = parse_inventory(fixture('patrimoni', 'Pla del patrimoni de Navàs amb documents.'), 'patrimoni')
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_rejects_navigation_login_missing_documents_and_wrong_municipality(self):
        for html in ['<a href="/poum/">POUM</a>', '<form>Identifica’t</form>',
                     fixture().replace('file-block', 'navigation'),
                     fixture().replace('Navàs', 'Manlleu')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, 'poum')

    def test_pagination_and_changed_document_links_fail(self):
        for html in [fixture() + '<a rel="next" href="?page=2">2</a>',
                     fixture() + '<button>Veure’n més</button>',
                     fixture().replace('/wp-content/uploads/2021/01/normes.pdf', 'https://example.com/x.pdf'),
                     fixture().replace("d'abril de 2019", 'el 2019')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, 'poum')

    def test_snapshot_failure_preserves_previous_output(self):
        adapter = NavasAyuntamientoAdapter('navas')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rows.jsonl'
            output.write_text('previous\n')
            with patch.object(adapter, '_fetch', side_effect=[fixture(), '<html>unavailable</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous\n')
            with patch.object(adapter, '_fetch', side_effect=[fixture(), fixture('patrimoni')]):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len({row['id'] for row in rows}), 2)
            self.assertEqual([row['url'] for row in rows], list(SOURCES.values()))

    def test_manifest(self):
        manifest = load_manifest('navas')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.navas:NavasAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
