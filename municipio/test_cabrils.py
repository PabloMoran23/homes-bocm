import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cabrils import CabrilsAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def fixture(extra=''):
    return '''<h1>POUM</h1><div class="ddbbtext">
    <p>Documentació: documentació relativa al POUM vigent actualment:</p>
    <a href="/media/repository/POUM/Normes_urbanistiques.pdf">Normes urbanístiques</a>
    <a href="/media/repository/POUM/Annex.pdf">Annex</a>''' + extra + '''</div>
    <span class="updated">Darrera actualització: 26.10.2026 | 09:29</span>'''


class CabrilsTests(unittest.TestCase):
    def test_groups_every_document_and_preserves_provenance(self):
        links = ''.join(f'<a href="/media/repository/POUM/plan{i}.pdf">Plànol {i}</a>' for i in range(80))
        rows = parse_inventory(fixture(links))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 82)
        self.assertTrue(all(d['source_url'] == SOURCE for d in rows[0]['documentos']))
        self.assertEqual(rows[0]['codigo_ine'], '08030')

    def test_dates_and_geometry_are_not_inferred(self):
        row = parse_inventory(fixture())[0]
        self.assertEqual(row['fecha_actualizacion_fuente'], '2026-10-26')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_duplicate_documents_do_not_duplicate_instrument(self):
        row = parse_inventory(fixture('<a href="/media/repository/POUM/Annex.pdf">Annex repetit</a>'))[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['titulos_fuente'], ['Annex', 'Annex repetit'])
        self.assertEqual(row['id'], parse_inventory(fixture())[0]['id'])

    def test_rejects_forms_news_login_and_missing_inventory(self):
        for html in ('<h1>Login</h1>', '<h1>POUM</h1><a href="formulari.pdf">Sol·licitud</a>',
                     '<h1>Notícies</h1>' + fixture(), fixture().replace('Normes_urbanistiques.pdf', 'form.pdf')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_rejects_pagination_and_unreviewed_links(self):
        for extra in ('<a rel="next" href="?page=2">2</a>', '<div class="pagination">2</div>',
                      '<a href="?page=2">Següent</a>', '<a href="https://example.org/doc.pdf">Doc</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(fixture(extra))

    def test_manifest_and_refresh_contract(self):
        manifest = load_manifest('cabrils')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08030')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CabrilsAyuntamientoAdapter)
        adapter = CabrilsAyuntamientoAdapter('cabrils')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            adapter._write(out, parse_inventory(fixture()))
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '08030')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as refresh:
                self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json'), {'rows': 1})
                refresh.assert_called_once_with(out)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
