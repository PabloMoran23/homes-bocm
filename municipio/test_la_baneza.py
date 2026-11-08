"""Offline parser and fail-closed adapter tests; no network required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.la_baneza import LaBanezaAyuntamientoAdapter, parse_projects
from municipio.manifest import load_manifest

CURRENT = '''<h2>7.3. NORMATIVA URBANÍSTICA</h2>
<table class="TransparencyListPanel"><tr><td><a href="/preview-document/0d59955b-b395-4a91-a6d7-d68a94527490">Plan General de Ordenacion Urbana</a></td></tr></table>'''
ARCHIVE = '''<div class="paragraph_block">
<p>Plan General de Ordenación Urbana de La Bañeza (León).
Acuerdos de 28 de noviembre de 2013 y de 30 de enero de 2014.</p>
<a href="http://bocyl.jcyl.es/boletines/2014/02/12/pdf/BOCYL-D-12022014-45.pdf">B.O.C.Y.L. 29 - 12/02/2014</a>
<p>Anuncio aprobación definitiva.</p>
<a href="http://bocyl.jcyl.es/boletines/2016/03/08/pdf/BOCYL-D-08032016-8.pdf">B.O.C.Y.L. 46 - 08/03/2016</a>
<a href="https://drive.google.com/open?id=example">INFORMACIÓN P.G.O.U.</a>
</div>'''


class LaBanezaTests(unittest.TestCase):
    def test_one_instrument_with_all_documents_and_separate_dates(self):
        rows = parse_projects(CURRENT, ARCHIVE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '24010')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual([d['fecha_publicacion'] for d in row['documentos']],
                         [None, '2014-02-12', '2016-03-08', None])
        self.assertTrue(row['documentos'][1]['url'].startswith('https://bocyl.jcyl.es/'))
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertFalse(row['publication_ready'])

    def test_navigation_forms_and_login_are_not_projects(self):
        for bad in ('<a href="/dossier">Licencia de Obra Mayor</a>',
                    '<h1>Identifícate</h1>', '<a>Plan General de Ordenacion Urbana</a>'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_projects(bad, ARCHIVE)
        with self.assertRaises(ValueError):
            parse_projects(CURRENT, '<a>Licencia urbanística</a>')

    def test_pagination_and_unreviewed_inventory_changes_fail(self):
        for suffix in ('<a href="?page=2" rel="next">2</a>',
                       '<a onclick="load()">Siguiente</a>', '<div class="pagination">1 2</div>'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                parse_projects(CURRENT + suffix, ARCHIVE)
        extra = CURRENT.replace('</table>', '<tr><td><a href="/another">Otro plan</a></td></tr></table>')
        with self.assertRaises(ValueError):
            parse_projects(extra, ARCHIVE)

    def test_document_provenance_and_missing_date(self):
        with self.assertRaises(ValueError):
            parse_projects(CURRENT.replace('href="/preview-document/', 'href="https://example.org/preview-document/'), ARCHIVE)
        with self.assertRaises(ValueError):
            parse_projects(CURRENT, ARCHIVE.replace('12/02/2014', 'fecha no disponible'))
        row = parse_projects(CURRENT, ARCHIVE.replace('Anuncio aprobación definitiva.', 'Información del plan.'))[0]
        self.assertIsNone(row['fase'])

    def test_full_refresh_and_failed_fetch_preserve_previous_output(self):
        adapter = LaBanezaAyuntamientoAdapter('la-baneza')
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[CURRENT, ARCHIVE,
                              'Plan General de Ordenacion Urbana. Información del documento. PDF']):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            original = path.read_text()
            self.assertEqual(json.loads(original)['id'], 'la-baneza-pgou')
            with patch.object(adapter, '_fetch', return_value='<h1>Login</h1>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), original)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('la-baneza')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'León')
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = LaBanezaAyuntamientoAdapter('la-baneza').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
