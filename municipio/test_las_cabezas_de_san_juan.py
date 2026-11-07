import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from municipio.adapters.las_cabezas_de_san_juan import (
    SOURCES, LasCabezasDeSanJuanAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(index=0, rows=None):
    if rows is None:
        rows = '<tr><td><a href="/export/sites/lascabezasdesanjuan/.galleries/documentos-general/avance.pdf">Documento de avance</a></td><td>1 KB</td><td>PDF</td></tr>'
    return ('<h1 class="detail-t">' + SOURCES[index][2] + '</h1>'
            '<table class="table"><tr><th>Nombre</th><th>Tamaño</th><th>Tipo</th></tr>' + rows + '</table>')


class InventoryTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        row = '<tr><td><a href="/.galleries/documentos-general/DIE">Documento inicial estratégico</a></td><td>1 KB</td><td>PDF</td></tr>'
        html = inventory().replace('</table>', row + row + '</table>')
        html += '<a href="/noticia.pdf">Noticias</a><a href="/formulario.pdf">Formulario</a>'
        record = parse_inventory(html, SOURCES[0][1])
        self.assertEqual(len(record['documentos']), 2)
        self.assertEqual(record['codigo_ine'], '41020')
        for doc in record['documentos']:
            self.assertEqual(doc['inventory_url'], SOURCES[0][1])
            self.assertTrue(doc['url'].startswith('https://www.lascabezasdesanjuan.es/'))
        self.assertFalse(record['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, record)

    def test_distinct_instruments_and_stable_identity(self):
        pgom = parse_inventory(inventory(), SOURCES[0][1])
        ranchillo = parse_inventory(inventory(1), SOURCES[1][1])
        self.assertNotEqual(pgom['id'], ranchillo['id'])
        changed = inventory().replace('avance.pdf', 'nuevo-avance.pdf')
        self.assertEqual(pgom['id'], parse_inventory(changed, SOURCES[0][1])['id'])

    def test_fail_closed(self):
        for html in ('<h1>Error</h1>', inventory(rows=''),
                     inventory().replace('PDF', 'HTML'),
                     inventory().replace('/export/sites/lascabezasdesanjuan/.galleries/documentos-general/avance.pdf', 'https://example.org/a.pdf'),
                     inventory().replace(SOURCES[0][2], 'Formulario de licencia'),
                     inventory() + '<ul class="pagination"><li>2</li></ul>',
                     inventory() + '<a href="?pagegalleryfiles-1-1=2">2</a>',
                     inventory() + '<link rel="next" href="/next">'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCES[0][1])

    def test_manifest(self):
        manifest = load_manifest('las-cabezas-de-san-juan')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41020')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    @patch('municipio.adapters.las_cabezas_de_san_juan.requests.Session')
    def test_live_contract_refresh_and_failed_fetch_preserves_output(self, session_class):
        session = session_class.return_value.__enter__.return_value
        def response(index):
            return Mock(text=inventory(index), url=SOURCES[index][1])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            adapter = LasCabezasDeSanJuanAyuntamientoAdapter('las-cabezas-de-san-juan')
            session.get.side_effect = [response(0), response(1)]
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 2)
            initial = output.read_text()
            self.assertEqual(len([json.loads(r) for r in initial.splitlines()]), 2)
            session.get.side_effect = [response(0), requests.Timeout('source unavailable')]
            with self.assertRaises(requests.Timeout):
                adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(initial, output.read_text())
            lic = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(lic)['disabled'])
            self.assertEqual(lic.read_text(), '')


if __name__ == '__main__':
    unittest.main()
