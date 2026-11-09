import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.borox import BoroxAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest

# Reduced municipal markup, preserving the reviewed section boundaries and labels.
HTML = '''<article><time itemprop="dateModified" datetime="2026-11-04"></time>
<div itemprop="articleBody"><table><tr><td><strong>NORMAS SUBSIDIARIAS</strong>
<table><tr><td><a href="/images/Ordenacion_nucleo_borox_1984.jpg"><img></a>
<a href="/images/Ordenacion_nucleo_borox_1984.jpg">Ordenación del núcleo de Borox en 1984.</a></td></tr></table>
<a href="/images/urbanismo/normas_para_nucleo_urbano.pdf">Normas para el núcleo urbano de Borox según Normas Subsidiarias de 1985.</a>
<a href="/images/urbanismo/normas_para_urbanizacion_nuevo_borox.pdf">Normas para la urbanizacion Nuevo Borox según Normas Subsidiarias de 1985.</a>
<a href="/images/urbanismo/normativa_poligono_industrial_antonio_del_rincon.pdf">Normativa polígono industrial Antonio del Rincón.</a>
</td></tr></table><table><tr><td>MODELOS DE SOLICITUD DE OBRAS
<a href="/images/solicitudes/solicitud_obra_mayor.pdf">Solicitud de Obra Mayor</a>
</td></tr></table></div></article>'''


class BoroxTests(unittest.TestCase):
    def test_grouping_provenance_and_no_inferred_dates(self):
        rows = parse_inventory(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '45021')
        self.assertEqual(len(row['documentos']), 3)
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        self.assertFalse(any('solicitud' in d['url'] or 'rincon' in d['url'] for d in row['documentos']))
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob'):
            self.assertIsNone(row[key])
        self.assertNotIn('lat', row)
        self.assertNotIn('fase', row)

    def test_no_placeholders(self):
        for html in ('', '<div itemprop="articleBody">Solicitud de obra mayor</div>',
                     HTML.replace('Normas para ', 'Formulario para ')):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails(self):
        for pager in ('<a rel="next" href="?start=5">Next</a>',
                      '<div class="pagination"><a href="?start=5">2</a></div>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(HTML + pager)

    def test_rejects_external_documents(self):
        with self.assertRaises(ValueError):
            parse_inventory(HTML.replace('/images/Ordenacion_nucleo_borox_1984.jpg',
                                         'https://example.com/images/map.jpg'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('borox')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, BoroxAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')

    def test_failure_preserves_existing_output(self):
        adapter = BoroxAyuntamientoAdapter('borox')
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=ValueError('Source unavailable')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
