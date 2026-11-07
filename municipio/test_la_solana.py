import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from municipio.adapters.la_solana import LaSolanaAyuntamientoAdapter, SOURCES, parse_inventory
from municipio.manifest import load_manifest

CATALOG = 'PLAN DE ORDENACION MUNICIPAL. Modificación Catálogo de Bienes y Espacios Protegidos'
ORDINANCE = 'Segunda modificación puntual de las Ordenanzas Municipales de Edificación del Plan de Ordenación de La Solana'
DRAWING = 'Plano Modificación puntual de las Ordenanzas Municipales de Edificación del Plan de Ordenación de La Solana'
POM = 'Modificación Puntual número 2 del Plan de Ordenación Municipal'


def page(documents):
    links = ''.join(f'<p><a href="/wp-content/uploads/{name}.pdf">{title}</a></p>' for name, title in documents)
    return ('<span class="elementor-post-info__item--type-date"><time>4 de mayo de 2026</time></span>'
            '<nav><a href="/unrelated.pdf">Proyecto ajeno</a></nav>'
            f'<div class="als-post-content">{links}</div>')


class LaSolanaTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_inventory(page([('catalog', CATALOG), ('ordinance', ORDINANCE), ('drawing', DRAWING)]), SOURCES[0])
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2])
        self.assertEqual(rows[1]['documentos'][1]['titulo'], DRAWING)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '13079')
            self.assertEqual(row['fecha_publicacion'], '2026-05-04')
            self.assertEqual(row['fecha_publicacion_provenance']['scope'], 'pagina_del_inventario')
            self.assertFalse(row['publication_ready'])
            for absent in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase']:
                self.assertNotIn(absent, row)

    def test_stable_ids_independent_of_document_order(self):
        a = parse_inventory(page([('a', ORDINANCE), ('b', DRAWING)]), SOURCES[0])
        b = parse_inventory(page([('b', DRAWING), ('a', ORDINANCE)]), SOURCES[0])
        self.assertEqual(a, b)
        pom = parse_inventory(page([('pom', POM)]), SOURCES[1])[0]
        self.assertNotEqual(a[0]['id'], pom['id'])

    def test_reject_missing_empty_unrecognised_and_orphan(self):
        for html in ['', page([]), page([('form', 'Solicitud de licencia de obra')]), page([('drawing', DRAWING)])]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCES[0])

    def test_pagination_and_external_documents_fail(self):
        html = page([('pom', POM)])
        for extra in ['<link rel="next" href="?page=2">', '<div class="page-links">2</div>']:
            with self.assertRaises(ValueError):
                parse_inventory(html + extra, SOURCES[1])
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('/wp-content/uploads/', 'https://example.com/'), SOURCES[1])

    def test_failed_second_inventory_preserves_existing_output(self):
        session = Mock()
        session.headers = {}
        response = Mock(url=SOURCES[0], text=page([('catalog', CATALOG)]))
        session.get.side_effect = [response, RuntimeError('source unavailable')]
        with TemporaryDirectory() as temp, patch('municipio.adapters.la_solana.requests.Session') as factory:
            factory.return_value.__enter__.return_value = session
            output = Path(temp) / 'proyectos.jsonl'
            output.write_text('previous output')
            with self.assertRaises(RuntimeError):
                LaSolanaAyuntamientoAdapter('la-solana').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous output')

    def test_manifest_loads_adapter_and_disables_licences(self):
        manifest = load_manifest('la-solana')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.la_solana:LaSolanaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
