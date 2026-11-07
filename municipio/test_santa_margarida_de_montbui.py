"""Offline contract tests using the source's reviewed HTML structure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_margarida_de_montbui import (
    MUNICIPAL_SOURCE, SOURCE, SantaMargaridaDeMontbuiAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


HTML = '''<article><div class="entry-content">
<p>Documents del POUM de Santa Margarida de Montbui.</p>
<p>ACTUALITZACIÓ (13 de gener de 2026):</p>
<p><a href="https://www.montbui.cat/form.docx">Sol·licitud</a></p>
<p>ACTUALITZACIÓ (12 de desembre de 2025):</p>
<p>Aprovació Inicial del Pla d’Ordenació Urbanística Municipal (POUM)
realitzada en Ple Ordinari el dijous 27 de novembre de 2025.</p>
<p><a href="http://www.montbui.cat/media/memoria.pdf">a) Memòria</a></p>
<p>Consulteu <a href="http://www.montbui.cat/media/\trepository/certificat.pdf">AQUÍ</a>
el certificat d’acord de Ple de data 27-11-2025.</p>
<p>Consulteu <a href="http://www.montbui.cat/bop.pdf">AQUÍ</a>
la publicació realitzada en el BOPB 12-12-2025</p>
<p>ACTUALITZACIÓ (4 de juliol de 2024):</p>
<p><a href="http://www.montbui.cat/avanc.pdf">Memòria Avanç</a></p>
</div></article>'''


class SantaMargaridaDeMontbuiTests(unittest.TestCase):
    def test_one_instrument_all_stages_distinct_dates(self):
        rows = Adapter.parse_projects(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '08250')
        self.assertEqual(row['fecha_acuerdo'], '2025-11-27')
        self.assertEqual(row['fecha_publicacion'], '2025-12-12')
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['documentos'][-1]['seccion_actualizacion'], '2024-07-04')
        cert = row['documentos'][1]
        self.assertEqual(cert['url'], 'https://www.montbui.cat/media/repository/certificat.pdf')
        self.assertIn('\t', cert['url_original'])
        self.assertEqual(cert['source_url'], SOURCE)

    def test_no_invented_publication_from_update(self):
        html = HTML.replace('la publicació realitzada en el BOPB 12-12-2025', 'Edicte')
        self.assertIsNone(Adapter.parse_projects(html)[0]['fecha_publicacion'])

    def test_duplicate_documents_and_forms(self):
        duplicate = '<p><a href="https://www.montbui.cat/media/memoria.pdf">Còpia</a></p>'
        row = Adapter.parse_projects(HTML.replace('</div>', duplicate + '</div>'))[0]
        self.assertEqual(len(row['documentos']), 4)
        self.assertFalse(any('docx' in d['url'] for d in row['documentos']))

    def test_reject_unverified_or_changed_inventory(self):
        variants = [
            '<html>Login <a href="/poum">POUM</a></html>',
            HTML.replace('27-11-2025', '28-11-2025'),
            HTML.replace('a) Memòria', 'Navegació'),
            HTML.replace('</div>', '<p>Aprovació definitiva</p></div>'),
            HTML.replace('www.montbui.cat/media/memoria', 'example.com/media/memoria'),
            HTML + '<a rel="next" href="?page=2">2</a>',
            HTML + '<div class="pagination">1 2</div>',
        ]
        for html in variants:
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_and_snapshot_refresh(self):
        manifest = load_manifest('santa-margarida-de-montbui')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        official = '<a href="http://www.poummontbui.com">POUM</a>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[official, HTML]):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(path.read_text().splitlines()), 1)
            self.assertEqual(json.loads(path.read_text())['fecha_aprob'], '2025-11-27')
            before = path.read_bytes()
            with patch.object(adapter, '_fetch', return_value='<html>login</html>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_bytes(), before)
            with patch.object(adapter, '_fetch', side_effect=AssertionError('No licence HTTP')):
                self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
