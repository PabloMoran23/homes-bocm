import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.guissona import GuissonaAyuntamientoAdapter as Adapter, SOURCES
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

DOC = 'https://drive.google.com/file/d/real-document/view?usp=sharing'


def article(body):
    return '<div class="journal-content-article">' + body + '</div>'


def plan():
    return article('<h3>PLANS URBANÍSTICS</h3><p><a href="' + DOC + '">'
                   'Pla Parcial del sector SUD-1 de Guissona</a></p>'
                   '<div class="datatable_info_footer">Actualització: 22/08/2019 | Font: Propi ens</div>')


class GuissonaTests(unittest.TestCase):
    def test_plan_dates_and_identity(self):
        row, = Adapter.parse_inventory(plan(), 'planejament')
        self.assertEqual(row['codigo_ine'], '25110')
        self.assertEqual(row['source_updated_at'], '2019-08-22')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])

    def test_split_title_multiple_documents_and_duplicate_paragraphs(self):
        body = '<p><a href="' + DOC + '">- Aprovació inicial de la modificació puntual núm. 10 del POUM</a>'
        body += '<a href="https://www.guissona.cat/urbanisme/"> relatiu als sistemes tècnics.</a>'
        body += '<a href="/documents/4027575/0/annex.pdf/uuid"> Annex</a></p>'
        row, = Adapter.parse_inventory(article(body + body), 'exposicio')
        self.assertIn('relatiu als sistemes tècnics', row['titulo'])
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['source_url'] == SOURCES['exposicio'] for d in row['documentos']))
        self.assertIsNone(row['fecha_acuerdo'])

    def test_public_works_and_provisional_phase(self):
        html = article('<p><a href="' + DOC + '">Projecte executiu per a les instal·lacions fotovoltaiques de Guissona</a></p>'
                       '<p><a href="/documents/1/0/mod.pdf/uuid">Aprovació provisional de la modificació Puntual núm. 12 del POUM</a></p>')
        rows = Adapter.parse_inventory(html, 'exposicio')
        self.assertEqual(rows[0]['tipo'], 'proyecto_obra')
        self.assertIsNone(rows[0]['fase'])
        self.assertEqual(rows[1]['fase'], 'aprobación provisional')

    def test_non_records_are_rejected(self):
        for html in ['<h1>Login</h1>', article('<p>Servei de llicències</p>'),
                     article('<p><a href="' + DOC + '">Sol·licitud de llicència</a></p>'),
                     article('<p><a href="' + DOC + '">Anunci de licitació</a></p>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html, 'exposicio')

    def test_navigation_cannot_become_a_record(self):
        html = article('<div class="item_indicador"><p><a href="' + DOC + '">Projecte executiu fictici</a></p></div>')
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(html, 'exposicio')

    def test_pagination_and_new_tables_fail_closed(self):
        for extra in ['<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Següent</a>',
                      article('<table><tr><td>new inventory</td></tr></table>')]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_inventory(plan() + extra, 'planejament')

    def test_failed_refresh_preserves_existing_output(self):
        class Response:
            url = SOURCES['planejament']
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield b'<h1>Login</h1>'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            with patch('municipio.adapters.guissona.requests.get', return_value=Response()):
                with self.assertRaises(ValueError):
                    Adapter('guissona').update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_text(), 'previous snapshot\n')

    def test_manifest_contract_and_disabled_licences(self):
        manifest = load_manifest('guissona')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
