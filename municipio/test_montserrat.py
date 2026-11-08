"""Offline contract tests; fixtures model GVA's observed directory markup."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

from municipio.adapters.montserrat import (
    SOURCE, MontserratAyuntamientoAdapter, collect_projects, parse_directory,
)
from municipio.manifest import load_manifest, load_yaml


def listing(url, entries):
    links = ''.join('<tr><td class="indexcolname"><a href="' + href + '">' + title
                    + '</a></td></tr>' for href, title in entries)
    return ('<h1 id="indextitle">Index of ' + unquote(urlsplit(url).path).rstrip('/')
            + '</h1><table id="indexlist">' + links + '</table>')


def inventory():
    category = SOURCE + '1%20P.%20GENERAL/'
    dossier = category + '46172-1000%20PG%202015-0087/'
    folder = dossier + '1%20APROBACION/'
    return {
        SOURCE: listing(SOURCE, [('1%20P.%20GENERAL/', '1 P. GENERAL/')]),
        category: listing(category, [('46172-1000%20PG%202015-0087/', '46172-1000 PG 2015-0087/')]),
        dossier: listing(dossier, [('1%20APROBACION/', '1 APROBACION/'),
                                   ('INSCRIPCI%d3N.pdf', 'INSCRIPCIÓN.pdf')]),
        folder: listing(folder, [('ACUERDO.pdf', 'ACUERDO.pdf'), ('BOP.pdf', 'BOP.pdf'),
                                 ('ACUERDO.pdf', 'ACUERDO.pdf')]),
    }


class MontserratTests(unittest.TestCase):
    def test_group_documents_and_preserve_provenance(self):
        pages = inventory()
        rows, visited = collect_projects(pages.__getitem__)
        self.assertEqual(set(visited), set(pages))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['expediente'], '2015-0087')
        self.assertEqual(row['codigo_ine'], '46172')
        self.assertEqual(row['provincia'], 'Valencia')
        self.assertEqual(len(row['documentos']), 3)
        self.assertTrue(any('INSCRIPCI%d3N.pdf' in doc['url'] for doc in row['documentos']))
        self.assertTrue(all(doc['inventory_url'] in visited for doc in row['documentos']))
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob',
                      'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(collect_projects(pages.__getitem__)[0], rows)

    def test_all_instruments_are_traversed(self):
        pages = inventory()
        category = next(u for u in pages if u.endswith('GENERAL/'))
        other = category + '46172-1001%20PG%202020-0001/'
        pages[category] = listing(category, [
            ('46172-1000%20PG%202015-0087/', '46172-1000 PG 2015-0087/'),
            ('46172-1001%20PG%202020-0001/', '46172-1001 PG 2020-0001/'),
        ])
        pages[other] = listing(other, [('MEMORIA.pdf', 'MEMORIA.pdf')])
        rows, visited = collect_projects(pages.__getitem__)
        self.assertEqual(len(rows), 2)
        self.assertIn(other, visited)
        self.assertEqual(len({row['id'] for row in rows}), 2)

    def test_reject_login_navigation_and_wrong_municipality(self):
        for html in ('<h1>Login</h1>', '<a href="PGOU.pdf">PGOU</a>',
                     listing(SOURCE.replace('46172', '46173'), [('a.pdf', 'a.pdf')])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_directory(html, SOURCE)

    def test_reject_pagination_and_unsafe_links(self):
        for html in (listing(SOURCE, [('a.pdf', 'a.pdf')]) + '<a rel="next" href="?page=2">Next</a>',
                     listing(SOURCE, [('https://example.org/a.pdf', 'a.pdf')]),
                     listing(SOURCE, [('%2e%2e/elsewhere/', 'elsewhere')])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_directory(html, SOURCE)

    def test_unknown_categories_and_empty_directories_fail(self):
        for entries in ([], [('2%20OTROS/', '2 OTROS/')]):
            pages = {SOURCE: listing(SOURCE, entries)}
            with self.assertRaises(ValueError):
                collect_projects(pages.__getitem__)

    def test_network_failure_preserves_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            with patch('municipio.adapters.montserrat.requests.Session.get', side_effect=RuntimeError('network failure')):
                with self.assertRaises(RuntimeError):
                    MontserratAyuntamientoAdapter().backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('montserrat')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46172')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = MontserratAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result['count'], 0)
            self.assertEqual(output.read_text(), '')

    def test_reject_other_ine(self):
        with self.assertRaises(ValueError):
            MontserratAyuntamientoAdapter(config={'ine_code': '08127'})


if __name__ == '__main__':
    unittest.main()
