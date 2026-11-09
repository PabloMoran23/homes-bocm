import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.nambroca import NambrocaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

TITLES = [
    'Anuncio CONTENIDO NORMATIVO Sector 8b 8c NNSS Nambroca BOP 07.09.2023',
    'PUBLICACION DOCM 2 DE MAYO DE 2023 APROBACION PAU SECT 8B Y 8C NNSS NAMBROCA',
    'P REPARCELACIÓN SCT8b-8c_r2_mayo 2023_signed',
    'Planos NNSS', 'TEXTO NNSS Y MODIFICACIONES NAMBROCA',
    'BOP ANUNCIO CONTENIDO NORMATIVO SECTOR 20',
]


def fixture(titles=TITLES):
    rows = ''.join(f'<tr><td><a href="/preview-document/00000000-0000-0000-0000-{i:012d}">{t}</a></td></tr>'
                   for i, t in enumerate(titles))
    return '<h2>7.1. PLANEAMIENTO URBANÍSTICO</h2><table class="TransparencyListPanel"><tbody>' + rows + '</tbody></table>'


class NambrocaTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows = NambrocaAyuntamientoAdapter.parse_inventory(fixture())
        self.assertEqual(len(rows), 4)
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [1, 1, 2, 2])
        pau = rows[0]
        self.assertEqual({d['fecha_publicacion'] for d in pau['documentos']}, {'2023-09-07', '2023-05-02'})
        for row in rows:
            self.assertEqual(row['codigo_ine'], '45107')
            for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase'):
                self.assertIsNone(row[key])
            self.assertFalse(row['publication_ready'])
            self.assertTrue(all(d['url_origen'] == SOURCE for d in row['documentos']))

    def test_reject_incomplete_changed_or_navigation_only(self):
        cases = [fixture(TITLES[:-1]), fixture(TITLES + ['Solicitud de licencia de obra']),
                 '<a href="/urbanismo">Urbanismo</a>',
                 fixture().replace('TransparencyListPanel', 'other'),
                 fixture().replace('/preview-document/', 'https://other.example/preview-document/')]
        for html in cases:
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                NambrocaAyuntamientoAdapter.parse_inventory(html)

    def test_pagination_is_never_silently_truncated(self):
        for control in ('<a href="?page=2">Mostrar más</a>', '<a rel="next" href="?p=2">2</a>', '<button>Siguiente</button>'):
            with self.subTest(control=control), self.assertRaises(ValueError):
                NambrocaAyuntamientoAdapter.parse_inventory(fixture() + control)

    def test_duplicates_and_order_keep_stable_identity(self):
        expected = NambrocaAyuntamientoAdapter.parse_inventory(fixture())
        reversed_rows = NambrocaAyuntamientoAdapter.parse_inventory(fixture(list(reversed(TITLES))))
        self.assertEqual([r['id'] for r in expected], [r['id'] for r in reversed_rows])
        html = fixture().replace('</tbody>', '<tr><td><a href="/preview-document/00000000-0000-0000-0000-000000000003">Planos NNSS</a></td></tr></tbody>')
        self.assertEqual(NambrocaAyuntamientoAdapter.parse_inventory(html), expected)

    def test_manifest_snapshot_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('nambroca'))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            with patch.object(NambrocaAyuntamientoAdapter, 'backfill_proyectos', return_value={}) as backfill:
                direct = NambrocaAyuntamientoAdapter('nambroca')
                direct.update_proyectos(out, Path(tmp) / 'state.json')
                backfill.assert_called_once()
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
            NambrocaAyuntamientoAdapter._write(out, NambrocaAyuntamientoAdapter.parse_inventory(fixture()))
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 4)


if __name__ == '__main__':
    unittest.main()
