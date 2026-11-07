import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

from municipio.adapters.castellbisbal import parse_projects, CastellbisbalAyuntamientoAdapter


def row(title='Modificació puntual número 2 del POUM', date='24-01-2019', doc='document2'):
    return (f'<tr><td>{title}</td><td>{date}</td><td></td>'
            f'<td><a href="/documents/3157329/{doc}">Document</a></td><td></td>')


def page(rows, extra=''):
    return ("<h1><span>Normativa d'urbanisme</span><!-- heading --></h1><table id='inventory'><thead><tr>"
            '<th>Normativa</th><th>Data de publicació</th><th>Enllaç</th>'
            '<th>Documents</th><th>Més informació</th></tr></thead><tbody>'
            + rows + '</tbody></table>' + extra)


class ParserTests(unittest.TestCase):
    def test_nested_rows_group_languages_and_preserve_dates(self):
        rows = parse_projects(page(row() + row('Versió en castellà. Modificació puntual número 2 del POUM', doc='es')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_publicacion'], '2019-01-24')
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fecha_acuerdo'])
        self.assertIsNone(rows[0]['geometry'])
        self.assertEqual(rows[0]['documentos'][1]['idioma'], 'es')

    def test_base_plan_and_resolutions_are_one_instrument(self):
        rows = parse_projects(page(row("Pla d'Ordenació Urbanística Municipal (POUM)", '30-04-2008') +
                                   row('Resolució sobre el POUM de febrer de 2009', '11-02-2009', 'resolution')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'castellbisbal-poum')
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertEqual(rows[0]['documentos'][1]['fecha_publicacion'], '2009-02-11')

    def test_missing_date_stays_null(self):
        self.assertIsNone(parse_projects(page(row(date='')))[0]['fecha_publicacion'])

    def test_stable_identity_and_separate_amendments(self):
        first = parse_projects(page(row() + row('Modificació puntual número 3 del POUM')))
        second = parse_projects(page(row('Modificació puntual número 3 del POUM') + row()))
        self.assertEqual([r['id'] for r in first], [r['id'] for r in second])
        self.assertEqual(len(first), 2)

    def test_invalid_sources_fail_closed(self):
        for html in ['<h1>Login</h1>', page(''), page(row('Llicència urbanística')),
                     page(row().replace('<a href="/documents/3157329/document2">Document</a>', '')),
                     page(row(date='31-02-2022')), page(row().replace('/documents/', 'https://example.com/documents/'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_new_pagination_fails(self):
        for extra in ['<a rel="next" href="?page=2">Següent</a>',
                      '<div class="pagination"><a href="?page=2">2</a></div>',
                      '<script>$("#inventory").DataTable({serverSide:true,ajax:"/api"});</script>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_projects(page(row(), extra))

    def test_does_not_truncate_large_inline_table(self):
        rows = parse_projects(page(''.join(row(f'Modificació puntual número {n} del POUM', doc=str(n)) for n in range(1, 31))))
        self.assertEqual(len(rows), 30)

    def test_update_refreshes_and_licences_disabled(self):
        adapter = CastellbisbalAyuntamientoAdapter('castellbisbal')
        with TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 8}) as fetch:
                self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state.json')['rows'], 8)
                fetch.assert_called_once_with(out)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
