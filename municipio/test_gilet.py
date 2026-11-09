import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from municipio.adapters.gilet import SOURCE, GiletAyuntamientoAdapter, decode_path, parse_index
from municipio.manifest import load_manifest
from municipio.entity_policy import classify


def index(url, *links):
    heading = 'Index of ' + decode_path(urlsplit(url).path).rstrip('/')
    entries = ''.join(f'<tr><td class="indexcolname"><a href="{h}">{h}</a></td></tr>' for h in links)
    return f'<h1 id="indextitle">{heading}</h1><table id="indexlist">{entries}</table>'


def fixture():
    category = SOURCE + '1%20P.%20GENERAL/'
    plan = category + '46134-1102%20PGMOD%20n%ba4/'
    section = plan + '1%20APROBACI%d3N/'
    pages = {
        SOURCE: index(SOURCE, '1%20P.%20GENERAL/'),
        category: index(category, '46134-1102%20PGMOD%20n%ba4/'),
        plan: index(plan, '1%20APROBACI%d3N/', 'registro.pdf'),
        section: index(section, '../', 'acuerdo.pdf', 'bop.PDF', 'bop.PDF'),
    }
    return pages, plan, section


class GiletTests(unittest.TestCase):
    def test_groups_all_documents_and_retains_provenance(self):
        pages, plan, section = fixture()
        rows, visited = GiletAyuntamientoAdapter.collect(pages.__getitem__)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['registro_id'], '46134-1102')
        self.assertEqual(row['expediente_grupo'], row['registro_id'])
        self.assertEqual(classify(row)['entity_type'], 'expediente')
        self.assertEqual(row['titulo'], 'PGMOD nº4')
        self.assertEqual(row['url'], plan)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(len(visited), 4)
        self.assertEqual(row['documentos'][0]['url_indice'], section)
        self.assertEqual(row['documentos'][0]['seccion'], '1 APROBACIÓN')
        for name in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(row[name])
        self.assertFalse(row['publication_ready'])

    def test_encoding_preserves_archive_urls(self):
        self.assertEqual(decode_path('n%ba4/APROBACI%d3N'), 'nº4/APROBACIÓN')
        self.assertEqual(decode_path('APROBACI%C3%93N'), 'APROBACIÓN')
        pages, _, section = fixture()
        links = parse_index(pages[section], section)
        self.assertEqual(links[0][0], section + 'acuerdo.pdf')

    def test_rejects_login_wrong_municipality_and_navigation(self):
        for html in ['<h1>Login</h1>', index(SOURCE.replace('46134', '46135'))]:
            with self.assertRaises(ValueError):
                parse_index(html, SOURCE)
        with self.assertRaises(ValueError):
            GiletAyuntamientoAdapter.collect(lambda u: index(u))

    def test_rejects_pagination_unsafe_links_and_unknown_files(self):
        for href in ['https://example.com/file.pdf', '../46135/file.pdf', '%2e%2e/file.pdf', 'files.zip', '?page=2']:
            with self.subTest(href=href), self.assertRaises(ValueError):
                parse_index(index(SOURCE, href), SOURCE)
        with self.assertRaises(ValueError):
            parse_index(index(SOURCE) + '<a href="?page=2" rel="next">more</a>', SOURCE)

    def test_multiple_instruments_not_multiple_documents(self):
        pages, plan, _ = fixture()
        category = SOURCE + '1%20P.%20GENERAL/'
        other = category + '46134-1000%20HOMOLOGACION/'
        pages[category] = index(category, plan, other)
        pages[other] = index(other, 'memoria.pdf')
        rows, _ = GiletAyuntamientoAdapter.collect(pages.__getitem__)
        self.assertEqual([r['registro_id'] for r in rows], ['46134-1000', '46134-1102'])

    def test_missing_document_and_fetch_failure_are_errors(self):
        pages, plan, section = fixture()
        pages[plan] = index(plan)
        with self.assertRaises(ValueError):
            GiletAyuntamientoAdapter.collect(pages.__getitem__)
        pages, _, section = fixture()
        del pages[section]
        with self.assertRaises(KeyError):
            GiletAyuntamientoAdapter.collect(pages.__getitem__)

    def test_snapshot_update_and_disabled_licences(self):
        adapter = GiletAyuntamientoAdapter('gilet')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 2})
            backfill.assert_called_once_with(Path('out'))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest_loads_correct_adapter_and_flags(self):
        manifest = load_manifest('gilet')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertEqual(manifest.portal.config['ine_code'], '46134')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.gilet:GiletAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
