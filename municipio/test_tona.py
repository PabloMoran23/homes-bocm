import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tona import SOURCE, TonaAyuntamientoAdapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def inventory(fields='', documents='', title='Obres de renovació', dossier='URB/2025/337'):
    return f'''<h1>Projectes d’obres municipals</h1><div class="entry-content">
    <h2>Any 2025</h2><h3>{title}</h3><ul>
    <li><strong>EXPEDIENT</strong><br>{dossier}</li>
    <li><strong>PROJECTE</strong><a href="/wp-content/uploads/a.pdf">Projecte</a>{documents}</li>
    {fields}</ul></div>'''


class TonaTests(unittest.TestCase):
    def test_date_semantics_and_multiple_documents(self):
        html = inventory('''<li><strong>APROVACIÓ INICIAL PROJECTE</strong>31/07/2025</li>
        <li><strong>Aprovació definitiva del projecte</strong>: 09/10/2025</li>
        <li><strong>INICI EXECUCIÓ</strong>01/07/2026</li>
        <li><strong>FINALITZACIÓ EXECUCIÓ</strong></li>''',
        '<a href="/wp-content/uploads/b.pdf">Segon projecte</a>')
        row, = TonaAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprobacion_inicial'], '2025-07-31')
        self.assertEqual(row['fecha_aprob'], '2025-10-09')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['hitos'][-1]['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)

    def test_memoir_and_old_colon_format(self):
        row, = TonaAyuntamientoAdapter.parse_projects(inventory(
            '<li><strong>Aprovació memòria tècnica valorada</strong>: 13/06/2024</li>'))
        self.assertEqual(row['fecha_aprobacion_memoria'], '2024-06-13')
        self.assertIsNone(row['fecha_aprobacion_inicial'])
        self.assertEqual(row['inventory_year'], 2025)

    def test_no_approval_inferred_from_procurement(self):
        row, = TonaAyuntamientoAdapter.parse_projects(inventory(
            '<li><strong>INICI LICITACIÓ</strong>01/01/2025</li>'))
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])

    def test_refuse_missing_records_dates_documents_and_pagination(self):
        cases = ['<h1>Login</h1>', inventory().replace('a.pdf', 'a.pdf').replace('href=', 'missing='),
                 inventory(dossier=''), inventory('<li><strong>INICI EXECUCIÓ</strong>31/02/2025</li>'),
                 inventory() + '<a rel="next" href="?page=2">2</a>',
                 inventory().replace('</div>', '<a href="?page=2">Següent</a></div>'),
                 inventory().replace('<ul>', '<p>Formulari de sol·licitud</p><ul>', 1)]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                TonaAyuntamientoAdapter.parse_projects(html)

    def test_grouping_and_distinct_dossiers(self):
        first = inventory()
        block = first[first.index('<h3>'):first.index('</div>')]
        rows = TonaAyuntamientoAdapter.parse_projects(first.replace('</div>', block + '</div>'))
        self.assertEqual(len(rows), 1)
        other = block.replace('URB/2025/337', 'URB/2025/451')
        rows = TonaAyuntamientoAdapter.parse_projects(first.replace('</div>', other + '</div>'))
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        with self.assertRaises(ValueError):
            TonaAyuntamientoAdapter.parse_projects(first.replace('</div>', block.replace('Obres de renovació', 'Other') + '</div>'))

    def test_manifest_and_update_disabled_licences(self):
        manifest = load_manifest('tona')
        self.assertIsInstance(load_portal_adapter(manifest), TonaAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08283')
        self.assertEqual(raw['provincia'], 'Barcelona')
        for section, flag in [('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')]:
            self.assertIs(raw[section][flag], False)
        adapter = TonaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
                self.assertEqual(adapter.update_proyectos(path, Path(tmp) / 'state.json'), {'rows': 2})
                backfill.assert_called_once_with(path)


if __name__ == '__main__':
    unittest.main()
