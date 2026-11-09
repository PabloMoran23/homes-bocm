"""Offline semantic and failure tests; no network required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.derio import DerioAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def inventory(extra=''):
    settings = json.dumps({'title': 'Normas subsidiarias', 'libraryType': 'single_folder',
                           'isNestedFolders': False, 'limit': 10})
    titles = ['normas urbanisticas tomo 2', 'NNSS normativa BOB', 'memoria tomo 1']
    titles += ['plano ' + str(i) for i in range(27)]
    links = ''.join(f'<a href="/wp-content/uploads/2025/04/{i}.pdf">{t}</a>'
                    for i, t in enumerate(titles))
    return (f"<div class='cf-app' data-json='{settings}'>{links}{extra}</div>"
            '<a href="https://hapo-derio.eus/es">Derio HAPO PGOU</a>'
            '<a href="/licencia.pdf">Solicitud de licencia</a>')


HOME = '<a href="/es/node/828">DOCUMENTACIÓN</a>' * 2
DOCS = '''<div class="field--name-body"><h2>Fase 3: Exposición pública (Avance)</h2>
<a href="/av.pdf">Documento de Avance</a><a href="/av.pdf">duplicado</a>
<a href="/map.pdf">Plano</a><a href="/info.pdf">Memoria de información</a>
<a href="https://example.org/unrelated.pdf">Otro</a></div>'''


class DerioTests(unittest.TestCase):
    def test_complete_library_grouped_with_no_invented_dates(self):
        row, home = Adapter.parse_inventory(inventory())
        self.assertEqual(len(row['documentos']), 30)  # all rows beyond display limit
        self.assertEqual(row['codigo_ine'], '48901')
        self.assertEqual(home, 'https://hapo-derio.eus/es')
        for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon'):
            self.assertIsNone(row[field])
        self.assertTrue(all(d['url_fuente'] == SOURCE for d in row['documentos']))

    def test_pgou_documents_are_one_instrument(self):
        url = Adapter.documentation_url(HOME, 'https://hapo-derio.eus/es')
        row = Adapter.parse_pgou(DOCS, url)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['fase'], 'Fase 3: Exposición pública (Avance)')
        self.assertIsNone(row['fecha_aprob'])
        self.assertFalse(row['publication_ready'])

    def test_reject_missing_or_changed_sources(self):
        for html in ('<a href="/form.pdf">Solicitud de licencia</a>',
                     inventory().replace('single_folder', 'hierarchical_folders'),
                     inventory().replace('memoria tomo 1', 'otro')):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        for html in (DOCS.replace('Fase 3:', 'Fase 4:'),
                     DOCS.replace('Documento de Avance', 'Formulario'), '<html>error</html>'):
            with self.assertRaises(ValueError):
                Adapter.parse_pgou(html, 'https://hapo-derio.eus/es/node/828')

    def test_pagination_fails_explicitly(self):
        for extra in ('<a rel="next" href="?page=2">2</a>',
                      '<div class="pager"><a href="?page=2">2</a></div>',
                      '<a href="?page=2">Siguiente</a>'):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory(extra))
            with self.assertRaises(ValueError):
                Adapter.parse_pgou(DOCS + extra, 'https://hapo-derio.eus/es/node/828')

    def test_refresh_and_failure_preserves_previous_output(self):
        adapter = Adapter('derio')
        with TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(), HOME, DOCS]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual([r['id'] for r in rows], ['derio-proy-nnss', 'derio-proy-pgou'])
            previous = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory(), HOME, '<html>error</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)
            lic = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(lic)['status'], 'disabled')
            self.assertEqual(lic.read_text(), '')

    def test_manifest_identity_and_safety_flags(self):
        manifest = load_manifest('derio')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']),
                         ('Derio', 'Bizkaia', '48901'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.derio:DerioAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
