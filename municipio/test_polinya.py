from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.polinya import PolinyaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

DOC = '/media/repository/documents_oficials/normativa_urbanistica/PGOU_Polinya_REFOS_gener_2022.pdf'
HTML = '''<main><div id="readspeakerPage"><h1>Normativa d'urbanisme</h1>
<div class="dinamic"><div class="subtitle">Pla General d'Ordenació Urbana</div>
<p>Planejament Urbanístic de Polinyà. text refós: document de treball.</p>
<a href="https://dtes.gencat.cat/rpucportal/#/consulta/cerca">RPUC</a>
<a href="%s">Refós PGOU</a><a href="%s">Consulta</a></div>
<span>Darrera actualització: 20.03.2023</span></div></main>''' % (DOC, DOC)


class PolinyaTests(unittest.TestCase):
    def test_group_and_preserve_documents(self):
        extra = DOC.replace('gener_2022', 'annex')
        html = HTML.replace('</p>', '</p><a href="%s">Annex</a>' % extra)
        row, = parse_inventory(html)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '08167')
        self.assertEqual(row['id'], parse_inventory(HTML)[0]['id'])
        self.assertTrue(row['url_documento'].endswith('annex.pdf'))
        self.assertIn('working compilation', row['document_provenance'])

    def test_unknown_dates_and_geometry(self):
        row, = parse_inventory(HTML)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_reject_incomplete_or_unrelated_source(self):
        for html in ('<h1>Login</h1>', '<a href="%s">PGOU</a>' % DOC,
                     HTML.replace('document de treball', 'formulari de llicència'),
                     HTML.replace(DOC, '/licencia.pdf'),
                     HTML.replace(DOC, 'https://other.example/PGOU.pdf'),
                     HTML.replace('Polinyà', 'Other municipality')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_pagination(self):
        for pager in ('<a rel="next" href="?page=2">Next</a>', '<div class="pagination">2</div>'):
            with self.assertRaises(ValueError):
                parse_inventory(HTML.replace('</main>', pager + '</main>'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('polinya')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, PolinyaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')

    def test_update_refreshes_snapshot(self):
        adapter = PolinyaAyuntamientoAdapter('polinya')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 1})
            backfill.assert_called_once_with(Path('out'))


if __name__ == '__main__':
    unittest.main()
