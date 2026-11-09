"""Offline parser contract tests; fixtures do not depend on evidence files."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from municipio.adapters.ortigueira import SOURCE, OrtigueiraAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture(extra='', approval='1993-05-27', document='normas.docx'):
    def table(identifier, figure, label, target):
        return f'''<div><table id="{identifier}"><thead><tr>
        <th>FIGURA</th><th>TÍTULO</th><th>APROB. DEF</th><th>BOP</th><th>DOG</th><th>NORMATIVA</th>
        </tr></thead><tbody><tr><td>{figure}</td><td><a href="/wp-content/uploads/{target}">{label}</a></td>
        <td>{approval}</td><td>1993-06-19</td><td>1993-09-20</td><td></td></tr></tbody></table>{extra}</div>'''
    return (table('gralPlanTableSortable', 'Normas subsidiarias de planeamiento', 'DESCARGA WORD NSP', document)
            + table('planDesTableSortable', 'Estudio de detalle', 'DESCARGA WORD Rúa Outeiro', 'outeiro.docx'))


class OrtigueiraTests(unittest.TestCase):
    def test_real_instrument_semantics_and_dates(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '15061')
        self.assertEqual(row['fecha_aprob'], '1993-05-27')
        self.assertEqual(row['fecha_publicacion_bop'], '1993-06-19')
        self.assertEqual(row['fecha_publicacion_dog'], '1993-09-20')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_publicacion_normativa'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['documentos'][0]['procedencia'], SOURCE)
        self.assertIn('Rúa Outeiro', rows[1]['titulo'])
        wordpress = '<script>var _wpUtilSettings = {"ajax": {"url": "/wp-admin/admin-ajax.php"}};</script>'
        self.assertEqual(parse_inventory(fixture(extra=wordpress)), rows)

    def test_group_documents_and_duplicate_rows(self):
        html = fixture()
        start = html.index('<tr><td>Normas')
        end = html.index('</tr>', start) + len('</tr>')
        duplicate = html[start:end].replace('normas.docx', 'normas-planos.docx')
        html = html[:end] + duplicate + html[end:]
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['id'], parse_inventory(fixture())[0]['id'])

    def test_fail_on_pagination_or_dynamic_source(self):
        for extra in ('<a href="?page=2" rel="next">Siguiente</a>',
                      '<div id="gralPlanTableSortable_info">1 a 10 de 20</div>',
                      '<script>var opts = {serverSide: true};</script>',
                      '<script>$("#gralPlanTableSortable").DataTable({ajax: "/rows"});</script>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(fixture(extra=extra))

    def test_fail_on_missing_or_changed_source(self):
        for html in ('<h1>Licencia de obras: solicitud</h1>',
                     fixture(approval='1993-02-30'),
                     fixture(document='solicitud.pdf'),
                     fixture().replace('Estudio de detalle', 'Anuncio de contratación'),
                     fixture().replace('1993-06-19', 'fecha desconocida')):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_same_figure_different_locations_are_distinct(self):
        html = fixture()
        start = html.index('<tr><td>Estudio')
        end = html.index('</tr>', start) + len('</tr>')
        extra = html[start:end].replace('Rúa Outeiro', 'Avda Penela').replace('outeiro.docx', 'penela.docx')
        rows = parse_inventory(html[:end] + extra + html[end:])
        self.assertEqual(len({r['id'] for r in rows}), 3)

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('ortigueira')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, OrtigueiraAyuntamientoAdapter)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
