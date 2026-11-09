import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.l_aldea import LAldeaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(extra='', mobility=True):
    return '''<div class="journal-content-article"><ul>
    <li><a href="http://www.seu-e.cat/documents/28831/1/NNSS/norms-id">Text refós de les Normes Subsidiàries de Planejament al terme de L'Aldea</a></li>
    <li><a href="http://www.seu-e.cat/documents/28831/2/map.pdf/map-id">Mapa de Planejament de L'Aldea.</a></li>
    <li><a href="http://dtes.gencat.cat/muc-visor/">Enllaç al Mapa Urbanístic de Catalunya</a></li>''' + ('''
    <li><a href="https://www.seu-e.cat/documents/28831/3/emus.pdf/study-id">Estudi de Mobilitat Urbana Sostenible</a></li>''' if mobility else '') + extra + '</ul></div><p>Actualització: 28/09/2023</p>'


class LAldeaTests(unittest.TestCase):
    def test_grouping_provenance_and_unknown_dates(self):
        rows = LAldeaAyuntamientoAdapter.parse_projects(inventory())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '43904')
            for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[key])
            self.assertFalse(row['publication_ready'])
            self.assertTrue(row['url_documento'].startswith('https://seu-e.cat/documents/28831/'))

    def test_stable_identity_without_optional_study(self):
        self.assertEqual(LAldeaAyuntamientoAdapter.parse_projects(inventory())[0]['id'],
                         LAldeaAyuntamientoAdapter.parse_projects(inventory(mobility=False))[0]['id'])

    def test_fail_closed(self):
        for html in ['<p>Login</p>', inventory().replace('Mapa de Planejament', 'Formulari'),
                     inventory('<a href="?page=1">Següent</a>'),
                     inventory('<a href="/documents/28831/4/new.pdf">Nou pla</a>'),
                     inventory().replace('/documents/28831/2', '/documents/999/2'),
                     inventory() + inventory()]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                LAldeaAyuntamientoAdapter.parse_projects(html)

    def test_live_contract_and_failed_document_preserve_output(self):
        manifest = load_manifest('l-aldea')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, LAldeaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url, limit: inventory().encode() if url == SOURCE else b'%PDF-1.7\nfixture'):
                result = adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 2)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertTrue(rows[0]['documentos'][0]['sha256'])
            saved = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'<html>Login</html>']):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_bytes(), saved)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'lic.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
