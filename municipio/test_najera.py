"""Offline parser and complete-inventory contract tests; no network required."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.najera import API, INVENTORY, NajeraAyuntamientoAdapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def dossier():
    return {
        'id': 42, 'parent': 4316, 'status': 'publish',
        'link': INVENTORY + 'alumbrado/',
        'title': {'rendered': 'Alumbrado &amp; entorno'},
        'date': '2026-11-03T13:19:41', 'modified': '2026-11-06T10:00:00',
        'content': {'rendered': '<p>Las obras de renovación del alumbrado de Nájera comenzaron en julio del 2025.</p>'
                    '<p>Finalizaron a primeros del 2026.</p>'
                    '<a href="/wp-content/proyecto.pdf">Proyecto</a>'
                    '<a href="/wp-content/proyecto.pdf">Mismo documento</a>'},
    }


class NajeraTests(unittest.TestCase):
    def setUp(self):
        self.adapter = NajeraAyuntamientoAdapter('najera')

    def test_physical_work_provenance_and_dates(self):
        row = self.adapter.parse_project(dossier(), 4316)
        self.assertEqual(row['titulo'], 'Alumbrado & entorno')
        self.assertEqual(row['fecha_publicacion'], '2026-11-03')
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(row['codigo_ine'], '26102')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['url'], 'https://najera.es/wp-content/proyecto.pdf')
        changed = dossier()
        changed['modified'] = '2026-11-07T00:00:00'
        self.assertEqual(self.adapter.parse_project(changed, 4316)['id'], row['id'])

    def test_forms_tenders_and_unrelated_news_are_not_works(self):
        for content in (
            'Solicitud de licencia de obras de alumbrado de Nájera.',
            'Anuncio de licitación de placas solares de Nájera.',
            'El Ayuntamiento de Nájera inició el proceso de inscripción en el concurso literario.',
        ):
            item = dossier()
            item['content']['rendered'] = '<p>' + content + '</p>'
            with self.assertRaises(ValueError):
                self.adapter.parse_project(item, 4316)

    def test_provenance_rejected(self):
        for key, value in [('parent', 1), ('status', 'draft'), ('link', 'https://other.example/obras-eu/a/')]:
            item = dossier()
            item[key] = value
            with self.assertRaises(ValueError):
                self.adapter.parse_project(item, 4316)
        with self.assertRaises(ValueError):
            self.adapter.parse_parent([])
        self.assertEqual(self.adapter.parse_parent([{'id': 4316, 'slug': 'obras-eu', 'link': INVENTORY}]), 4316)

    def test_all_pages_followed(self):
        with patch.object(self.adapter, '_get', side_effect=[([{'id': 1}], 2, 2), ([{'id': 2}], 2, 2)]) as get:
            self.assertEqual(len(self.adapter._inventory(None, {'parent': 4316})), 2)
            self.assertEqual(get.call_args_list[1].args[1]['page'], 2)

    def test_incomplete_duplicate_or_changing_inventory_fails(self):
        for responses in (
            [([{'id': 1}], 1, 2)],
            [([{'id': 1}], 2, 2), ([{'id': 1}], 2, 2)],
            [([{'id': 1}], 2, 2), ([{'id': 2}], 3, 3)],
            [([], 0, 0)],
        ):
            with patch.object(self.adapter, '_get', side_effect=responses):
                with self.assertRaises(ValueError):
                    self.adapter._inventory(None, {})

    def test_atomic_output_on_rejected_dossier_and_licences_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'proyectos.jsonl'
            target.write_text('previous\n')
            bad = copy.deepcopy(dossier())
            bad['content']['rendered'] = '<p>Solicitud</p>'
            with patch.object(self.adapter, '_inventory', side_effect=[
                [{'id': 4316, 'slug': 'obras-eu', 'link': INVENTORY}], [bad]
            ]):
                with self.assertRaises(ValueError):
                    self.adapter.backfill_proyectos(target)
            self.assertEqual(target.read_text(), 'previous\n')
            self.assertEqual(self.adapter.backfill_licencias(target)['status'], 'disabled')
            self.assertEqual(target.read_text(), '')

    def test_manifest_and_registry(self):
        manifest = load_manifest('najera')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Nájera', 'La Rioja', '26102'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), NajeraAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
