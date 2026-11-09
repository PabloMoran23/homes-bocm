import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.teia import SOURCE, TeiaAyuntamientoAdapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def row(title='Projecte de reforma del parc', date='02-05-2026', href='/documents/parc.pdf'):
    return f'<tr><td>{date}</td><td><a href="{href}">{title}</a></td></tr>'


def inventory(rows):
    return '<table id="projectTable"><thead><tr><th>Data del Projecte</th><th>Nom del Projecte</th></tr></thead><tbody>' + rows + '</tbody></table>'


class TeiaTests(unittest.TestCase):
    def test_dates_and_provenance(self):
        r = TeiaAyuntamientoAdapter.parse_projects(inventory(row()))[0]
        self.assertEqual(r['fecha_proyecto_fuente'], '2026-05-02')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(r[field])
        self.assertEqual(r['documentos'][0]['provenance_url'], SOURCE)
        self.assertFalse(r['documentos'][0]['contenido_verificado'])

    def test_group_documents_and_dates(self):
        rows = row() + row(date='03-05-2026', href='/documents/parc2.pdf') + row()
        r = TeiaAyuntamientoAdapter.parse_projects(inventory(rows))
        self.assertEqual(len(r), 1)
        self.assertEqual(len(r[0]['documentos']), 2)
        self.assertIsNone(r[0]['fecha_proyecto_fuente'])
        self.assertEqual(len(r[0]['entradas_fuente']), 3)

    def test_excludes_housing_allocation(self):
        html = inventory(row() + row('Procés d’adjudicació d’habitatges en règim de lloguer per a joves'))
        self.assertEqual(len(TeiaAyuntamientoAdapter.parse_projects(html)), 1)

    def test_no_silent_unknown_categories(self):
        for title in ('Sol·licitud llicència', 'Anunci de licitació', 'Notícies del poble'):
            with self.subTest(title=title), self.assertRaises(ValueError):
                TeiaAyuntamientoAdapter.parse_projects(inventory(row(title)))

    def test_pagination_rejected(self):
        for pager in ('<a rel="next" href="?page=2">2</a>', '<div class="pagination">2</div>', '<a href="?start=20">20</a>'):
            with self.subTest(pager=pager), self.assertRaises(ValueError):
                TeiaAyuntamientoAdapter.parse_projects(inventory(row()) + pager)

    def test_invalid_sources(self):
        for html in ('<html>Login</html>', inventory(''), inventory(row(date='31-02-2026')), inventory(row(href='https://example.org/foo'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                TeiaAyuntamientoAdapter.parse_projects(html)

    def test_planning_folder_and_missing_date(self):
        r = TeiaAyuntamientoAdapter.parse_projects(inventory(row('Avanç de planejament del Pla d’ordenació POUM', '', 'https://ajuntamentteia.sharepoint.com/:f:/s/PUB_GENERAL/abc?e=123 ')))[0]
        self.assertEqual(r['tipo'], 'planeamiento_urbanistico')
        self.assertEqual(r['documentos'][0]['tipo_enlace'], 'carpeta')
        self.assertIsNone(r['fecha_proyecto_fuente'])

    def test_manifest_and_live_method_contract(self):
        manifest = load_manifest('teia')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08281')
        self.assertEqual(manifest.provincia, 'Barcelona')
        for section in ('schedule', 'licencias'):
            self.assertFalse(raw[section]['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.teia.requests.get') as get:
            get.return_value.text = inventory(row())
            get.return_value.content = get.return_value.text.encode()
            path = Path(d) / 'projects.jsonl'
            self.assertEqual(adapter.update_proyectos(path, Path(d) / 'state.json')['rows'], 1)
            self.assertEqual(len(path.read_text().splitlines()), 1)
            get.return_value.raise_for_status.assert_called_once()


if __name__ == '__main__':
    unittest.main()
