import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santona import SantonaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

DOC = {'titulo': 'PGOU', 'url': 'https://santona.es/descargas/51/PGOU/139/Plan', 'relacion': 'indice_municipal'}
INVENTORY = '''<div class="dropfiles-container"><a class="dropfiles_downloadlink"
 href="/descargas/51/PGOU/139/Plan">PGOU</a><a class="downloadlink"
 href="/descargas/51/PGOU/139/Plan">Descargar</a></div>
 <div class="dropfiles-container"><a class="dropfiles_downloadlink"
 href="/descargas/52/Modelo-obra">Solicitud licencia</a></div>'''
INDEX = '''<body>PLAN GENERAL de ORDENACIÓN URBANA de SANTOÑA
 aprobado definitivamente por la Comisión Regional de Urbanismo de Cantabria
 en su sesión de fecha 20 de noviembre de 1987
 publicado en el Boletín Oficial de Cantabria BOC de 19 de agosto de 1988
 0 ÍNDICE GENERAL
 <a href="http://www.santona.es/Datos/Urbanismo/PG.SANTOÑA_1_memoria_1.1.pdf">Memoria</a>
 <a href="http://www.santona.es/Datos/Urbanismo/PG.SANTOÑA_1_memoria_1.1.pdf">Duplicado</a>
 <a href="https://boc.cantabria.es/ordenanza">Ordenanza de ruido</a></body>'''


class SantonaTests(unittest.TestCase):
    def test_inventory_excludes_forms_and_duplicate_downloads(self):
        self.assertEqual(Adapter.parse_inventory(INVENTORY), [DOC])

    def test_grouping_dates_and_provenance(self):
        rows = Adapter.parse_index(INDEX, DOC)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['fecha_aprob'], '1987-11-20')
        self.assertEqual(row['fecha_publicacion'], '1988-08-19')
        self.assertEqual(row['date_provenance_url'], DOC['url'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['referencias']), 1)
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])

    def test_rejects_changed_or_paginated_inventory(self):
        for html in ['<h1>Login</h1>', INVENTORY + '<a rel="next" href="?page=2">Next</a>',
                     INVENTORY.replace('</div>', '<a class="dropfiles_downloadlink" href="/descargas/51/PGOU/140/extra">Extra</a></div>', 1)]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_rejects_missing_dates_or_wrong_plan(self):
        for html in [INDEX.replace('SANTOÑA', 'SANTANDER'), INDEX.replace('20 de noviembre de 1987', ''),
                     INDEX.replace('19 de agosto de 1988', '')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_index(html, DOC)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('santona')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '39079')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            with patch('requests.get', side_effect=AssertionError('No licence fetch allowed')):
                result = load_portal_adapter(manifest).backfill_licencias(path)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(path.read_text(), '')

    def test_update_refresh_and_failure_preserves_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous snapshot')
            adapter = Adapter('santona')
            with patch.object(adapter, '_fetch', return_value=b'<html>Login</html>'):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_text(), 'previous snapshot')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as backfill:
                self.assertEqual(adapter.update_proyectos(path, Path(tmp) / 'state.json'), {'rows': 1})
                backfill.assert_called_once_with(path)


if __name__ == '__main__':
    unittest.main()
