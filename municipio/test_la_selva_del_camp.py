"""Parser contract tests; fixtures intentionally omit any claimed approval dates."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_selva_del_camp import LaSelvaDelCampAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def fixture(extra='', sheet=True):
    return '''<div class="journal-content-article">
    <p>PLANEJAMENT URBANÍSTIC VIGENT: LES NORMES SUBSIDIÀRIES DE LA SELVA DEL CAMP</p>
    <p>Aprovades definitivament l'any 1998. Documents provisionals pendents d'aprovació.</p>
    <ul><li><a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/221130">Text Refós normes urbanístiques planejament general</a> - 19 de juliol 2005</li>
    <li>Plànols del planejament general</li></ul>''' + (
        '<p><a href="/documents/1/2/sheet.pdf/uuid">PLÀNOL-1 - Situació</a></p>' if sheet else '') + '''
    <ul><li><a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/232929">MPNSP 09 - Sòl rural i activitats</a> - Regulació del sòl.</li>
    <li><a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/236793">Pla territorial general</a> - Camp de Tarragona.</li></ul>
    <div class="paginacio_footer">Actualització: 28/02/2025</div>''' + extra + '</div>'


class PlanningTests(unittest.TestCase):
    def test_grouping_identity_and_provenance(self):
        rows = Adapter.parse_projects(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['rpuc_id'], '221130')
        self.assertEqual(rows[0]['expediente_grupo'], 'RPUC 221130')
        self.assertNotIn('expediente', rows[0])
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][1]['url'], 'https://seu-e.cat/documents/1/2/sheet.pdf/uuid')
        self.assertIn('Regulació del sòl', rows[1]['descripcion'])
        self.assertTrue(all(d['source_url'] == rows[0]['url'] for d in rows[0]['documentos']))

    def test_dates_and_geometry_are_not_invented(self):
        for row in Adapter.parse_projects(fixture()):
            for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])

    def test_repeated_dossier_grouped(self):
        duplicate = '<ul><li><a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/232929">MPNSP 09 - Sòl rural i activitats</a></li></ul>'
        rows = Adapter.parse_projects(fixture(duplicate))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)

    def test_missing_content_and_sheets_fail(self):
        for html in ['<a href="/licencia">Sol·licitud de llicència</a>', '<h1>Login</h1>', fixture(sheet=False)]:
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_fails_without_partial_output(self):
        for pagination in ['<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Següent</a>', '<ul class="pagination"><li><a href="?page=2">2</a></li></ul>']:
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                Adapter.parse_projects(fixture(pagination))

    def test_unknown_items_or_wrong_dossier_host_fail(self):
        for html in [fixture('<ul><li>Nou pla sense enllaç</li></ul>'), fixture().replace('dtes.gencat.cat', 'example.org'), fixture().replace('MPNSP 09', 'Convocatòria')]:
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_snapshot_update_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            adapter = Adapter('la-selva-del-camp')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state.json')['rows'], 2)
                backfill.assert_called_once_with(path)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
            adapter._write(path, Adapter.parse_projects(fixture()))
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 2)

    def test_manifest_contract(self):
        manifest = load_manifest('la-selva-del-camp')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '43145')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)


if __name__ == '__main__':
    unittest.main()
