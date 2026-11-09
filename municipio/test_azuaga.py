"""Offline regression tests for the municipal document parser and safe refresh."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.azuaga import AzuagaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def block(title, href, date):
    return f'<div><span>Documento| <strong>Fecha de Alta: </strong>{date}</span><a href="{href}">{title}</a></div>'


PDF = block('Normas Subsidiarias', './documentos/normas.pdf', '14/06/2023')
PLANS = block('Planos Normas Subsidiarias de Azuaga', './documentos/planos.zip', '21/03/2019')
FORM = block('Solicitud licencia obra mayor', './documentos/form.pdf', '13/11/2024')


def inventory(body):
    return '<div class="contenidop"><h1>Normativa y Solicitudes</h1>' + body + '</div>'


class AzuagaTests(unittest.TestCase):
    def test_group_documents_exclude_forms_and_keep_date_semantics(self):
        rows = AzuagaAyuntamientoAdapter.parse_inventory(inventory(PDF + PLANS + PDF + FORM))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '06014')
        self.assertEqual(row['url'], SOURCE)
        self.assertEqual({d['fecha_alta'] for d in row['documentos']}, {'2019-03-21', '2023-06-14'})
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'lon', 'fase'):
            self.assertIsNone(row[field])
        self.assertEqual(row['id'], AzuagaAyuntamientoAdapter.parse_inventory(inventory(PLANS + PDF))[0]['id'])

    def test_incomplete_changed_or_paginated_inventory_fails(self):
        for html in [inventory(FORM), inventory(PDF), '<html>unavailable</html>',
                     inventory(PDF + PLANS + '<a href="?ini=10">2</a>'),
                     inventory(PDF + PLANS + '<a rel="next" href="/more">Más</a>'),
                     inventory(PDF.replace('./documentos/normas.pdf', 'https://example.org/n.pdf') + PLANS),
                     inventory(PDF.replace('14/06/2023', '32/06/2023') + PLANS)]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                AzuagaAyuntamientoAdapter.parse_inventory(html)

    def test_failed_download_keeps_existing_output(self):
        adapter = AzuagaAyuntamientoAdapter('azuaga')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('existing\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory(PDF + PLANS).encode(), b'<html>error</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'existing\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('azuaga')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
