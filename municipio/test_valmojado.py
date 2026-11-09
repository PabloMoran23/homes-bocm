import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.valmojado import SOURCE, ValmojadoAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def page(*links):
    return ('<h1 class="entry-title">Normas Subsidarias</h1><article>'
            '<div class="entry-content">' + ''.join(
                f'<a href="{url}">{label}</a>' for label, url in links
            ) + '</div></article>')


BASE = ('Normas Subsidarias Valmojado.', '/docs/normas.pdf')


class ValmojadoTests(unittest.TestCase):
    def test_groups_documents_and_isolates_sectors(self):
        html = page(BASE, ('Anexo def. conceptos Valmojado.', '/docs/anexo.pdf'),
                    ('Doc. memoria justificativa Valmojado.', '/docs/memoria.pdf'),
                    ('01 – ORD 01 – CLASIFICACION suelo.', '/docs/plano.pdf'),
                    ('Plan Parcial Ordenación SECTOR 3.', '/docs/sector3.pdf'),
                    ('Plan Parcial Ordenación SECTOR 16.', '/docs/sector16.pdf'),
                    ('Plan Parcial Ordenación SECTOR 3.', '/docs/sector3.pdf'),
                    ('Solicitud licencia', '/formulario/'))
        rows = parse_inventory(html)
        self.assertEqual([len(r['documentos']) for r in rows], [4, 1, 1])
        self.assertEqual(len({r['id'] for r in rows}), 3)
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('sector16.pdf'))
        for r in rows:
            self.assertEqual(r['codigo_ine'], '45180')
            self.assertIsNone(r['fecha_acuerdo'])
            self.assertIsNone(r['fecha_publicacion'])
            self.assertIsNone(r['fecha_aprob'])
            self.assertIsNone(r['geometry'])
            self.assertFalse(r['publication_ready'])
            self.assertNotIn('fase', r)

    def test_empty_and_navigation_are_not_records(self):
        for html in ('', page(), '<nav><a href="/normas.pdf">Normas Subsidarias Valmojado.</a></nav>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_refuses_unclassified_pdf_and_external_documents(self):
        for link in [('Solicitud licencia', '/licencia.pdf'),
                     ('Licitación de obras', '/contrato.pdf'),
                     ('Noticia', '/noticia.pdf'),
                     ('Plan Parcial Ordenación SECTOR 3.', 'https://example.org/plan.pdf')]:
            with self.assertRaises(ValueError):
                parse_inventory(page(BASE, link))

    def test_refuses_pagination(self):
        for marker in ('<a rel="next" href="?page=2">Siguiente</a>',
                       '<div class="page-links">1 2</div>'):
            with self.assertRaises(ValueError):
                parse_inventory(page(BASE) + marker)

    def test_cms_dates_not_approval_dates(self):
        rows = parse_inventory(page(BASE) + '<time datetime="2011-12-14">Publicado</time>')
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fecha_publicacion'])

    @patch('municipio.adapters.valmojado.requests.get')
    def test_snapshot_update_and_capture(self, get):
        get.return_value = Mock(url=SOURCE, text=page(BASE))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = ValmojadoAyuntamientoAdapter(config={'capture_dir': directory})
            result = adapter.update_proyectos(root / 'rows.jsonl', root / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads((root / 'rows.jsonl').read_text())['id'], 'valmojado-planeamiento-nnss')
            self.assertTrue((root / 'inventory.html').is_file())
            adapter.backfill_licencias(root / 'licencias.jsonl')
            self.assertEqual((root / 'licencias.jsonl').read_text(), '')

    @patch('municipio.adapters.valmojado.requests.get')
    def test_bad_redirect_does_not_overwrite_output(self, get):
        get.return_value = Mock(url='https://www.valmojado.com/', text=page(BASE))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rows.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                ValmojadoAyuntamientoAdapter().backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest(self):
        manifest = load_manifest('valmojado')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '45180')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
