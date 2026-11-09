import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.mora_d_ebre import MoraDEbreAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def panel(title, documents='<a href="/wp-content/uploads/plan.pdf">Pla</a>'):
    return (f'<div class="fusion-panel"><div class="fusion-toggle-heading">{title}</div>'
            f'<div class="panel-body">{documents}</div></div>')


def inventory(panels):
    return '<h1>Modificació Normes Subsidiàries</h1><div class="post-content">' + panels + '</div>'


class ParserTests(unittest.TestCase):
    def test_group_documents_and_date_semantics(self):
        html = inventory(panel(
            'Modificació puntual de les Normes Subsidiàries de Planejament de diversos sistemes municipals '
            '(Aprovada al Ple de data 30/04/2026)',
            '<a href="/wp-content/uploads/plan.pdf">Pla</a>'
            '<a href="/wp-content/uploads/cert.pdf">Certificat</a>') + panel(
            'EDICTE aprovació inicial modificació NNSS Sector 19 (novembre 2025)',
            '<a href="http://eseu.moradebre.cat/sector19.pdf"><img alt="Sector 19"></a>'))
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_acuerdo'], '2026-04-30')
        self.assertIsNone(rows[0]['fase'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertEqual(rows[1]['fase'], 'aprobación inicial')
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertIsNone(rows[1]['fecha_publicacion'])
        self.assertIsNone(rows[1]['lat'])
        self.assertFalse(rows[1]['publication_ready'])

    def test_duplicate_panels_merge_documents_and_identity_ignores_date(self):
        title = 'EDICTE aprovació inicial modificació NNSS Sector 19'
        rows = Adapter.parse_projects(inventory(panel(title + ' (novembre 2025)') + panel(
            title + ' (novembre 2025)', '<a href="/wp-content/uploads/edict.pdf">Edicte</a>')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        other = Adapter.parse_projects(inventory(panel(title + ' (desembre 2025)')))
        self.assertEqual(rows[0]['id'], other[0]['id'])

    def test_fail_closed_for_empty_form_news_and_missing_documents(self):
        for html in ('<h1>Login</h1>', inventory(''),
                     inventory(panel('Sol·licitud de llicència')),
                     inventory(panel('Notícies municipals')),
                     inventory(panel('Modificació NNSS Sector 19', '')),
                     inventory(panel('Modificació NNSS Sector 19', '<a href="https://example.org/a.pdf">Pla</a>'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_and_invalid_date_fail(self):
        html = inventory(panel('Modificació NNSS Sector 19'))
        for pager in ('<a rel="next" href="?page=2">Next</a>', '<div class="pagination">2</div>'):
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html + pager)
        with self.assertRaises(ValueError):
            Adapter.parse_projects(inventory(panel('Modificació NNSS (Aprovada al Ple de data 31/02/2026)')))

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('mora-d-ebre')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '43093')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            with patch('municipio.adapters.mora_d_ebre.requests.get') as get:
                result = adapter.backfill_licencias(out)
                get.assert_not_called()
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_update_refreshes_full_snapshot_without_state_cutoff(self):
        adapter = Adapter('mora-d-ebre')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 2})
            backfill.assert_called_once_with(Path('out'))


if __name__ == '__main__':
    unittest.main()
