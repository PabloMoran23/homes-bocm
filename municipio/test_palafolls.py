import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.palafolls import PalafollsAyuntamientoAdapter, SOURCE, TITLE, parse_projects
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def row(title, date='', url='https://seu-e.cat/documents/14304757/1/plan.pdf/id', info=''):
    # Deliberately omit closing tr, as in the live source.
    return f'<tr><td>{title}</td><td>{date}</td><td><a href="{url}">link</a></td><td></td><td>{info}</td>'


def page(rows):
    return ('<table><thead><tr><th>Normativa</th><th>Data de publicació</th></tr></thead>'
            '<tbody>' + rows + '</tbody></table>')


class PalafollsTests(unittest.TestCase):
    def test_grouping_dates_history_and_no_geometry(self):
        html = page(row(TITLE + ' (VOL. 1)', '19-09-2006') +
                    row(TITLE + ' Refós', '31-12-2005', 'https://seu-e.cat/documents/14304757/1/no-vigent.pdf/id') +
                    row('Plànols normatius de la revisió del pla general', '19-09-2006',
                        'https://www.palafolls.cat/old-plan',
                        "aprovat d'ofici segons acord de la comissió territorial d'urbanisme de Barcelona del 27 d´abril del 2006. Publicació al DOGC de 19/9/2006."))
        records = parse_projects(html)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['fecha_publicacion'], '2006-09-19')
        self.assertEqual(record['fecha_acuerdo'], '2006-04-27')
        self.assertIsNone(record['fecha_aprob'])
        self.assertEqual(sum(d['historico'] for d in record['documentos']), 1)
        self.assertEqual(len(record['documentos']), 3)
        self.assertIsNone(record['lat'])
        self.assertFalse(record['publication_ready'])

    def test_all_rows_beyond_browser_first_page_and_exclusions(self):
        html = page(''.join(row('Decret regional ' + str(i)) for i in range(15)) +
                    row('Llicència: formulari de sol·licitud') +
                    row(TITLE + ' (VOL. 1)', '19-09-2006'))
        record = parse_projects(html)[0]
        self.assertEqual(len(record['documentos']), 1)
        self.assertIsNone(record['fecha_acuerdo'])

    def test_navigation_forms_and_missing_table_rejected(self):
        for html in ('<a>Planejament</a>', page(row('Llicència obres'))):
            with self.assertRaises(ValueError):
                parse_projects(html)

    def test_pagination_and_remote_loading_rejected(self):
        valid = page(row(TITLE + ' (VOL. 1)'))
        for suffix in ('<a rel="next" href="?page=2">2</a>',
                       '<script>{"serverSide": true}</script>',
                       '<script>{ajax: "/api/rows"}</script>'):
            with self.assertRaises(ValueError):
                parse_projects(valid + suffix)

    def test_bad_dates_and_document_provenance_rejected(self):
        for html in (page(row(TITLE + ' (VOL. 1)', '31-02-2006')),
                     page(row(TITLE + ' (VOL. 1)', url='https://example.org/a.pdf')),
                     page(row(TITLE + ' (VOL. 1)', url='https://seu-e.cat/documents/999/a.pdf'))):
            with self.assertRaises(ValueError):
                parse_projects(html)

    def test_duplicate_documents_do_not_duplicate_instrument(self):
        r = row(TITLE + ' (VOL. 1)', '19-09-2006')
        self.assertEqual(len(parse_projects(page(r + r))[0]['documentos']), 1)

    def test_live_method_writes_snapshot_and_disabled_licences(self):
        body = page(row(TITLE + ' (VOL. 1)', '19-09-2006')).encode()
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.palafolls.requests.get') as get:
            response = get.return_value.__enter__.return_value
            response.url = SOURCE
            response.headers = {'Content-Type': 'text/html'}
            response.iter_content.return_value = [body]
            adapter = PalafollsAyuntamientoAdapter(config={'capture_dir': tmp})
            output = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(output, Path(tmp) / 'state')['rows'], 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '08155')
            self.assertTrue((Path(tmp) / 'normativa-live.html').exists())
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest_loads_without_registry_changes(self):
        manifest = load_manifest('palafolls')
        self.assertIsInstance(load_portal_adapter(manifest), PalafollsAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
