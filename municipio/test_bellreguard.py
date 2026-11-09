import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.bellreguard import BellreguardAyuntamientoAdapter, SOURCE
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def inventory():
    groups = [('Nomativa urbanística', 'Normes urbanístiques', 'normas.pdf'),
              ('Zona urbanística poble', 'Plànol poble', 'poble.pdf'),
              ('Zona urbanística mar', 'Plànol mar', 'mar.pdf')]
    items = ''.join(
        f'<div class="et_pb_accordion_item"><h5 class="et_pb_toggle_title">{heading}</h5>'
        f'<a href="/wp-content/uploads/2020/02/{name}">{title}</a></div>'
        for heading, title, name in groups)
    return ('<div class="et_pb_column"><h1>Ordenació urbanística. Plànols i normativa</h1>'
            f'<div class="et_pb_accordion">{items}</div></div>')


class BellreguardTests(unittest.TestCase):
    def test_grouped_instrument_and_semantics(self):
        html = inventory() + '<a href="/licencia.pdf">Sol·licitud de llicència</a><h2>Notícies</h2>'
        rows = BellreguardAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '46048')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual({d['rol'] for d in row['documentos']}, {'normativa', 'plano_pueblo', 'plano_playa'})
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])

    def test_fail_closed_on_missing_new_or_paginated_inventory(self):
        for html in ('<h1>Urbanisme</h1>',
                     inventory().replace('Zona urbanística mar', 'Proyecto nuevo'),
                     inventory().replace('class="et_pb_accordion"', 'class="other"'),
                     inventory().replace('</h1>', '</h1><a rel="next" href="?page=2">Next</a>'),
                     inventory().replace('mar.pdf', 'licencia.html'),
                     inventory().replace('/wp-content/uploads/2020/02/mar.pdf', 'https://example.org/mar.pdf')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                BellreguardAyuntamientoAdapter.parse_projects(html)

    def test_live_path_validates_all_documents_before_writing(self):
        adapter = BellreguardAyuntamientoAdapter('bellreguard')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'%PDF-a', b'%PDF-b', b'%PDF-c']) as fetch:
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
                self.assertEqual(fetch.call_count, 4)
                self.assertEqual(len(json.loads(output.read_text())['documentos']), 3)
            before = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), ValueError('not PDF')]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), before)

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('bellreguard')
        self.assertIsInstance(load_portal_adapter(manifest), BellreguardAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Valencia')


if __name__ == '__main__':
    unittest.main()
