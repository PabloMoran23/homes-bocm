import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pobla_sa import PoblaSaAyuntamientoAdapter, SOURCE
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

PLAN = 'https://drive.google.com/file/d/real-document-id/view'
BOIB = 'https://sapobla.cat/sites/cilma_sa_pobla/files/2023-09/boib.pdf'


def card(title, url, date=''):
    return f'<div><div><h3>{title}</h3>{date}</div><a href="{url}">Visitar</a></div>'


def inventory(extra=''):
    return '<main><h1>Urbanisme</h1>' + card('Normes subsidiàries de sa Pobla 2003', PLAN) + card(
        'BOIB acord de les NNSS de sa Pobla', BOIB, '25/09/2023') + extra + '</main>'


class PoblaSaTests(unittest.TestCase):
    def test_grouping_identity_dates_and_exclusions(self):
        extra = card('Sol·licitud de llicència urbanística', '/form.pdf') + card('Pla Territorial Insular de Mallorca', '/regional')
        rows = PoblaSaAyuntamientoAdapter.parse_inventory(inventory(extra))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '07044')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['fecha_archivo_portal'], '25/09/2023')
        for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'geometry', 'lat', 'lon'):
            self.assertIsNone(row[field])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])

    def test_duplicate_cards_do_not_duplicate_instruments(self):
        rows = PoblaSaAyuntamientoAdapter.parse_inventory(inventory(card('Normes subsidiàries de sa Pobla 2003', PLAN)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['id'], PoblaSaAyuntamientoAdapter.parse_inventory(inventory())[0]['id'])

    def test_fail_closed_on_pagination_missing_documents_or_untrusted_links(self):
        for html in (inventory('<nav class="pager">2</nav>'), inventory('<a href="?page=1">Següent</a>'),
                     inventory().replace('BOIB acord de les NNSS de sa Pobla', 'Removed'),
                     inventory().replace(PLAN, 'https://example.com/file/d/test/view'),
                     inventory().replace(BOIB, 'https://example.com/boib.pdf'), '<main>No results</main>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                PoblaSaAyuntamientoAdapter.parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('pobla-sa')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07044')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.pobla_sa.requests.get') as get:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.update_licencias(path, Path(tmp) / 'state.json')['rows'], 0)
            self.assertEqual(path.read_text(), '')
            get.assert_not_called()

    def test_failed_document_fetch_preserves_previous_snapshot(self):
        adapter = PoblaSaAyuntamientoAdapter('pobla-sa')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'projects.jsonl'
            path.write_text('previous snapshot')
            class Response:
                text = inventory()
                content = b'not a PDF'
            with patch.object(adapter, '_fetch', return_value=Response()), self.assertRaises(ValueError):
                adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
