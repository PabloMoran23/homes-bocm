"""Offline parser and adapter contract checks; no evidence fixtures required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.membrilla import MembrillaAyuntamientoAdapter, SOURCE
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def link(title, name):
    return ('<p class="elementor-icon-box-title"><a href="/wp-content/uploads/2026/04/'
            + name + '.pdf">' + title + '</a></p>')


def inventory():
    return ('<h1>Planeamiento Urbanístico</h1><h2>Normas de Planeamiento Urbanístico</h2>'
            + link('NORMAS URBANÍSTICAS DE MEMBRILLA', 'normas') * 2
            + '<div data-element_type="container">'
            + link('MODIFICACIÓN PUNTUAL 1-2022 MEMBRILLA', 'modificacion')
            + link('OFICIO DIFERENTES ORGANISMOS', 'oficio')
            + link('PLANOS 1', 'planos1') + link('PLANOS 2', 'planos2') + '</div>'
            + '<h2>Instrumentos de desarrollo urbanístico</h2>'
            + link('ESTUDIO DE DETALLE MANZANA M1 SECTOR SI A', 'M1')
            + link('ESTUDIO DE DETALLE MANZANA M2 SECTOR SI A', 'M2')
            + link('PROYECTO DE REPARCELACIÓN SECTOR S1 A', 'reparcelacion')
            + link('PROYECTO OBRA PUBLICA ORDINARIA DE URBANIZACIÓN NIQUEL-PASTORES', 'obra'))


class MembrillaTests(unittest.TestCase):
    def test_grouping_identity_and_no_invented_semantics(self):
        rows = MembrillaAyuntamientoAdapter.parse_projects(inventory())
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(len(r['documentos']) for r in rows), 9)
        self.assertEqual(len(rows[1]['documentos']), 4)
        self.assertEqual(len({r['id'] for r in rows}), 6)
        self.assertEqual(rows, MembrillaAyuntamientoAdapter.parse_projects(inventory()))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '13054')
            self.assertEqual(row['url'], SOURCE)
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])

    def test_rejects_pagination(self):
        for extra in ('<a rel="next" href="/next">2</a>', '<a href="?paged=2">2</a>',
                      '<a href="/next">Siguiente</a>', '<div class="pagination"></div>'):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Pagination'):
                MembrillaAyuntamientoAdapter.parse_projects(inventory() + extra)

    def test_rejects_missing_or_unsupported_content(self):
        for html in ('<h1>Login</h1>', '<h1>Planeamiento Urbanístico</h1>',
                     inventory() + link('SOLICITUD DE LICENCIA', 'formulario'),
                     inventory().replace('/wp-content/uploads/', 'https://example.org/'),
                     inventory().replace('MODIFICACIÓN PUNTUAL 1-2022 MEMBRILLA', 'PLANOS 0')):
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                MembrillaAyuntamientoAdapter.parse_projects(html)

    def test_annex_must_share_parent_container(self):
        html = inventory().replace(link('PLANOS 1', 'planos1'), '</div>' + link('PLANOS 1', 'planos1') + '<div>')
        with self.assertRaisesRegex(ValueError, 'Annex'):
            MembrillaAyuntamientoAdapter.parse_projects(html)

    def test_verified_snapshot_and_failure_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            adapter = MembrillaAyuntamientoAdapter('membrilla')
            with patch.object(adapter, '_fetch', side_effect=lambda url, limit: inventory().encode() if url == SOURCE else b'%PDF-1.4\nfixture') as fetch:
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 6)
            self.assertEqual(fetch.call_count, 10)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows[1]['documentos'][1]['sha256']), 64)
            previous = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=lambda url, limit: inventory().encode() if url == SOURCE else b'<html>Denied</html>'):
                with self.assertRaisesRegex(ValueError, 'not a PDF'):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)
            self.assertFalse((Path(tmp) / 'state.json').exists())

    def test_manifest_registry_and_disabled_licences(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/membrilla/manifest.yaml'
        raw = load_yaml(path)
        self.assertEqual(raw['codigo_ine'], '13054')
        self.assertEqual(raw['provincia'], 'Ciudad Real')
        for section, field in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[section][field], False)
        adapter = load_portal_adapter(load_manifest(path))
        self.assertIsInstance(adapter, MembrillaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
