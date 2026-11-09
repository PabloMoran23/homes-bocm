"""Offline parser contracts; live validation is captured separately in evidence/."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.dosrius import DosriusAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def doc(uid, label='Descarrega Projecte'):
    return f'<a href="/documents/1218885/123/{uid}.pdf/{uid}">{label}</a>'


def inventory(content):
    return ('<div class="journal-content-article"><p>informació pública general</p>'
            '<p>Projectes Urbanístics any 2026</p>' + content +
            '<div class="datatable_info_footer paginacio_footer">Actualització: 05/10/2026</div></div>')


class DosriusTests(unittest.TestCase):
    def test_group_volumes_and_repeated_titles_across_years(self):
        html = inventory('<p><strong>-Projecte biblioteca municipal Can Batlle</strong></p><ul><li>' +
                         doc('volume1') + '</li><li>' + doc('volume2') + '</li></ul>' +
                         '<h4>rojectes Urbanístics any 2021</h4>' +
                         '<h4>-Projecte construcció biblioteca Can Batlle</h4><p>' + doc('volume3') + '</p>')
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['anios_seccion'], [2021, 2026])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['lat'])
        self.assertEqual(rows[0]['documentos'][0]['url_origen'], SOURCE)

    def test_duplicate_pdf_merges_titles_retaining_labels(self):
        rows = Adapter.parse_projects(inventory('<p>-Projecte coberta</p>' + doc('same') +
                    '<p>-Projecte tècnic coberta</p>' + doc('same', 'Projecte coberta nau')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['titulos_fuente']), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_malformed_title_link_does_not_merge_unrelated_instruments(self):
        # Live source wraps the Tortuga title in the preceding library PDF URL.
        html = inventory('<p>-Projecte biblioteca Can Batlle</p>' + doc('library') +
                         '<p><a href="/documents/1218885/123/library.pdf/library">'
                         '<strong>-Projecte coberta La Tortuga</strong></a></p>' + doc('roof'))
        # A document anchor used as heading is a title as well as a link.
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        roof = next(r for r in rows if 'Tortuga' in r['titulo'])
        self.assertTrue(roof['documentos'][0]['enlace_en_titulo'])
        self.assertEqual(len(roof['documentos']), 2)

    def test_explicit_agreement_not_publication(self):
        html = inventory('<p>-Projecte pavimentació (aprovat inicialment per la Junta de Govern Local en sessió de data 17/10/2023)</p>' + doc('road'))
        row = Adapter.parse_projects(html)[0]
        self.assertEqual(row['fecha_acuerdo'], '2023-10-17')
        self.assertEqual(row['fecha_aprob'], '2023-10-17')
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])

    def test_link_agreement_and_reference(self):
        row = Adapter.parse_projects(inventory('<p>-Modificació puntual NNSS exp Absis 904/2024</p>' +
            doc('plan', 'Document aprovat inicialment en sessió de Ple municipal de data 29/09/2022')))[0]
        self.assertEqual(row['fecha_aprob'], '2022-09-29')
        self.assertEqual(row['expediente'], '904/2024')
        self.assertEqual(row['tipo'], 'planeamiento_urbanistico')

    def test_excludes_heritage_forms_and_procurement(self):
        html = inventory('<p>-Projecte <span>P</span><span>avelló</span></p>' + doc('hall') +
                         '<p>-Declaració BCIL Torre de les Aigües</p>' + doc('heritage') +
                         '<p>-Llicència d’obres</p>' + doc('form') +
                         '<p>-Anunci de licitació</p>' + doc('procurement'))
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['titulo'], 'Projecte Pavelló')
        self.assertEqual(len(rows[0]['documentos']), 1)

    def test_rejects_empty_and_unlinked_projects(self):
        for html in ['<a href="/login">Login</a>', inventory('<p>-Projecte buit</p>'),
                     inventory('<p>-Projecte complet</p>' + doc('ok') + '<p>-Projecte buit</p>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_rejects_pagination_and_unexpected_document_host(self):
        valid = inventory('<p>-Projecte aigua</p>' + doc('water'))
        for html in [valid + '<a rel="next" href="?page=2">2</a>',
                     valid + '<a href="?page=2">Següent</a>',
                     valid.replace('</div>', '<div class="pagination">1 2</div></div>', 1),
                     valid.replace('href="/documents/', 'href="https://example.org/documents/')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('dosrius')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08075')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'licencias.jsonl'
            with patch('municipio.adapters.dosrius.requests.get', side_effect=AssertionError('No licence requests')):
                result = adapter.backfill_licencias(p)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(p.read_text(), '')

    def test_failed_refresh_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'proyectos.jsonl'
            p.write_text('previous snapshot\n')
            with patch('municipio.adapters.dosrius.requests.get') as get:
                get.return_value.content = b'login'
                get.return_value.text = '<p>login</p>'
                with self.assertRaises(ValueError):
                    Adapter('dosrius').update_proyectos(p, Path(d) / 'state.json')
            self.assertEqual(p.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
