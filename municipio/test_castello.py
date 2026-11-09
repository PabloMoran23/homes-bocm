import unittest
from municipio.adapters.castello import parse_inventory, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

DOC = 'https://castello.sedelectronica.es/preview-document/42dfa6a1-f51a-4f2a-b15d-3556257747a3'


def fixture(extra='', title="PLA D'ORDENACIÓ DETALLADA COMPLET", url=DOC):
    return f'''<h2>6.1.2. NORMATIVA URBANÍSTICA</h2><table><tbody><tr><td>
    <a href="{url}" title="Aprovació definitiva del Pla d'Ordenació Detallada">{title}</a>
    </td></tr></tbody></table>{extra}'''


class CastelloTests(unittest.TestCase):
    def test_actual_plan_and_date_semantics(self):
        row, = parse_inventory(fixture() + '<footer>9 novembre 2026</footer>', 1)
        self.assertEqual(row['codigo_ine'], '46257')
        self.assertEqual(row['fase'], 'aprobación definitiva')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(row['documentos'][0]['url'], DOC)

    def test_group_documents_and_deduplicate(self):
        html = fixture() + fixture(url=DOC + '-annex', title="PLA D'ORDENACIÓ DETALLADA PLÀNOLS") + fixture()
        row, = parse_inventory(html, 2)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['id'], parse_inventory(fixture())[0]['id'])

    def test_no_plan_from_navigation_or_login(self):
        for html in ('<h1>Identifica’t</h1>', '<a href="' + DOC + '">Pla general</a>', fixture(title='Sol·licitud de llicència')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_count_mismatch_and_pagination_fail(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture(), 2)
        for extra in ('<a href="?page=2">Veure\'n més</a>', '<a rel="next" href="?page=2">2</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(fixture(extra), 1)

    def test_external_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture(url='https://example.org/preview-document/x'))

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('castello')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(load_portal_adapter(manifest).slug, 'castello')
        self.assertEqual(parse_inventory(fixture())[0]['url'], SOURCE)


if __name__ == '__main__':
    unittest.main()
