import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.l_arboc import LArbocAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def section(label, day='24-02-2016', doc='Normativa.pdf/id'):
    return (f'<tr><td>{label}</td><td>{day}</td><td></td><td>'
            f'<a href="/documents/8061681/8642920/{doc}">{doc}</a></td><td></td>')


def inventory(rows, script=''):
    return ('<div><table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in
            ['Normativa', 'Data de publicació', 'Enllaç', 'Documents', 'Més informació'])
            + '</tr></thead><tbody>' + rows + '</tr></tbody></table>' + script + '</div>')


class LArbocTests(unittest.TestCase):
    def test_group_malformed_nested_rows_and_deduplicate_documents(self):
        rows = parse_inventory(inventory(section('POUM - Normativa') + section('POUM - Annexos')
                                        + section('Mapa de Capacitat Acústica')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(len(rows[0]['secciones']), 2)
        self.assertEqual(rows[0]['fecha_publicacion'], '2016-02-24')
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['geometry'])

    def test_distinct_section_dates_and_missing_dates(self):
        row = parse_inventory(inventory(section('POUM - Normativa') + section('POUM - Annexos', '')))[0]
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['secciones'][0]['fecha_publicacion'], '2016-02-24')
        self.assertIsNone(row['fecha_acuerdo'])

    def test_reject_navigation_forms_or_undocumented_instrument(self):
        for html in ['<a>POUM</a>', inventory(section('Sol·licitud de llicència')),
                     inventory(section('POUM - Normativa').replace('<a href=', '<span data=').replace('</a>', '</span>'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_foreign_document_or_source(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory(section('POUM - Normativa')).replace('/documents/8061681/', 'https://example.org/'))
        with self.assertRaises(ValueError):
            parse_inventory(inventory(section('POUM - Normativa')), 'https://example.org')

    def test_no_row_limit_and_stable_identity(self):
        small = parse_inventory(inventory(section('POUM - Normativa')))[0]
        large = parse_inventory(inventory(section('POUM - Normativa') + ''.join(
            section('POUM - Annexos', doc=f'annex-{n}') for n in range(45))))[0]
        self.assertEqual(len(large['documentos']), 46)
        self.assertEqual(small['id'], large['id'])

    def test_refuse_unverified_pagination(self):
        for script in ['<script>x={serverSide: true}</script>', '<script>x={"ajax": "/data"}</script>',
                       '<a rel="next" href="?page=2">Next</a>']:
            with self.subTest(script=script), self.assertRaises(ValueError):
                parse_inventory(inventory(section('POUM - Normativa'), script))

    def test_do_not_merge_a_new_modification_into_base_plan(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory(section('POUM - Normativa') + section('POUM - Modificació 1')))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('l-arboc')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, LArbocAyuntamientoAdapter)
        self.assertEqual(manifest.provincia, 'Tarragona')
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.l_arboc.requests.get') as get:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')
            get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
