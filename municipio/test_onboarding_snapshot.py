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

    def test_explicit_catalogue_stubs_and_procedures_are_not_projects(self):
        rows = [{'titulo': 'Licencias urbanísticas', 'origen': origin,
                 'expediente': '12/2025', 'url': 'https://sede.example/catalog'}
                for origin in ('catalog_stub', 'catalogo', 'sede_tramite_info',
                               'wp_form_pdf', 'portal_semilla')]
        self.assertEqual(reviewed_records(Path('proyectos.jsonl'), rows), [])

    def test_municipal_centroid_is_removed_but_real_geometry_centroid_survives(self):
        base = {'titulo': 'Plan parcial sector 3', 'expediente': '12/2025',
                'url': 'https://sede.example/exp12', 'lat': 38.2, 'lon': -1.4}
        guessed = {**base, 'coord_source': 'municipio_centroid'}
        measured = {**base, 'coord_source': 'portal_geometry_centroid'}
        exported = reviewed_records(Path('proyectos.jsonl'), [guessed, measured])
        self.assertNotIn('lat', exported[0])
        self.assertNotIn('lon', exported[0])
        self.assertEqual(exported[1], measured)
        self.assertIn('lat', guessed)


if __name__ == '__main__':
    unittest.main()
