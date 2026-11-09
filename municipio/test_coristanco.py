"""Parser contract tests; fixtures are synthetic markup, not extracted records."""
import unittest

from municipio.adapters.coristanco import LABELS, SOURCE, parse_projects
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    return '<section><h2>PXOM</h2>' + ''.join(
        f'<div data-pdf-url="/wp-content/uploads/2026/05/{label.replace(" ", "")}.pdf">{label}</div>'
        for label in sorted(LABELS)) + '</section>'


class CoristancoTests(unittest.TestCase):
    def test_groups_all_documents_and_deduplicates(self):
        html = fixture()
        html = html.replace('</section>', '<div data-pdf-url="/wp-content/uploads/2026/05/TOMOI.pdf">TOMO I</div></section>')
        rows = parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 6)
        self.assertTrue(all(d['source_url'] == SOURCE for d in rows[0]['documentos']))

    def test_upload_dates_are_not_approval_dates_or_geometry(self):
        row = parse_projects(fixture())[0]
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_rejects_forms_navigation_and_incomplete_inventory(self):
        for html in ('<a>PXOM</a>', '<h2>PXOM</h2><a href="form.pdf">Solicitude de licenza</a>',
                     fixture().replace('TOMO V', 'FORMULARIO')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_rejects_foreign_documents_and_conflicts(self):
        for html in (fixture().replace('/wp-content/', 'https://example.org/wp-content/', 1),
                     fixture().replace('</section>', '<div data-pdf-url="/wp-content/uploads/other.pdf">TOMO I</div></section>')):
            with self.assertRaises(ValueError):
                parse_projects(html)

    def test_pagination_fails_instead_of_truncating(self):
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            parse_projects(fixture() + '<a rel="next" href="?page=2">Seguinte</a>')

    def test_manifest_resolves_adapter(self):
        manifest = load_manifest('coristanco')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(load_portal_adapter(manifest).slug, 'coristanco')


if __name__ == '__main__':
    unittest.main()
