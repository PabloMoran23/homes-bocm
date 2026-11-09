"""Offline parser and snapshot safety tests; no live website dependency."""
import unittest
from municipio.adapters.mino import MinoAyuntamientoAdapter as Adapter


def fixture(rows=None, count=1):
    rows = rows or '<tr><td>2025</td><td>Pavimentación da Rúa Real</td><td>186.810,84 €</td><td>180.000,00 €</td></tr>'
    return f'''<h1>PLAN ÚNICO Miño</h1>
    <select id="selector-exercicio"><option value="todos" selected>Todos</option></select>
    <li><span>Obras aprobadas</span><div>{count}</div></li>
    <table aria-label="Lista de obras e investimentos"><thead><tr>
    <th>Exercicio</th><th>Obxecto</th><th>Orzamento</th><th>Aportación</th>
    </tr></thead><tbody>{rows}</tbody></table>'''


class MinoTests(unittest.TestCase):
    def test_semantics_and_stable_identity(self):
        row = Adapter.parse_projects(fixture())[0]
        self.assertEqual(row['presupuesto_eur'], '186810.84')
        self.assertEqual(row['ejercicio'], 2025)
        self.assertEqual(row['codigo_ine'], '15048')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        changed = Adapter.parse_projects(fixture().replace('186.810,84', '190.000,00'))[0]
        self.assertEqual(row['id'], changed['id'])

    def test_all_rows_and_documents_grouped(self):
        rows = '''<tr><td>2024</td><td>Parque <a href="/plano.pdf">Plano</a>
        <a href="/memoria.pdf">Memoria</a></td><td>1.000,00 €</td><td>900,00 €</td></tr>
        <tr><td>2023</td><td>Saneamento</td><td>2.000,00 €</td><td>2.000,00 €</td></tr>'''
        parsed = Adapter.parse_projects(fixture(rows, 2))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(len(parsed[0]['documentos']), 2)
        self.assertEqual(parsed[0]['documentos'][0]['url'], 'https://plan-unico.dacoruna.gal/plano.pdf')

    def test_fail_closed(self):
        base = fixture()
        bad = [fixture(count=2), base.replace('Miño', 'Outro'),
               base.replace('value="todos"', 'value="2025"'),
               base + '<a href="?page=2" rel="next">Seguinte</a>',
               base.replace('186.810,84', 'invalid'), base.replace('Obxecto', 'New column'),
               '<h1>Formulario de licencia</h1>',
               fixture('<tr><td>2025</td><td>Obra</td><td>1,00 €</td><td>1,00 €</td></tr>' * 2, 2)]
        for html in bad:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)


if __name__ == '__main__':
    unittest.main()
