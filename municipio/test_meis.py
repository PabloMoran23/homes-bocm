"""Parser semantics and adapter wiring; synthetic markup, no network in tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.meis import MeisAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def document(title, filename):
    return f'<a href="/wp-content/uploads/2026/04/{filename}.pdf">{title}</a>'


def inventory(extra='', outer=''):
    return ('<a href="/fake.pdf">MODIFICACIÓN PUNTUAL N9 PXOM</a>'
            '<div id="page-content"><div class="page-content-inner">'
            '<div class="wpb_wrapper"><p>Plan Xeral de Ordenación Municipal</p>'
            + document('PLAN XERAL DE ORDENACION MUNICIPAL DE MEIS', 'pxom')
            + document('MODIFICACIÓN PUNTUAL N4 PXOM', 'bop')
            + document('Plano 01', 'plano-01')
            + document('Suelo urbano-02', 'suelo-02') + extra + '</div>'
            + document('PLAN DE MOBILIDADE SOSTIBLE DE MEIS', 'pmus')
            + document('AuditoriaSaneamento_ConcellodeMeis', 'audit')
            + document('Solicitude de licenza', 'licenza') + outer + '</div></div>')


class MeisTests(unittest.TestCase):
    def test_instruments_group_documents_and_exclude_other_content(self):
        rows = parse_inventory(inventory(document('MODIFICACIÓN PUNTUAL N4 PXOM', 'normativa')))
        self.assertEqual([r['id'] for r in rows], ['meis-pxom', 'meis-pxom-mp-4', 'meis-pmus'])
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2, 1])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '36028')
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fase'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(row['publication_ready'])
            self.assertTrue(all(d['source_url'] == row['url'] for d in row['documentos']))

    def test_new_modifications_discovered_and_duplicate_links_grouped(self):
        rows = parse_inventory(inventory(document('MODIFICACIÓN PUNTUAL N5 PXOM', 'mp5') * 2))
        row = next(r for r in rows if r['id'] == 'meis-pxom-mp-5')
        self.assertEqual(len(row['documentos']), 1)

    def test_pagination_fails_instead_of_truncating(self):
        for anchor in ('<a href="/urbanismo/page/2/">2</a>', '<a rel="next" href="/next">&gt;</a>',
                       '<a href="?paged=2">2</a>', '<a href="/next">Seguinte</a>'):
            with self.subTest(anchor=anchor), self.assertRaisesRegex(ValueError, 'Paginated'):
                parse_inventory(inventory(outer=anchor))

    def test_changed_or_untrusted_sources_fail(self):
        for html in ('<html>error</html>', inventory().replace('Plano 01', 'Documento novo'),
                     inventory().replace('/wp-content/uploads/2026/04/pxom.pdf', 'https://example.org/pxom.pdf'),
                     inventory().replace('PLAN XERAL DE ORDENACION MUNICIPAL DE MEIS', 'Solicitude')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('meis')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MeisAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '36028')
        self.assertEqual(raw['provincia'], 'Pontevedra')
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            with patch('requests.Session', side_effect=AssertionError('No network for licences')):
                result = adapter.backfill_licencias(path)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(path.read_text(), '')

    def test_update_refreshes_full_inventory(self):
        adapter = MeisAyuntamientoAdapter('meis')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 5}) as run:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 5})
            run.assert_called_once_with(Path('out'))


if __name__ == '__main__':
    unittest.main()
