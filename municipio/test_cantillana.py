import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.cantillana import CantillanaAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

PREFIX = '/export/sites/cantillana/es/transparencia/.galleries/IND-53-/'


def gallery(title, body):
    return f'<section class="gallery"><h4 class="gallery-title">{title}</h4>{body}</section>'


def pdf(name):
    return f'<a href="{PREFIX}{name}.pdf">{name}</a>'


def page(body):
    return f'<article class="sg-indicador-trans">{body}</article>'


class CantillanaTests(unittest.TestCase):
    def test_grouping_and_document_isolation(self):
        html = page(gallery('PLAN PARCIAL A', pdf('Memoria-A') + pdf('Planos-A') + pdf('Memoria-A'))
                    + gallery('PLAN PARCIAL B', pdf('Memoria-B'))
                    + gallery('AVANCE INVENTARIO DECRETO 2/2002', pdf('Inventario')))
        rows = parse_inventory(html)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('Memoria-B.pdf'))
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['id'], parse_inventory(page(gallery('PLAN PARCIAL A', pdf('Nuevo'))))[0]['id'])
        for row in rows:
            for field in ('fecha', 'fecha_aprob', 'lat', 'lon', 'fase', 'fecha_publicacion'):
                self.assertNotIn(field, row)

    def test_catalogue_and_agreement_dates_are_separate(self):
        media = ('<div class="media">' + pdf('Plan')
                 + '<time datetime="2026-04-10T11:50:00.000+0200"></time>'
                 + '<div class="description">Aprobado por acuerdo plenario de 29 de enero de 2026.</div></div>')
        row = parse_inventory(page(gallery('PLAN ESPECIAL PAJARES', media)))[0]
        self.assertEqual(row['fecha_acuerdo'], '2026-01-29')
        self.assertEqual(row['documentos'][0]['fecha_catalogo'], '2026-04-10')
        self.assertIn('texto', row['fecha_acuerdo_fuente'])
        self.assertNotIn('fecha_publicacion', row)

    def test_fail_closed_on_missing_content_or_document(self):
        for html in ('<html>error</html>', page(''), page(gallery('PLAN PARCIAL A', '')),
                     page(gallery('Solicitud de licencia', pdf('formulario')))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_never_silently_truncated(self):
        base = gallery('PLAN PARCIAL A', pdf('Plan'))
        for more in ('<a rel="next" href="?page=2">2</a>', '<ul class="pagination"></ul>',
                     '<a href="?page=2">Siguiente</a>'):
            with self.subTest(more=more), self.assertRaises(ValueError):
                parse_inventory(page(base + more))

    def test_foreign_pdf_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(page(gallery('PLAN PARCIAL A', '<a href="https://other.es/a.pdf">Plan</a>')))

    def test_live_method_writes_full_snapshot_and_preserves_output_on_failure(self):
        adapter = CantillanaAyuntamientoAdapter('cantillana')
        response = Mock(url=SOURCE, text=page(gallery('PLAN PARCIAL A', pdf('Plan'))))
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.cantillana.requests.get', return_value=response):
            path = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['count'], 1)
            original = path.read_text()
            self.assertEqual(json.loads(original)['codigo_ine'], '41023')
            response.text = '<html>unavailable</html>'
            with self.assertRaises(ValueError):
                adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_text(), original)

    def test_manifest_and_registry(self):
        manifest = load_manifest('cantillana')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('41023', 'Sevilla'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CantillanaAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
