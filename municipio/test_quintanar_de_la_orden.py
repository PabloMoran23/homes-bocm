"""Offline fixtures exercise source semantics and fail-closed inventory handling."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.quintanar_de_la_orden import (
    HOST, SOURCE, QuintanarDeLaOrdenAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def fixture(extra=''):
    def block(name, label):
        url = f'https://{HOST}/wp-content/uploads/2020/08/{name}.pdf'
        return f'<div class="wp-block-file"><a href="{url}">{label}</a><a href="{url}">Descarga</a></div>'
    return ('<article><h1>Normas Urbanísticas</h1><div class="entry-content">'
            '<h2>CONSULTA Y DESCARGA DE TEXTOS:</h2>'
            + block('complete', '00 - DOCUMENTO COMPLETO TEXTO')
            + block('memory', '02 – MEMORIA INFORMATIVA')
            + '<h2>CONSULTA Y DESCARGA DE PLANOS:</h2>'
            + block('zoning', '00 – ZONIFICACIÓN mod NNSS1985')
            + block('mp1', '12 – ORD 000 MP 1 – TÉRMINO CLASIFICACIÓN SUELO')
            + extra + '</div></article>')


class InventoryTests(unittest.TestCase):
    def test_group_documents_preserve_provenance_and_unknown_dates(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '45142')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual({d['seccion'] for d in row['documentos']}, {'textos', 'planos'})
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        for key in ('fecha', 'fecha_acuerdo', 'fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertIn('MP 1', row['documentos'][-1]['titulo'])
        self.assertEqual(parse_inventory(fixture())[0]['id'], row['id'])

    def test_reject_pagination_and_unsupported_sources(self):
        for extra in ('<a rel="next" href="?page=2">2</a>',
                      '<a href="?page=2">Siguiente</a>',
                      '<div class="page-links">1 2</div>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(fixture(extra))
        for html in ('<h1>Solicitud de licencia de obras</h1>',
                     fixture().replace('CONSULTA Y DESCARGA DE PLANOS:', 'Otros'),
                     fixture().replace('NNSS1985', 'sector'),
                     fixture().replace(HOST, 'example.org'),
                     fixture().replace('memory.pdf">Descarga', 'other.pdf">Descarga')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_refresh_failure_preserves_previous_output_and_disabled_licences(self):
        adapter = QuintanarDeLaOrdenAyuntamientoAdapter('quintanar-de-la-orden')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            path.write_text('previous\n')
            with patch('municipio.adapters.quintanar_de_la_orden.requests.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(path.read_text(), 'previous\n')
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest_load_and_adapter_resolution(self):
        from municipio.adapters.registry import load_portal_adapter
        manifest = load_manifest('quintanar-de-la-orden')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), QuintanarDeLaOrdenAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
