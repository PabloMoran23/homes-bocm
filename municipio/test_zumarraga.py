"""Offline parser and adapter contract checks; no live network in unit tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.zumarraga import (
    MUNICIPAL, SOURCE, ZumarragaAyuntamientoAdapter,
)
from municipio.manifest import load_manifest


def fixture():
    docs = ''.join(f'<a href="/wp-content/uploads/2024/05/{name}.pdf">AVANCE: {name}</a>'
                   for name in ('MEMORIA', 'PLANOS', 'DIE'))
    return ('<h1>Plan General de Ordenación Urbana</h1><p>Ayuntamiento de Zumarraga</p>'
            '<h2>LOS OBJETIVOS DE LA REVISIÓN DEL PGOU</h2>' + docs + docs
            + '<p>07. APROBACIÓN DEFINITIVA (fase futura)</p>'
            '<a href="https://forms.gle/test">CUESTIONARIO</a>'
            '<a href="https://example.com/otro.pdf">Ajeno</a>')


class ZumarragaTests(unittest.TestCase):
    def test_grouping_provenance_and_unknown_dates(self):
        rows = ZumarragaAyuntamientoAdapter.parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '20080')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertNotIn('definitiva', row['fase'])

    def test_changed_or_unusable_source_rejected(self):
        for html in ('<a href="plan.pdf">Plan</a>', fixture().replace('AVANCE: MEMORIA', 'Formulario'),
                     fixture().replace('Ayuntamiento de Zumarraga', 'Otro municipio')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                ZumarragaAyuntamientoAdapter.parse_projects(html)

    def test_pagination_rejected(self):
        for link in ('<a href="?page=2" rel="next">2</a>',
                     '<a href="?page=2">Siguiente</a>',
                     '<a href="?page=2" class="page-numbers">2</a>'):
            with self.subTest(link=link), self.assertRaises(ValueError):
                ZumarragaAyuntamientoAdapter.parse_projects(fixture() + link)

    def test_live_path_writes_and_provenance_guard(self):
        adapter = ZumarragaAyuntamientoAdapter('zumarraga')
        municipal = '<a href="https://zumarragaplanorokorra.eus/">HAPO</a>'
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[municipal, fixture()]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['id'], 'zumarraga-proy-pgou')
            before = out.read_bytes()
            with patch.object(adapter, '_fetch', return_value='<p>No plan portal</p>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest_loads(self):
        manifest = load_manifest('zumarraga')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.zumarraga:ZumarragaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
