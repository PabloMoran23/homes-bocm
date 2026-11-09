from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.la_canonja import LaCanonjaAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

DOSSIER = 'https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/detallExpedient/259094'


def fixture(links=None):
    links = links if links is not None else [DOSSIER]
    return ('<div><div class="elementor-widget-heading"><h4 class="elementor-heading-title">'
            'POUM la Canonja - Aprovació Definitiva</h4></div><div>' +
            ''.join(f'<a href="{url}">Registre</a>' for url in links) + '</div></div>')


class LaCanonjaTests(unittest.TestCase):
    def test_real_instrument_and_unknown_fields(self):
        row, = parse_inventory(fixture())
        self.assertEqual((row['codigo_ine'], row['provincia'], row['rpuc_id']), ('43907', 'Tarragona', '259094'))
        self.assertEqual(row['fase'], 'aprobación definitiva')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)

    def test_documents_grouped_and_identity_stable(self):
        row, = parse_inventory(fixture([DOSSIER, DOSSIER]))
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['id'], parse_inventory(fixture())[0]['id'])

    def test_navigation_forms_news_not_records(self):
        for html in (f'<nav><a href="{DOSSIER}">POUM</a></nav>',
                     '<h4>Sol·licitud llicència d’obres</h4>', '<h4>Notícies</h4>',
                     '<form>Login</form>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_unrelated_link_cannot_supply_missing_dossier(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture([]) + f'<nav><a href="{DOSSIER}">POUM</a></nav>')
        with self.assertRaises(ValueError):
            parse_inventory(fixture(['https://example.org/rpucportal/index.html#/consulta/detallExpedient/259094']))

    def test_conflicting_dossiers_fail(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture([DOSSIER, DOSSIER.replace('259094', '123456')]))

    def test_unexpected_pagination_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace('</a>', '</a><a rel="next" href="?page=2">Next</a>'))

    def test_manifest_and_snapshot_update(self):
        manifest = load_manifest('la-canonja')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, LaCanonjaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            state = Path(directory) / 'state.json'
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as backfill:
                adapter.update_proyectos(output, state)
                backfill.assert_called_once_with(output)
            self.assertFalse(state.exists())
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
