import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.orkoien import OrkoienAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml

TITLE = 'RENOVACIÓN DE ALUMBRADO PÚBLICO EN ORKOIEN – III FASE'
LINK = '<a href="/wp-content/uploads/2026/01/comunicacion.pdf">' + TITLE + '</a>'


def inventory(links=LINK):
    return ('<main><h3>Política Antifraude</h3><a href="/antifraude.pdf">Acuerdos</a>'
            '<h3>Proyectos Ayuntamiento de Orkoien</h3>'
            '<p>Proyectos presentados al Plan de Recuperación.</p>' + links +
            '<h3>Canal de Denuncias</h3><a href="/formulario.pdf">Formulario</a></main>')


class OrkoienTests(unittest.TestCase):
    def test_group_documents_without_inventing_dates(self):
        html = inventory(LINK + LINK + LINK.replace('comunicacion.pdf', 'anexo.pdf'))
        rows = OrkoienAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '31906')
        self.assertEqual(row['url'], SOURCE)
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[field])
        self.assertEqual(row['id'], OrkoienAyuntamientoAdapter.parse_inventory(inventory())[0]['id'])

    def test_changed_or_paginated_inventory_fails(self):
        for html in ('<main>Missing</main>', inventory(''),
                     inventory(LINK + '<a rel="next" href="?page=2">2</a>'),
                     inventory(LINK + '<a href="?page=2">Siguiente</a>'),
                     inventory('<a href="/form.pdf">Solicitud de licencia</a>'),
                     inventory(LINK.replace('/wp-content', 'https://example.com/wp-content'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                OrkoienAyuntamientoAdapter.parse_inventory(html)

    def test_live_pipeline_and_disabled_licences(self):
        adapter = OrkoienAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(), b'%PDF-fixture']):
                result = adapter.backfill_proyectos(path)
            self.assertEqual(result['rows'], 1)
            row = json.loads(path.read_text())
            self.assertEqual(len(row['documentos'][0]['sha256']), 64)
            # A network/document failure must not overwrite a previous snapshot.
            before = path.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('orkoien')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '31906')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
