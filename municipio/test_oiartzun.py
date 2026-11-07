import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.oiartzun import (GENERAL, MODIFICATIONS, OiartzunAyuntamientoAdapter,
                                        parse_detail, parse_inventory)


def inventory(source, titles, next_page=''):
    rows = ''.join(f'<tr><td>2026-02-17</td><td><a href="{source}/{slug}">{title}</a></td><td>Batzordea</td></tr>' for slug, title in titles)
    return f'<table class="table"><tbody>{rows}</tbody></table>' + (f'<a rel="next" href="{next_page}">»</a>' if next_page else '')


def detail(text, filename):
    return f'''<div class="container content"><h2>Instrument</h2>
    <div class="col-md-8"><p>{text}</p></div>
    <a href="/fitxategiak/erab_2/{filename}">{filename}</a></div>
    <footer><a href="/fitxategiak/erab_2/ENS.pdf">Unrelated certificate</a></footer>'''


class OiartzunTests(unittest.TestCase):
    def test_dates_are_separate_and_footer_is_excluded(self):
        text = ('Oiartzungo Udalak, 2026ko urtarrilaren 28an egindako bilkuran, '
                'HAPOaren 3. Aldaketari hasierako onarpena ematea erabaki zuen. '
                'Boletinean argitaratua: GAO 2026-02-19')
        row = parse_detail(detail(text, 'plan.pdf'), MODIFICATIONS + '/third')
        self.assertEqual(row['fecha_acuerdo'], '2026-01-28')
        self.assertEqual(row['fecha_publicacion'], '2026-02-19')
        self.assertEqual(row['fase'], 'aprobacion_inicial')
        self.assertEqual(len(row['documentos']), 1)
        unknown = parse_detail(detail('2015-03-25 dokumentua', 'a.pdf'), GENERAL + '/a')
        self.assertIsNone(unknown['fecha_acuerdo'])
        self.assertIsNone(unknown['fecha_publicacion'])

    def test_all_pages_group_chapters_and_keep_provenance(self):
        fixtures = {
            GENERAL: inventory(GENERAL, [('approval', 'Hirigintza Antolatzeko Plan Orokorra - Onarpena')], GENERAL + '?page=2'),
            GENERAL + '?page=2': inventory(GENERAL, [('chapter', 'Hirigintza Antolatzeko Plan Orokorra - 1. DOKUMENTUA')]),
            MODIFICATIONS: inventory(MODIFICATIONS, [('third', 'HAPO-aren 3. aldaketa puntuala')]),
            GENERAL + '/approval': detail('2015eko martxoaren 25eko osoko bilkuran onartutako plana', 'approval.pdf'),
            GENERAL + '/chapter': detail('Memoria', 'memoria.pdf'),
            MODIFICATIONS + '/third': detail('Testua', 'third.pdf'),
        }
        adapter = OiartzunAyuntamientoAdapter('oiartzun')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=fixtures.__getitem__) as fetch:
            path = Path(folder) / 'projects.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(fetch.call_count, 6)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[0]['fecha_acuerdo'], '2015-03-25')
            self.assertIsNone(rows[0]['fecha_publicacion'])
            self.assertEqual(rows[0]['fichas_fuente'][0]['fecha_listado'], '2026-02-17')
            self.assertIn(GENERAL + '?page=2', result['source_urls'])

    def test_officially_linked_external_document_is_retained(self):
        html = detail('Informe', 'a.pdf').replace('/fitxategiak/erab_2/a.pdf', 'https://drive.google.com/file/d/public-file/view?usp=sharing')
        row = parse_detail(html, GENERAL + '/chapter')
        self.assertEqual(row['documentos'][0]['url_procedencia'], GENERAL + '/chapter')
        self.assertIn('drive.google.com/file/d/public-file', row['documentos'][0]['url'])

    def test_source_drift_and_unrecognized_pagination_fail(self):
        for html in ('<html>Login</html>', '<table class="table"><tbody></tbody></table>',
                     inventory(GENERAL, [('a', 'Plan')], GENERAL + '?offset=12')):
            with self.assertRaises(ValueError):
                parse_inventory(html, GENERAL)
        with self.assertRaises(ValueError):
            parse_detail('<div class="container content"><h2>Form</h2><div class="col-md-8">Apply</div></div>', GENERAL)

    def test_failure_does_not_overwrite_previous_snapshot(self):
        adapter = OiartzunAyuntamientoAdapter('oiartzun')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', return_value='<html>Unavailable</html>'):
            path = Path(folder) / 'projects.jsonl'
            path.write_text('previous snapshot\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
