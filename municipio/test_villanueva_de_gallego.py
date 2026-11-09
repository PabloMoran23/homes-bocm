import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.villanueva_de_gallego import SOURCE, VillanuevaDeGallegoAyuntamientoAdapter as Adapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest

PREFIX = 'https://www.villanuevadegallego.org/wp-content/uploads/2025/04/'


def fixture(extra=''):
    return f'''<main id="main"><p>Texto refundido enero de 2009. Aprobado por el Pleno Municipal de fecha 16 de Marzo de 2.009. Incluye las modificaciones aisladas núms. 1, 2, 3.</p>
    <nav aria-label="PGOU"><a href="{PREFIX}memoria.pdf">1. Memoria</a>
    <a href="{PREFIX}plano.pdf">1. T.M.-0</a>
    <a href="{PREFIX}mod4.pdf">9. Modificación aislada núm. 4 del P.G.O.U</a>
    <a href="{PREFIX}mod4-anexo.pdf">Modificación núm. 4 Anexo</a>
    <a href="{PREFIX}mod15.rar">18. Modificación núm. 15</a><a href="https://idearagon.aragon.es/archivoSIUa/">Archivo SIUA</a></nav>
    <a href="{PREFIX}consolidado.pdf">NORMAS URBANÍSTICAS TEXTO CONSOLIDADO (Incluye hasta la Modif. 15)</a>
    <a href="{PREFIX}formulario.pdf">DECLARACION RESPONSABLE EN MATERIA URBANISTICA</a>
    <time>2025-12-18</time>{extra}</main>'''


class InventoryTests(unittest.TestCase):
    def test_grouping_dates_and_exclusion(self):
        rows = Adapter.parse_inventory(fixture())
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2, 1])
        self.assertEqual(rows[0]['fecha_acuerdo'], '2009-03-16')
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(any('formulario' in d['url'] for d in row['documentos']))
        self.assertIsNone(rows[1]['fecha_acuerdo'])

    def test_duplicates_and_stable_ids(self):
        original = fixture()
        duplicate = original.replace('</nav>', f'<a href="{PREFIX}mod4.pdf#page=2">Modificación núm. 4</a></nav>')
        self.assertEqual(Adapter.parse_inventory(original), Adapter.parse_inventory(duplicate))

    def test_source_drift_and_pagination_fail(self):
        for html in [fixture('<a rel="next" href="?page=2">2</a>'), fixture('<div class="pagination">2</div>'),
                     fixture().replace('aria-label="PGOU"', 'aria-label="Other"'),
                     fixture().replace(PREFIX + 'memoria.pdf', '/otro-inventario/'), '<html>Unavailable</html>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_manifest_live_entrypoint_refresh_and_disabled_licences(self):
        manifest = load_manifest('villanueva-de-gallego')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(url=SOURCE, text=fixture())
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.villanueva_de_gallego.requests.get', return_value=response):
            path = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['rows'], 3)
            before = path.read_text()
            adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(before, path.read_text())
            self.assertEqual(json.loads(before.splitlines()[0])['codigo_ine'], '50288')
            adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')
            self.assertEqual((Path(directory) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
