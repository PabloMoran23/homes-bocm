from pathlib import Path
import unittest
from municipio.onboarding_snapshot import reviewed_records


class SnapshotTests(unittest.TestCase):
    def test_forms_and_undated_notice_are_not_grants(self):
        rows = [
            {'titulo': 'Formulario de licencia de obra', 'fecha_concesion': '2025-01-02', 'url': 'https://sede.example/form', 'expediente': '12/2025'},
            {'titulo': 'Información sobre licencia de obra', 'url': 'https://sede.example/info'},
        ]
        self.assertEqual(reviewed_records(Path('licencias.jsonl'), rows), [])

    def test_explicitly_evidenced_grant_survives(self):
        row = {'titulo': 'Se concede licencia para obras', 'expediente': '12/2025', 'url': 'https://sede.example/notice'}
        self.assertEqual(reviewed_records(Path('licencias.jsonl'), [row]), [row])

    def test_portal_links_are_not_projects(self):
        ref = {'titulo': 'Visor urbanístico', 'origen': 'referencia_portal', 'url': 'https://sede.example/visor'}
        project = {'titulo': 'Plan parcial sector 3', 'expediente': '12/2025', 'url': 'https://sede.example/exp12'}
        self.assertEqual(reviewed_records(Path('proyectos.jsonl'), [ref, project]), [project])


if __name__ == '__main__':
    unittest.main()
