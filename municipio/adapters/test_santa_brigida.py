import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from municipio.adapters.santa_brigida import SantaBrigidaAyuntamientoAdapter, record


def post(title='Finalizan las obras de reforma de la Biblioteca Municipal', **extra):
    return {'id': 123, 'title': {'rendered': title}, 'content': {'rendered': '<p>Obras ejecutadas en la biblioteca municipal.</p>'}, 'link': 'https://www.santabrigida.es/2026/10/01/reforma-biblioteca/', 'date': '2026-10-01T09:30:00', **extra}


class LaUnionTest(unittest.TestCase):
    def test_real_announcement_semantics(self):
        row = record(post())
        self.assertEqual(row['fecha_publicacion'], '2026-10-01')
        self.assertEqual(row['origen'], 'comunicado_municipal')
        self.assertFalse(row['publication_ready'])
        for field in ('lat', 'lon', 'geometry', 'fecha_aprob', 'fase', 'fecha'):
            self.assertNotIn(field, row)

    def test_noise_forms_and_staging_excluded(self):
        for title in ('Exposición de obras de Paco Conesa', 'La Biblioteca Municipal acoge la obra de José Moreno Ojeda', 'Cortes de calles por obras de asfaltado', 'Formulario licencia de obras', 'El Ayuntamiento exige obras de mejora de la carretera', 'Obras y proyectos del municipio'):
            self.assertIsNone(record(post(title)))
        self.assertIsNone(record(post(link='https://staging.www.santabrigida.es/2026/10/01/reforma/')))
        self.assertIsNone(record(post(link='https://www.santabrigida.es/')))

    def test_missing_date_not_invented(self):
        self.assertNotIn('fecha_publicacion', record(post(date='bad')))

    def test_pagination_dedup_and_bounded_coverage(self):
        adapter = SantaBrigidaAyuntamientoAdapter('santa-brigida', {'max_pages': 2})
        with patch.object(adapter, '_fetch', side_effect=[([post()], 2), ([post(), post(id=124)], 2)]), patch('municipio.adapters.santa_brigida.time.sleep'):
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / 'projects.jsonl'
                stats = adapter.backfill_proyectos(output)
                self.assertEqual(stats['written'], 2)
                self.assertFalse(stats['truncated'])
                self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 2)
        with patch.object(adapter, '_fetch', return_value=([post()], 3)), patch('municipio.adapters.santa_brigida.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'cap reached'):
                adapter._collect()
        with patch.object(adapter, '_fetch', return_value=([], 1)):
            with self.assertRaises(RuntimeError):
                adapter._collect()


if __name__ == '__main__':
    unittest.main()
