"""Offline semantic and structural regression tests; no network required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.colindres import ColindresAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def fixture(extra=()):
    titles = ['NORMAS URBANÍSTICAS', 'PLANO 1', 'MODIFICACION PUNTUAL REDIA', 'MODIFICION PUNTUAL 2 COLEGIO', *extra]
    items, targets = [], []
    for i, title in enumerate(titles):
        key = f'et_pb_accordion_item_{i}'
        items.append(f'<div class="et_pb_accordion_item {key}"><h5 class="et_pb_toggle_title">{title}</h5></div>')
        targets.append({'class': key, 'url': f'https://www.colindres.es/wp-content/uploads/2019/06/{i}.pdf'})
    return '<h1>Plan General de Ordenación Urbana 1964:</h1><div class="et_pb_accordion">' + ''.join(items) + '</div><script>var et_link_options_data = ' + json.dumps(targets) + ';</script>'


class ColindresTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1, 1])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '39023')
            self.assertEqual(row['url'], SOURCE)
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
        self.assertEqual(rows, parse_inventory(fixture()))

    def test_no_news_forms_or_navigation(self):
        for html in ('<a>Plan General de Ordenación Urbana 1964:</a>', '<h1>Solicitud de licencia</h1>', fixture(['LICENCIA DE OBRAS'])):
            with self.subTest(html=html[:40]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected(self):
        for marker in ('<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Siguiente</a>', '<div class="wp-pagenavi"></div>'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                parse_inventory(fixture() + marker)

    def test_incomplete_or_foreign_targets_rejected(self):
        for html in (fixture().replace('www.colindres.es', 'example.org'), fixture().replace('et_pb_accordion_item_1"', 'missing"', 1), fixture().replace('PLANO 1', 'Sin clasificar')):
            with self.subTest(html=html[:40]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_more_documents_are_not_truncated(self):
        rows = parse_inventory(fixture([f'PLANO {i}' for i in range(2, 85)]))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]['documentos']), 85)

    def test_manifest_and_refresh(self):
        manifest = load_manifest('colindres')
        raw = load_yaml(manifest.path)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(raw['codigo_ine'], '39023')
        adapter = ColindresAyuntamientoAdapter('colindres')
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 3}) as mocked:
                self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state'), {'rows': 3})
                mocked.assert_called_once_with(out)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
