import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.llanca import (
    HOST, SOURCE, LlancaAyuntamientoAdapter, parse_inventory, project_record,
)
from municipio.manifest import load_manifest


def table(*entries):
    return '<table class="TransparencyListPanel">' + ''.join(
        '<tr><td class="class_name">' + e + '</td></tr>' for e in entries
    ) + '</table>'


def folder(title, count, key):
    return (f'<a class="gIconLink exp" onclick="wicketAjaxGet(\'../../?x={key}\')">'
            f'{title}<span class="linkExtraInfo"> ( {count} )</span></a>')


def document(key, title='Projecte tècnic'):
    return f'<a href="https://{HOST}/preview-document/{key}" title="Font municipal">{title}</a>'


class Response:
    def __init__(self, url, html='', location=None):
        self.url, self.encoding = url, 'utf-8'
        self.payload = html.encode()
        self.headers = {'Ajax-Location': location} if location else {}

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.payload

    def close(self):
        pass


class LlancaTests(unittest.TestCase):
    def test_group_documents_and_preserve_provenance_without_guessing_dates(self):
        docs = parse_inventory(table(document('a'), document('b', 'BOP_22.05.26 Aprov. def.')))['documentos']
        row = project_record('Exp. 2730/2026 Projecte asfaltat de diversos carrers', SOURCE, '2026', docs)
        self.assertEqual(row['expediente'], '2730/2026')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['descripcion'], 'Font municipal')
        for key in ['fecha', 'fecha_acuerdo', 'fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(row[key])
        self.assertEqual(row['id'], project_record('Exp. 2730/2026 Projecte canviat', SOURCE, '2026', docs)['id'])

    def test_reject_non_records_and_changed_inventory(self):
        for html in ['<h1>Identifica’t</h1>', table('<span>Unrecognised row</span>'),
                     table(document('x')) + '<a rel="next">2</a>',
                     table(document('x')) + '<a title="Següent" href="#">&gt;</a>',
                     table(document('x'), document('x')),
                     table('<a href="https://unrelated.example/preview-document/x">Projecte</a>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            project_record('Sol·licitud llicència obres majors', SOURCE, '2026', [{}])
        with self.assertRaises(ValueError):
            project_record('Expedient 1/2026 Sol·licitud amb projecte tècnic', SOURCE, '2026', [{}])
        with self.assertRaises(ValueError):
            project_record('Expedient 1/2026 Projecte', SOURCE, '2026', [])

    def _run_fake(self, destination, mismatch=False):
        year_url = f'https://{HOST}/transparency/year/'
        detail_url = f'https://{HOST}/transparency/project/'
        empty_url = f'https://{HOST}/transparency/empty/'
        pages = {
            SOURCE: table(folder('2026', 2, 'year')),
            year_url: table(folder('Expedient 1/2026 Projecte de construcció', 2, 'project'),
                            folder('Expedient 2/2026 Projecte buit', 0, 'empty')),
            detail_url: table(document('1'), *([] if mismatch else [document('2', 'Edicte BOP')])),
            empty_url: table(),
        }
        locations = {'year': year_url, 'project': detail_url, 'empty': empty_url}

        def fetch(session, url, **kwargs):
            if '?x=' in url:
                self.assertEqual(kwargs['headers']['Wicket-Ajax'], 'true')
                return Response(url, location=locations[url.split('?x=')[1]])
            return Response(url, pages[url])

        with patch('municipio.adapters.llanca.requests.Session.get', fetch):
            return LlancaAyuntamientoAdapter('llanca').backfill_proyectos(destination)

    def test_complete_traversal_groups_documents_and_reports_empty_folder(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'out.jsonl'
            result = self._run_fake(target)
            rows = [json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(result['source_urls']), 4)
            self.assertEqual(len(result['empty_folders']), 1)
            self.assertEqual(len(rows[0]['documentos']), 2)

    def test_count_mismatch_fails_without_replacing_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'out.jsonl'
            target.write_text('previous snapshot\n')
            with self.assertRaisesRegex(ValueError, 'count mismatch'):
                self._run_fake(target, mismatch=True)
            self.assertEqual(target.read_text(), 'previous snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('llanca')
        self.assertEqual(manifest.nombre, 'Llançà')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'licencias.jsonl'
            result = LlancaAyuntamientoAdapter('llanca').backfill_licencias(target)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
