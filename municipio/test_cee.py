"""Offline parser contract tests; live captures remain in evidence/."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cee import CeeAyuntamientoAdapter, SOURCE, TITLE
from municipio.manifest import load_manifest


def inventory():
    labels = ['Documento de consultas 03/02/2022', 'Borrador do plan 14/01/2022',
              'Documento inicial estratéxico 14/01/2022', 'Documento de alcance 04/04/2022']
    links = [f'<a href="https://cmatv.xunta.gal/en-curso?_aaeRunning_WAR_aae_id=2476&amp;doc={i}">{label}</a>'
             for i, label in enumerate(labels)]
    # Includes unrelated resources before/after the actual plan section.
    return ('<main><div class="entry-content"><h4>Normas</h4><a href="/form">Formulario</a>'
            f'<h4>{TITLE}</h4><p>O concello de Cee atópase inmerso na elaboración do PXOM.</p>'
            + ''.join(links) + links[0] + '<h4>Contacto</h4><a href="/news">Noticias</a></div></main>')


class CeeTests(unittest.TestCase):
    def test_one_instrument_documents_dates_and_provenance(self):
        rows = CeeAyuntamientoAdapter.parse_projects(inventory())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '15023')
        self.assertEqual(row['expediente'], 'AAE 2476')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['documentos'][1]['fecha_documento'], '2022-01-14')
        self.assertEqual(row['documentos'][0]['procedencia'], SOURCE)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_changed_or_incomplete_inventory_fails(self):
        for html in [inventory().replace(TITLE, 'Formulario de licencia'),
                     inventory().replace('Documento de alcance', 'Otro documento'),
                     inventory().replace('id=2476&amp;doc=1', 'id=9999&amp;doc=1'),
                     inventory().replace('cmatv.xunta.gal', 'example.org'),
                     inventory().replace('inmerso na elaboración do PXOM', 'aprobado'),
                     '<main>Sin contenido</main>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                CeeAyuntamientoAdapter.parse_projects(html)

    def test_pagination_is_never_silently_truncated(self):
        for pager in ['<a rel="next" href="?page=2">2</a>',
                      '<div class="page-links">1 2</div>', '<a href="?page=2">Seguinte</a>']:
            with self.subTest(pager=pager), self.assertRaises(ValueError):
                CeeAyuntamientoAdapter.parse_projects(inventory().replace('<h4>Contacto', pager + '<h4>Contacto'))

    def test_refresh_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            adapter = CeeAyuntamientoAdapter('cee')
            rows = adapter.parse_projects(inventory())
            adapter._write(path, rows)
            self.assertEqual(json.loads(path.read_text())['id'], 'cee-pxom-aae-2476')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as refresh:
                adapter.update_proyectos(path, Path(directory) / 'state.json')
                refresh.assert_called_once_with(path)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('cee')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.cee:CeeAyuntamientoAdapter')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
