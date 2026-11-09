import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.arbucies import ArbuciesAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest


def page(body):
    return '<h1>Obres i infraestructures municipals</h1><div class="text-justify">' + body + '</div>'


def work(title='Obres del museu', extra=''):
    return (f'<p><strong>{title}</strong></p>'
            '<p>L’Ajuntament d’Arbúcies està duent a terme l\'execució de les obres del projecte.</p>' + extra)


class ArbuciesTests(unittest.TestCase):
    def test_grouping_provenance_and_no_inferred_dates(self):
        rows = Adapter.parse_projects(page(work(extra=(
            '<p>Expedient de subvenció 2025/6666. Borrasca del 7 al 9 de març de 2025.</p>'
            '<p><a href="/uploads/plan.pdf">Memòria</a><a href="/uploads/plan.pdf">Duplicat</a>'
            '<a href="/uploads/map.pdf">Plànol</a><img src="logo.jpg"></p>'))))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertNotIn('expediente', row)
        self.assertFalse(row['publication_ready'])

    def test_execution_status_divider_and_stable_identity(self):
        completed = ('<p><strong>Xarxa de calor</strong></p>'
                     '<p>L\'Ajuntament d\'Arbúcies ha dut a terme les obres d\'extensió de xarxa.</p>')
        rows = Adapter.parse_projects(page(work() + '<p><strong>Àrea de Medi Ambient</strong></p>' + completed))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['fase'], 'ejecutado según fuente municipal')
        self.assertEqual(rows[1]['id'], Adapter.parse_projects(page(completed))[0]['id'])

    def test_rejects_forms_procurement_empty_and_changed_markup(self):
        for html in ['<h1>Login</h1>', page(''), page('<p>Obres noves</p>'),
                     page('<p><strong>Sol·licitud de llicència</strong></p><p>Formulari</p>'),
                     page('<p><strong>Licitació obres</strong></p><p>Contractació pública</p>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_and_duplicates_fail(self):
        for tail in ['<a href="?page=2" rel="next">Més</a>', '<ul class="pagination"></ul>',
                     '<a href="?page=2">Següent</a>']:
            with self.assertRaises(ValueError):
                Adapter.parse_projects(page(work()) + tail)
        with self.assertRaises(ValueError):
            Adapter.parse_projects(page(work() + work()))

    def test_live_capture_structure(self):
        # Optional local capture verifies the exact discovered source without network in unit tests.
        capture = Path(__file__).resolve().parents[1] / 'evidence/works.html'
        if not capture.exists():
            self.skipTest('Local evidence capture absent')
        rows = Adapter.parse_projects(capture.read_text())
        self.assertEqual(len(rows), 4)
        self.assertEqual([r['fase'] for r in rows].count('en ejecución'), 2)
        self.assertTrue(all(not r['documentos'] for r in rows))

    def test_manifest_and_disabled_licences_and_refresh(self):
        manifest = load_manifest('arbucies')
        self.assertEqual(manifest.nombre, 'Arbúcies')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        adapter = Adapter('arbucies', manifest.portal.config)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 4}) as refresh:
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state')['rows'], 4)
                refresh.assert_called_once_with(path)


if __name__ == '__main__':
    unittest.main()
