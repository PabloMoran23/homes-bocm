"""Offline structural and completeness tests; no fixture depends on local evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from municipio.adapters.nules import (
    HOST, PARENT, SOURCE, NulesAyuntamientoAdapter, parse_inventory, project_record,
)
from municipio.manifest import load_manifest, load_yaml


def document(key, title, description=''):
    return (f'<a class="gIconLink" href="https://{HOST}/preview-document/{key}" '
            f'title="{description}">{title}</a>')


def folder(title, count):
    return (f'<a class="gIconLink exp" href="#" '
            f'''onclick="wicketAjaxGet('../../?x=folder-action',null)">{title}'''
            f'<span class="linkExtraInfo"> ( {count} )</span></a>')


def table(body):
    return f'<table class="TransparencyListPanel"><tr><td>{body}</td></tr></table>'


DOC1 = 'f9421be0-412c-42e2-9fce-7a720be32266'
DOC2 = 'c0fc7f26-c071-4abf-91f9-c0e6c288abb8'
DOC3 = 'a0e0fc5b-312a-410a-855f-4b432fb7d360'
FOLDER = f'https://{HOST}/transparency/d937eb2b-d6d8-4e34-8dc3-7cf3bbc70b4f/'


class NulesTests(unittest.TestCase):
    def fake_adapter(self, child_count=2):
        adapter = NulesAyuntamientoAdapter()
        parent = table(folder('7.4. OBRES PÚBLIQUES', 3)) + '<a>Veure\'n més</a>'
        inventory = table(folder('7.4.2. PROYECTO Santa Natalia', child_count) +
                          document(DOC1, '01 Projecte Cámara Agraria',
                                   'Proyecto remodelación Cámara Agraria'))
        children = table(document(DOC2, 'DECRETO 2016-1526 aprobación proyecto') +
                         document(DOC3, 'Proyecto remodelacion calle Santa Natalia'))
        pages = {PARENT: parent, SOURCE: inventory, FOLDER: children}
        adapter._get = Mock(side_effect=lambda url: Mock(text=pages[url], url=url))
        adapter._folder_url = Mock(side_effect=[SOURCE, FOLDER])
        return adapter

    def test_grouping_provenance_and_no_invented_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            result = self.fake_adapter().backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['documents'], 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertIn('DECRETO 2016-1526', rows[0]['documentos'][0]['title'])
        self.assertEqual(rows[0]['url'], FOLDER)
        self.assertNotIn(rows[1]['documentos'][0]['url'],
                         [d['url'] for d in rows[0]['documentos']])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '12082')
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion',
                          'lat', 'lon', 'geometry', 'fase'):
                self.assertNotIn(field, row)

    def test_count_mismatch_does_not_write_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            with self.assertRaisesRegex(ValueError, 'Incomplete project'):
                self.fake_adapter(child_count=3).backfill_proyectos(path)
            self.assertFalse(path.exists())

    def test_pending_pagination_is_explicit_error(self):
        html = table(document(DOC1, 'Proyecto')) + "<a>Veure'n més</a>"
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(html, SOURCE)

    def test_missing_markup_and_external_links_fail(self):
        for html in ('<html>Login</html>', table(''),
                     table('<a class="gIconLink" href="https://example.org/x">Proyecto</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)

    def test_generic_forms_are_not_projects(self):
        with self.assertRaises(ValueError):
            project_record('Solicitud licencia de obra', SOURCE, [{'url': SOURCE}])

    def test_stable_identity(self):
        doc = [{'title': 'Proyecto', 'url': SOURCE}]
        self.assertEqual(project_record('Proyecto original', FOLDER, doc)['id'],
                         project_record('Proyecto corregido', FOLDER, doc)['id'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('nules')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('12082', 'Castellón'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertTrue(NulesAyuntamientoAdapter().backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
