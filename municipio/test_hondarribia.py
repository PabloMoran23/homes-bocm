"""Offline semantic/parser checks; run with python -m unittest municipio.test_hondarribia."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.hondarribia import HondarribiaAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def page(body):
    return '<div id="content">' + body + '</div>'


def doc(title='Memoria', uuid='unique', query='?v=1'):
    return f'<a href="/documents/124308/42650235/file.pdf/{uuid}{query}">{title}</a>'


class HondarribiaTests(unittest.TestCase):
    def test_inventory_requires_both_supported_instruments(self):
        body = 'Recursos Geográficos y de Urbanismo'
        body += '<a href="/es/hapo/contenido-aprobacion-provisional-plan">VER</a>'
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(page(body))
        body += '<a href="/es/plan-director-muralla-hondarribia">VER</a>'
        body += '<a href="/es/plan-general-ordenacion-urbana-pgou">No vigente</a>'
        self.assertEqual(set(Adapter.parse_inventory(page(body))), {'pgou', 'muralla'})

    def test_approval_narrative_not_document_label_date(self):
        html = page('El Pleno acordó la aprobación provisional del PGOU en la sesión del 19 de junio de 2025.' + doc('27-07-2026 Informe definitivo de la COTPV'))
        row = Adapter.parse_instrument('pgou', html, SOURCE)
        self.assertEqual(row['fecha_acuerdo'], '2025-06-19')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])
        self.assertEqual(row['fase'], 'aprobación provisional')
        self.assertIsNone(row['geometry'])
        with self.assertRaises(ValueError):
            Adapter.parse_instrument('pgou', page(doc()), SOURCE)

    def test_documents_grouped_deduplicated_and_provenance_retained(self):
        html = page('Plan Director Muralla de Hondarribia'
                    '<div class="relacionados_descarga"><p class="titulo">Fase 1</p>'
                    + doc() + doc(query='?v=2') + '</div>'
                    '<div class="relacionados_descarga"><p class="titulo">Fase 3</p>'
                    + doc(uuid='another') + '</div>')
        row = Adapter.parse_instrument('muralla', html, SOURCE)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['seccion'], 'Fase 3')
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        self.assertTrue(row['documentos'][0]['url'].endswith('?v=1'))
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])

    def test_reject_changed_source_pagination_and_external_documents(self):
        for html in ['<h1>Login</h1>', page('<a href="?page=2">2</a>'),
                     page('<a rel="next" href="/next">Continue</a>'),
                     page('<a href="https://example.com/documents/test">Memoria</a>'),
                     page('No documents')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_documents(html, SOURCE)

    def test_licences_disabled_and_manifest_loads(self):
        manifest = load_manifest('hondarribia')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '20036')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = Adapter('hondarribia').backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
