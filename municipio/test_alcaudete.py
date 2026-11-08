import unittest
from municipio.adapters.alcaudete import inventory_pdf, parse_inventory
from municipio.manifest import load_manifest

PDF = 'https://www.dipujaen.es/inventario.pdf'


def section(rows):
    return ('MUNICIPIO:       002. ALCALÁ LA REAL\n'
            'Estudio de Detalle   Ajeno   Ap. Inicial\n'
            'MUNICIPIO:       003. ALCAUDETE\n' + rows +
            '\nMUNICIPIO:       BOBADILLA (LA)\n'
            'Estudio de Detalle   Ajeno Bobadilla   Ap. Inicial\n')


class ParserTests(unittest.TestCase):
    def test_multiline_grouping_and_provenance(self):
        text = section('Estudio de Detalle   Solar sobre Avda. Andalucía   Ap. Inicial   01/06/2007   23/05/2007\n'
                       '                     y Camino Viejo                Ap. Definitiva   27/07/2007\n'
                       'Ordenanza Fiscal     Tasas                         Ap. Inicial\n'
                       '                     Texto ajeno\n'
                       'Estudio de Detalle   Solar sobre Avda. Andalucía   Ap. Inicial\n'
                       '                     y Camino Viejo\n')
        rows = parse_inventory(text, PDF)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ambito'], 'Solar sobre Avda. Andalucía y Camino Viejo')
        self.assertEqual(len(rows[0]['extractos_fuente']), 2)
        self.assertEqual(rows[0]['documentos'][0]['url'], PDF + '#page=1')
        self.assertNotIn('fecha_aprob', rows[0])
        self.assertNotIn('fecha_publicacion', rows[0])
        self.assertNotIn('lat', rows[0])
        self.assertFalse(rows[0]['publication_ready'])

    def test_all_pages_and_no_unrelated_figures(self):
        rows = parse_inventory(section('Proyecto Urbanización   Proyecto\n'
            'Estudio de Detalle   Calle Uno   Ap. Inicial\n'
            '\n10/09/2026\n13:17\n        9\n\f'
            'Estudio de Detalle   Calle Dos   Ap. Inicial\n'), PDF)
        self.assertEqual([r['ambito'] for r in rows], ['Calle Uno', 'Calle Dos'])
        self.assertEqual(rows[1]['documentos'][0]['pagina_pdf'], 2)
        self.assertEqual(rows[0]['codigo_ine'], '23003')

    def test_spacing_inside_scope_is_not_a_column(self):
        rows = parse_inventory(section('Estudio de Detalle   Poligono 2 del    P.P.   Los Pozuelos   Ap. definitiva   07/01/1999\n'
                                       '                     Modificación nº 1\n'), PDF)
        self.assertEqual(rows[0]['ambito'], 'Poligono 2 del P.P. Los Pozuelos Modificación nº 1')

    def test_incomplete_and_empty_fail(self):
        for text in ['', section('Ordenanza Fiscal   Tasas'),
                     'MUNICIPIO:       003. ALCAUDETE\nEstudio de Detalle   Calle   Ap. Inicial']:
            with self.assertRaises(ValueError):
                parse_inventory(text, PDF)

    def test_discovery_and_pagination(self):
        label = 'Desarrollo del Planeamiento de la Provincia'
        self.assertEqual(inventory_pdf(f'<a href="/inventario.pdf">{label}</a>'), PDF)
        for html in ['', f'<a href="https://example.com/a.pdf">{label}</a>',
                     f'<a href="/inventario.pdf">{label}</a><a rel="next" href="?page=2">2</a>']:
            with self.assertRaises(ValueError):
                inventory_pdf(html)

    def test_manifest(self):
        m = load_manifest('alcaudete')
        self.assertEqual(m.provincia, 'Jaén')
        self.assertFalse(m.licencias.enabled)
        self.assertEqual(m.portal.adapter, 'municipio.adapters.alcaudete:AlcaudeteAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
