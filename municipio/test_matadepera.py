import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.matadepera import MatadeperaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<div class="journal-content-article"><p>projectes locals d\'obra ordinària</p>' + body + '</div>'


def doc(label='Projecte', folder='10', uid='abc'):
    return f'<a href="/documents/1686281/{folder}/file.pdf/{uid}">{label}</a>'


class MatadeperaTests(unittest.TestCase):
    def test_grouping_dedup_dates_and_provenance(self):
        html = page('<ul><li>Projecte de renovació. El projecte s\'ha aprovat inicialment pel Ple de 05/10/2020.</li></ul>'
                    + doc() + doc('Certificat', uid='def') + doc()
                    + '<p>Actualització: 19/05/2026</p>')
        row, = MatadeperaAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_acuerdo'], '2020-10-05')
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['lat'])
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)

    def test_paragraph_heading_and_date_before_approval(self):
        rows = MatadeperaAyuntamientoAdapter.parse_projects(page(
            '<p><strong>Projecte escola</strong></p><p>La Junta en data 29.11.2021 ha aprovat inicialment el Projecte.</p>'
            + doc() + '<ul><li>Memòria valorada del carrer</li></ul>' + doc('Memòria', '20')))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['fecha_acuerdo'], '2021-11-29')
        self.assertIsNone(rows[1]['fecha_acuerdo'])
        self.assertIsNone(rows[1]['fase'])

    def test_bundles_and_mixed_source_folders_retained(self):
        row, = MatadeperaAyuntamientoAdapter.parse_projects(page(
            '<ul><li>Aprovació inicial de 9 projectes fotovoltaics</li></ul>'
            + doc('Projecte escola', '10') + doc('Projecte piscines', '20', 'def')))
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(row['document_warning'])

    def test_no_fabrication_from_document_or_page_dates(self):
        row, = MatadeperaAyuntamientoAdapter.parse_projects(page(
            '<ul><li>Projecte executiu</li></ul>' + doc()
            + doc('Anunci 10/02/2026', uid='def') + '<p>Actualització 15/03/2026</p>'))
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_reject_missing_projects_changed_markup_and_pagination(self):
        valid = '<ul><li>Projecte escola</li></ul>' + doc()
        for html in ['<html>Login</html>', page('<a href="/tramits">Formulari llicència</a>'),
                     page('<ul><li>Projecte escola</li></ul>' + doc('Anunci')),
                     page(valid) + '<a rel="next" href="?page=2">2</a>',
                     page(valid) + '<a href="?page=2">Següent</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                MatadeperaAyuntamientoAdapter.parse_projects(html)

    def test_all_groups_and_stable_identity(self):
        first = '<ul><li>Projecte escola</li></ul>' + doc()
        second = '<ul><li>Projecte carrer</li></ul>' + doc(folder='20')
        a = MatadeperaAyuntamientoAdapter.parse_projects(page(first + second))
        b = MatadeperaAyuntamientoAdapter.parse_projects(page(second + first + doc('Informe', uid='new')))
        self.assertEqual(len(a), 2)
        self.assertEqual({r['titulo']: r['id'] for r in a}, {r['titulo']: r['id'] for r in b})

    def test_invalid_date_and_duplicate_headings_fail(self):
        body = '<ul><li>Projecte escola</li></ul>' + doc()
        with self.assertRaises(ValueError):
            MatadeperaAyuntamientoAdapter.parse_projects(page(body + body))
        with self.assertRaises(ValueError):
            MatadeperaAyuntamientoAdapter.parse_projects(page(
                '<ul><li>Projecte escola. El projecte s\'ha aprovat inicialment de 31/02/2025.</li></ul>' + doc()))

    def test_manifest_loading_snapshot_update_and_disabled_licences(self):
        manifest = load_manifest('matadepera')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08120')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MatadeperaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
            state = Path(tmp) / 'state.json'
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 32}) as backfill:
                self.assertEqual(adapter.update_proyectos(path, state)['rows'], 32)
                backfill.assert_called_once_with(path)
            self.assertFalse(state.exists())


if __name__ == '__main__':
    unittest.main()
