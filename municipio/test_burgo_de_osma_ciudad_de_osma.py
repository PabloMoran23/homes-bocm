"""Offline parser and adapter-contract regression tests; no network required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.burgo_de_osma_ciudad_de_osma import (
    BASE, SOURCE, WORKS, BurgoDeOsmaCiudadDeOsmaAyuntamientoAdapter,
    parse_inventory, parse_project,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(content):
    return '<div data-elementor-type="wp-page">' + content + '</div>'


def inventory(extra=''):
    return page('Actuaciones llevadas a cabo por el ayuntamiento' + ''.join(
        f'<a href="{url}">Ver actuación</a>' for url in [*WORKS, BASE + 'vehiculo-electrico/']
    ) + extra)


def project(url):
    return page('OBJETO DEL PROYECTO PROYECTO SUBVENCIONADO El Burgo de Osma ' + WORKS[url][1]
                + ' Resolución de concesión de ayuda 18/11/2022'
                + '<a href="/wp-content/uploads/plan.pdf">Plan estratégico</a>' * 2
                + '<a href="https://contrataciondelestado.es/wps/poc?id=1">Lote 1</a>'
                + '<a href="https://contrataciondelestado.es/wps/poc?id=2">Lote 2</a>')


class ParserTests(unittest.TestCase):
    def test_inventory_excludes_vehicle_and_deduplicates(self):
        duplicate = f'<a href="{next(iter(WORKS))}">Ver actuación</a>'
        self.assertEqual(parse_inventory(inventory(duplicate)), sorted(WORKS))

    def test_changed_inventory_and_pagination_fail(self):
        for html in (inventory('<a href="/new/">Ver actuación</a>'),
                     inventory('<a rel="next" href="?page=2">2</a>'),
                     page('<a href="/solicitud-licencia/">Solicitud de licencia</a>'),
                     inventory().replace(next(iter(WORKS)), '/missing/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_group_documents_dates_and_no_geometry(self):
        url = next(iter(WORKS))
        row = parse_project(project(url), url)
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(len(row['referencias_contratacion']), 2)
        self.assertEqual(row['documentos'][0]['procedencia'], url)
        self.assertEqual(row['codigo_ine'], '42043')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertEqual(parse_project(project(url), url)['id'], row['id'])

    def test_tender_title_alone_is_not_project(self):
        url = next(iter(WORKS))
        with self.assertRaises(ValueError):
            parse_project(page(WORKS[url][0] + '<a href="https://contrataciondelestado.es/">Licitación</a>'), url)

    def test_adapter_snapshot_and_failure_preserves_previous_output(self):
        adapter = BurgoDeOsmaCiudadDeOsmaAyuntamientoAdapter('burgo-de-osma-ciudad-de-osma')
        def fetch(session, url):
            return inventory() if url == SOURCE else project(url)
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=fetch):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 2)
                original = output.read_text()
                adapter.update_proyectos(output, Path(tmp) / 'state.json')
                self.assertEqual(original, output.read_text())
            with patch.object(adapter, '_fetch', return_value='<html>error</html>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(original, output.read_text())
            self.assertEqual(len([json.loads(line) for line in original.splitlines()]), 2)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('burgo-de-osma-ciudad-de-osma')
        self.assertEqual(manifest.provincia, 'Soria')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), BurgoDeOsmaCiudadDeOsmaAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
