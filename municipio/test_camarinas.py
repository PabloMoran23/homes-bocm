"""Offline parser/crawler contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.camarinas import (
    SOURCE, CamarinasAyuntamientoAdapter, canonical_url, discover_instruments, parse_links,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

NAV = '''<a href="http://www.camarinas.net/pxom/root.htm">PXOM</a>
<a href="/pepri/root.htm">PEPRI</a>
<a href="/portal-cidadan/modificacionpuntualpxom/gl">Modificación puntual PXOM</a>
<a href="/formulario.pdf">Solicitude de licenza</a>'''


class CamarinasTests(unittest.TestCase):
    def test_manifest_contract(self):
        manifest = load_manifest('camarinas')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('15016', 'Camariñas', 'A Coruña'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CamarinasAyuntamientoAdapter)

    def test_discovery_excludes_forms_and_news(self):
        self.assertEqual(set(discover_instruments(NAV)), {'pxom', 'pepri', 'modificacion-pxom'})
        with self.assertRaises(ValueError):
            discover_instruments('<a href="/formulario.pdf">Licenza</a>')

    def test_urls_and_image_maps(self):
        self.assertEqual(canonical_url(SOURCE, 'http://www.camarinas.net/pxom/a.pdf#page=1'), 'https://camarinas.net/pxom/a.pdf')
        links = parse_links('<map><area href="a.pdf" alt="Plano"></map><frame src="index.html">', 'https://camarinas.net/pxom/root.htm')
        self.assertEqual(links['https://camarinas.net/pxom/a.pdf'], 'Plano')
        self.assertIn('https://camarinas.net/pxom/index.html', links)

    def test_nested_frames_cycles_dedup_and_no_invented_dates(self):
        pages = {
            'https://camarinas.net/pxom/root.htm': '<frame src="index.html"><frame src="Presentacion.html">',
            'https://camarinas.net/pxom/Presentacion.html': '<p>DOCUMENTO PARA APROBACIÓN DEFINITIVA OUTUBRO 2012</p>',
            'https://camarinas.net/pxom/index.html': '<a href="a.pdf">Normativa</a><a href="nested.html">Planos</a>',
            'https://camarinas.net/pxom/nested.html': '<area href="a.pdf#page=1"><area href="b.pdf" alt="Plano B"><a href="root.htm">Inicio</a><a href="https://example.org/x.html">External</a>',
        }
        adapter = CamarinasAyuntamientoAdapter()
        with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            row = adapter._instrument('pxom', 'https://camarinas.net/pxom/root.htm', 'PXOM')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['paginas_fuente']), 4)
        for field in ['fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertNotIn('fase', row)
        self.assertEqual(row['documentos'][0]['url_indice'], 'https://camarinas.net/pxom/index.html')

    def test_pagination_and_empty_fail_closed(self):
        for html in ['<a rel="next" href="?page=2">2</a>', '<a href="p2">Seguinte</a>']:
            with self.assertRaises(ValueError):
                parse_links(html, SOURCE)
        adapter = CamarinasAyuntamientoAdapter()
        with patch.object(adapter, '_fetch', return_value='<p>Removed</p>'):
            with self.assertRaises(ValueError):
                adapter._instrument('pxom', 'https://camarinas.net/pxom/root.htm', 'PXOM')

    def test_backfill_groups_and_refreshes(self):
        adapter = CamarinasAyuntamientoAdapter()
        def fetch(url):
            return NAV if url == SOURCE else '<div class="listado-descargas-convocatorias"><a href="/media/documentos/mod.pdf">Documento</a></div><footer><a href="/media/documentos/privacy.pdf">Privacy</a></footer>' if '/portal-cidadan/' in url else '<a href="a.pdf">Documento</a>'
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=fetch):
                result = adapter.backfill_proyectos(output)
                adapter.update_proyectos(output, Path(folder) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({r['id'] for r in rows}), 3)
            self.assertTrue(all(len(r['documentos']) == 1 for r in rows))
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_fetch_failure_preserves_previous_snapshot(self):
        adapter = CamarinasAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=RuntimeError('network failure')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
