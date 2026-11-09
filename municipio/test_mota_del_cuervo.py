import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.mota_del_cuervo import (
    MotaDelCuervoAyuntamientoAdapter, SOURCE, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest

DETAIL_URL = SOURCE.rsplit('/', 1)[0] + '/pau/el-tesoro'
TITLE = 'PAU 4/2006 "EL TESORO" de las NNSS de Mota del Cuervo (Cuenca)'


def inventory(extra='', municipality='Mota del Cuervo', link='/registros/pau/el-tesoro'):
    return f'''<table class="views-table"><thead><tr><th>Denominación</th>
    <th>Municipio</th><th>Fecha de constitución</th></tr></thead><tbody><tr>
    <td><a href='{link}'>{TITLE}</a></td><td>{municipality}</td><td>25/09/2020</td>
    </tr></tbody></table>{extra}'''


def detail(documents=''):
    return f'''<main><article class="node--type-programa-actuacion-urbanizadora">
    <h1>{TITLE}</h1><div class="field--name-municipios-clm"><ul>
    <li>CUENCA</li><li>Mota del Cuervo</li></ul></div>
    <div class="field--name-field-fecha-aprobacion">
    <div class="field__label">Fecha de aprobación</div><time datetime="2020-09-25T12:00:00Z">25/09/2020</time></div>
    <div class="field--name-field-datos-inscripcion"><div class="field__item">
    PAU inscrito el 9 de noviembre de 2020.</div></div>{documents}</article></main>'''


class ParserTests(unittest.TestCase):
    def test_exact_municipality_not_title_substring(self):
        entries, _ = parse_inventory(inventory(municipality='Cuenca'))
        self.assertEqual(entries, [])
        entries, _ = parse_inventory(inventory(municipality='Mota del Cuervo y otros'))
        self.assertEqual(entries, [])

    def test_dates_and_grouped_documents(self):
        entry = parse_inventory(inventory())[0][0]
        html = detail('''<a href="/sites/default/files/memoria.pdf">Memoria</a>
        <a href="/sites/default/files/plano.pdf">Plano</a>
        <a href="/sites/default/files/memoria.pdf">Repetido</a>''')
        row = parse_detail(html, entry)
        self.assertEqual(row['fecha_aprob'], '2020-09-25')
        self.assertIn('9 de noviembre', row['datos_inscripcion_original'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '16133')

    def test_missing_and_mismatched_sources_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory('<a>Solicitud de licencia</a>')
        with self.assertRaises(ValueError):
            parse_inventory(inventory(link='https://example.org/registros/pau/x'))
        entry = parse_inventory(inventory())[0][0]
        for html in [detail().replace('CUENCA', 'TOLEDO'), '<h1>Noticia</h1>',
                     detail().replace('Fecha de aprobación', 'Fecha de publicación')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, entry)

    def test_missing_approval_is_not_inferred_from_list(self):
        entry = parse_inventory(inventory())[0][0]
        html = detail().replace('field--name-field-fecha-aprobacion', 'other-date')
        self.assertIsNone(parse_detail(html, entry)['fecha_aprob'])

    def test_pagination_deduplicates_records_and_preserves_all_documents(self):
        next_page = SOURCE + '?page=1'
        pages = {SOURCE: inventory('<nav class="pager"><a href="?page=1">Siguiente</a></nav>'),
                 next_page: inventory('<nav class="pager"><a href="/registros/pau-cu">Anterior</a></nav>'),
                 DETAIL_URL: detail('<a href="/sites/default/files/plan.pdf">Plan</a>')}
        visited = []
        def fetch(url):
            visited.append(url)
            return pages[url]
        adapter = MotaDelCuervoAyuntamientoAdapter('mota-del-cuervo')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=fetch):
            output = Path(folder) / 'projects.jsonl'
            result = adapter.update_proyectos(output, Path(folder) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(result['inventory_pages'], 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(visited, [SOURCE, next_page, DETAIL_URL])

    def test_failed_later_page_never_writes_partial_snapshot(self):
        adapter = MotaDelCuervoAyuntamientoAdapter('mota-del-cuervo')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[
                inventory('<a rel="next" href="?page=1">Next</a>'), '<html>Unavailable</html>'
            ]), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('mota-del-cuervo')
        self.assertEqual(manifest.provincia, 'Cuenca')
        self.assertFalse(manifest.licencias.enabled)
        adapter = MotaDelCuervoAyuntamientoAdapter('mota-del-cuervo')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
