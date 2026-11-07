import unittest

from municipio.adapters.la_bisbal_d_emporda import LaBisbalDEmpordaAyuntamientoAdapter as Adapter


def inventory(*titles):
    links = ''.join(f'<li><a href="/wp-content/uploads/2026/10/{i}.pdf">{t}</a></li>'
                    for i, t in enumerate(titles))
    return ('<div class="elementor-widget-wrap"><h1>Obres locals</h1>'
            '<h2>En exposició pública</h2><ul>' + links + '</ul></div>')


class ProjectParserTests(unittest.TestCase):
    def test_document_grouping_and_distinct_places(self):
        html = inventory('PROJECTE DE REURBANITZACIÓ DEL CARRER NOU_PART 1',
                         'PROJECTE DE REURBANITZACIÓ DEL CARRER NOU_PART 2',
                         'PROJECTE DE REURBANITZACIÓ DEL CARRER NOU_PRESSUPOST',
                         'PROJECTE DE REURBANITZACIÓ DEL CARRER NOU_PLÀNOLS',
                         'PROJECTE DE REURBANITZACIÓ DEL CARRER NOU_PLEC DE CONDICIONS',
                         "PROJECTE D'URBANITZACIÓ DE LA PLAÇA DEL CALL",
                         "PROJECTE D'URBANITZACIÓ DEL CARRER DEL CALL")
        rows = Adapter.parse_projects(html)
        self.assertEqual([len(r['documentos']) for r in rows], [5, 1, 1])
        self.assertEqual(len({r['id'] for r in rows}), 3)
        # Source upload directories and extraction time are not agreement dates.
        for row in rows:
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            self.assertEqual(row['codigo_ine'], '17022')

    def test_initial_approval_parts_and_stable_identity(self):
        a = "APROVACIO INICIAL PROJECT_URB PLA D'ACCESSIBILITAT DE LA BISBAL_PART_"
        rows = Adapter.parse_projects(inventory(a + '1', a + '2'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fase'], 'aprobación inicial')
        self.assertEqual(rows[0]['id'], Adapter.parse_projects(inventory(a + '2'))[0]['id'])

    def test_no_navigation_forms_or_login_records(self):
        for html in ('<h1>Login</h1>', inventory(), inventory('SOL·LICITUD LLICÈNCIA'),
                     inventory('Anunci de licitació')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_and_unexpected_document_host_fail(self):
        html = inventory('PROJECTE DE REURBANITZACIÓ DEL CARRER NOU_PART 1')
        for changed in (html + '<a rel="next" href="?page=2">2</a>',
                        html + '<div class="pagination">2</div>',
                        html.replace('/wp-content/', 'https://example.org/wp-content/')):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                Adapter.parse_projects(changed)


if __name__ == '__main__':
    unittest.main()
