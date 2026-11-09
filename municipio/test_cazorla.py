import unittest

from municipio.adapters.cazorla import SOURCE, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


HEADER = '''<tr><th>DENOMINACIÓN PROYECTO Y ALCANCE POR MEDIDA</th>
<th>Nº EXP. IDAE</th><th>INVERSIÓN TOTAL PROYECTO</th>
<th>FINANCIACIÓN FONDOS FEDER (80%)</th><th>APORTACIÓN MUNICIPAL (20%)</th></tr>'''


def row(exp='5716', title='Bombas de calor en el Ayuntamiento de Cazorla', link=''):
    return f'<tr><td>{title}{link}</td><td>{exp}</td><td>88.250,00 €</td><td>70.600,00 €</td><td>17.650,00 €</td></tr>'


def page(rows, extra=''):
    return '<article class="page"><table>' + HEADER + rows + '</table>' + extra + '</article>'


class CazorlaTests(unittest.TestCase):
    def test_real_project_semantics_and_provenance(self):
        r = parse_inventory(page(row()))[0]
        self.assertEqual(r['id'], 'cazorla-idae-5716')
        self.assertEqual(r['codigo_ine'], '23028')
        self.assertEqual(r['inversion_total_texto'], '88.250,00 €')
        self.assertEqual(r['documentos'][0]['url'], SOURCE)
        self.assertIn('5716', r['documentos'][0]['localizador'])
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, r)

    def test_group_documents_and_isolate_projects(self):
        a = '<a href="/a.pdf"></a>'
        b = '<a href="/b.pdf"></a>'
        rows = parse_inventory(page(row(link=a) + row(link=b) + row('5660', 'Piscina municipal')))
        self.assertEqual(len(rows), 2)
        self.assertEqual([d['url'] for d in rows[0]['documentos']], [SOURCE, 'https://cazorla.es/a.pdf', 'https://cazorla.es/b.pdf'])
        self.assertEqual(len(rows[1]['documentos']), 1)

    def test_all_rows_without_fixed_limit(self):
        self.assertEqual(len(parse_inventory(page(''.join(row(str(n)) for n in range(60))))), 60)

    def test_reject_incomplete_or_changed_inventory(self):
        for html in ('<p>Formulario de licencia</p>', page(''), page(row() + '<tr><td>broken</td></tr>'),
                     page(row('not an expediente')), page(row() + row(title='Conflicting project')),
                     page(row(), '<a rel="next" href="/page/2">2</a>'),
                     page(row(), '<a href="/page/2">Entradas más antiguas</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('cazorla')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(load_portal_adapter(manifest).slug, 'cazorla')


if __name__ == '__main__':
    unittest.main()
