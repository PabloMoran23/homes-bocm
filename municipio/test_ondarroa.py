import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ondarroa import OndarroaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


ROOT = '/contenidos/informacion/puertos_planes_urbanisticos/es_def/adjuntos/'
HTML = '''<h1>Planes urbanísticos</h1><h3>BIZKAIA</h3><ul>
<li><strong>Ondarroa</strong><ul>
<li><a href="{root}original.pdf">PE original de 1990 (PDF, 241 MB)</a></li>
<li><a href="{root}modificacion.pdf">Modificación nº1 de 2009 (PDF, 44 MB)</a></li>
<li><a href="{root}original.pdf#page=2">PE original de 1990</a></li>
</ul></li><li><strong>Bermeo</strong><a href="{root}bermeo.pdf">Otro plan</a></li>
</ul>'''.format(root=ROOT)


class OndarroaTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_dates(self):
        rows = OndarroaAyuntamientoAdapter.parse_inventory(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '48073')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertEqual(row['id'], OndarroaAyuntamientoAdapter.parse_inventory(
            HTML.replace('1990', '1991'))[0]['id'])

    def test_all_new_versions_retained(self):
        html = HTML.replace('</ul></li><li>', '<li><a href="' + ROOT +
                            'third.pdf">Modificación nº2</a></li></ul></li><li>', 1)
        self.assertEqual(len(OndarroaAyuntamientoAdapter.parse_inventory(html)[0]['documentos']), 3)

    def test_fail_closed_for_missing_content_pagination_and_foreign_links(self):
        for html in ('<h1>Login</h1>', HTML.replace('Ondarroa', 'Otro'),
                     HTML.replace('BIZKAIA', 'GIPUZKOA'),
                     HTML.replace('PE original', 'Solicitud'),
                     HTML + '<a href="?page=2" rel="next">2</a>',
                     HTML + '<a href="?page=2">Siguiente</a>',
                     HTML.replace(ROOT + 'original.pdf', 'https://example.org/form.pdf')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                OndarroaAyuntamientoAdapter.parse_inventory(html)

    def test_failed_refresh_preserves_output_and_licences_are_disabled(self):
        adapter = OndarroaAyuntamientoAdapter('ondarroa')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous snapshot\n')
            with patch('municipio.adapters.ondarroa.requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_text(), 'previous snapshot\n')
            lic = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(lic)['status'], 'disabled')
            self.assertEqual(lic.read_text(), '')
            adapter._write(path, adapter.parse_inventory(HTML))
            self.assertEqual(json.loads(path.read_text())['municipio'], 'Ondarroa')

    def test_manifest(self):
        manifest = load_manifest('ondarroa')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '48073')
        self.assertEqual(manifest.provincia, 'Bizkaia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
