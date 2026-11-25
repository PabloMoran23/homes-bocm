from __future__ import annotations

import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.oviedo import OviedoAyuntamientoAdapter


def registry_page(page: int, total: int, instrument_id: int, next_page: int | None = None) -> str:
    following = f'<a href="/busquedaConsulta?method=listPublico&amp;page={next_page}">Siguiente</a>' if next_page else ""
    return (
        f'<span class="pagebanner">{total} registros encontrados</span>'
        f'<span class="selected_page">{page}</span>{following}'
        f'<tr><td><a href="?idInstrumento={instrument_id}">Ver</a></td>'
        '<td>Municipal</td><td>OVIEDO</td><td>General</td>'
        '<td>PGO OVIEDO</td><td>ABC-123</td><td>Vigente</td></tr>'
    )


class OviedoRegistryTest(unittest.TestCase):
    def setUp(self):
        self.adapter = OviedoAyuntamientoAdapter('oviedo')

    def test_checks_all_advertised_instruments(self):
        pages = [registry_page(1, 2, 1797, next_page=2), registry_page(2, 2, 1798)]
        with patch.object(self.adapter, '_fetch', side_effect=pages) as fetch:
            rows = self.adapter._fetch_rpgur_list()
        self.assertEqual([row['id'] for row in rows], ['1797', '1798'])
        self.assertEqual(fetch.call_count, 2)
        self.assertIn('&page=2', fetch.call_args.args[0])

    def test_rejects_mismatched_or_incomplete_pages(self):
        for pages, message in (
            ([registry_page(1, 2, 1797, next_page=20)], 'read 1 of 2'),
            ([registry_page(1, 2, 1797, next_page=2), registry_page(1, 2, 1798)], 'pagination for page 2'),
            ([registry_page(1, 2, 1797, next_page=2), registry_page(2, 2, 1797)], 'repeated instrument 1797'),
            ([registry_page(1, 2, 1797, next_page=2), registry_page(2, 3, 1798)], 'inconsistent count'),
            (['<html>Temporarily unavailable</html>'], 'pagination for page 1'),
        ):
            with self.subTest(message=message):
                with patch.object(self.adapter, '_fetch', side_effect=pages):
                    with self.assertRaisesRegex(ValueError, message):
                        self.adapter._fetch_rpgur_list()

    def test_failed_later_page_keeps_previous_projects_and_state(self):
        pages = [registry_page(1, 2, 1797, next_page=2), urllib.error.URLError('lost connection')]
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            state = Path(directory) / 'proyectos.state.json'
            out.write_text('{"id":"previous"}\n')
            state.write_text('{"count":1}')
            with patch.object(self.adapter, '_fetch', side_effect=pages):
                with self.assertRaises(urllib.error.URLError):
                    self.adapter.update_proyectos(out, state)
            self.assertEqual(out.read_text(), '{"id":"previous"}\n')
            self.assertEqual(state.read_text(), '{"count":1}')

    def test_wfs_geometry_uses_the_declared_crs(self):
        crs = 'urn:ogc:def:crs:EPSG::4326'
        geom = {'type': 'Polygon', 'coordinates': [[[-5.85, 43.36], [-5.84, 43.36], [-5.85, 43.37], [-5.85, 43.36]]]}
        response = {
            'crs': {'type': 'name', 'properties': {'name': crs}},
            'features': [{'properties': {'Id._Inventario_Registro_Urbanístico': 1797}, 'geometry': geom}],
        }
        record = {}
        with patch.object(self.adapter, '_fetch_json', return_value=response):
            self.adapter._attach_geometry(record, 1797)
        self.assertEqual(record['geometry_crs'], crs)
        self.assertEqual(record['geom_geojson'], geom)
