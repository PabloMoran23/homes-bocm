"""Offline parser and traversal regressions; no live network in unit tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.cajar import (
    CajarAyuntamientoAdapter, WORKS, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest

FOLDER = 'https://cajar.sedelectronica.es/transparency/daeb6707-9c68-4492-98c7-9560f2f1c768/'
PROJECT = 'https://cajar.sedelectronica.es/preview-document/30c18b1d-daa1-4a00-9b2a-a8b14cd655bc'


def table(body):
    return '<table><tr><td class="class_name">' + body + '</td></tr></table>'


def doc(title, url=PROJECT):
    return f'<a class="gIconLink" href="{url}">{title}</a>'


def folder(count=2):
    return table('<a class="gIconLink exp" href="#" '
                 'onclick="wicketAjaxGet(\'?x=test\',null)">'
                 f'EXPROPIACION FORZOSA AVDA. DE HUÉTOR<span class="linkExtraInfo"> ( {count} )</span></a>')


HTML = table(doc('PROYECTO ACERADO AVDA. HUETOR VEGA') + doc(
    'Cdo acuerdo de pleno', PROJECT.replace('30c18b1d', 'a86ca74e')))


class CajarTests(unittest.TestCase):
    def test_group_documents_and_preserve_provenance(self):
        row = parse_project(HTML, FOLDER)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['url_documento'], PROJECT)
        self.assertEqual(row['url'], FOLDER)
        self.assertEqual(row['codigo_ine'], '18036')
        self.assertEqual(row['id'], parse_project(HTML, FOLDER)['id'])

    def test_no_invented_dates_geometry_or_phase(self):
        row = parse_project(HTML + '<p>Fecha de creación 12-ago-2026</p>', FOLDER)
        for key in ['fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])

    def test_forms_announcements_and_unrelated_news_excluded(self):
        for title in ['Solicitud de licencia de obras', 'Anuncio de licitación',
                      'Fiestas municipales', 'BOP Nº 156 de 14-08-26']:
            self.assertIsNone(parse_project(table(doc(title)), FOLDER))

    def test_missing_inventory_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory('<h1>Identifícate</h1>')

    def test_ambiguous_projects_rejected(self):
        with self.assertRaises(ValueError):
            parse_project(HTML + table(doc('PROYECTO OTRO')), FOLDER)

    def test_foreign_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_project(table(doc('PROYECTO', 'https://example.org/file.pdf')), FOLDER)

    def test_pagination_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            parse_inventory(HTML + '<a href="?page=2" rel="next">Siguiente</a>')

    def test_folder_count_and_action(self):
        entry = parse_inventory(folder())[0]
        self.assertEqual(entry['count'], 2)
        self.assertEqual(entry['action'], '?x=test')
        self.assertEqual(entry['title'], 'EXPROPIACION FORZOSA AVDA. DE HUÉTOR')

    def test_manifest_safety_and_identity(self):
        m = load_manifest('cajar')
        self.assertEqual((m.nombre, m.provincia), ('Cájar', 'Granada'))
        self.assertFalse(m.licencias.enabled)

    def run_snapshot(self, count):
        def response(url, text='', headers=None):
            r = Mock(url=url, text=text, headers=headers or {'Content-Type': 'text/html'})
            return r
        session = Mock()
        session.headers = {}
        session.get.side_effect = [response(WORKS, folder(count)),
                                   response('https://cajar.sedelectronica.es/?x=test', headers={'Ajax-Location': FOLDER}),
                                   response(FOLDER, HTML)]
        context = Mock()
        context.__enter__ = Mock(return_value=session)
        context.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.cajar.requests.Session', return_value=context):
            output = Path(tmp) / 'projects.jsonl'
            result = CajarAyuntamientoAdapter().backfill_proyectos(output)
            self.assertEqual(result['live_records'], 1)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)

    def test_live_path_with_fake_session(self):
        self.run_snapshot(2)

    def test_count_mismatch_fails_before_writing(self):
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            self.run_snapshot(7)


if __name__ == '__main__':
    unittest.main()
