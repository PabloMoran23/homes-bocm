import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.baztan import BaztanAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def fixture():
    labels = ['1.1 Memoria informativa', '1.2 Memoria justificativa',
              '2.1 Normas urbanísticas generales', 'PO1. Calificación pormenorizada']
    links = ''.join(f'<p><a href="/wp-content/uploads/2023/08/{i}.pdf">{t}</a></p>'
                    for i, t in enumerate(labels))
    return ('<article><div class="entry-content"><p>Documentos del PEAU de los Cascos de Baztan.</p>'
            '<p><strong>FASE 3: Documento de Aprobación Inicial – Exposición Pública</strong></p>'
            + links + '</div></article>')


class BaztanTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_semantics(self):
        html = fixture().replace('</div>', '<p><a href="/wp-content/uploads/2023/08/0.pdf#page=2">Duplicado</a></p></div>')
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '31050')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        self.assertIn('Aprobación Inicial', row['documentos'][0]['seccion'])
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon'):
            self.assertNotIn(field, row)
        self.assertEqual(parse_inventory(fixture())[0]['id'], row['id'])

    def test_reject_missing_inventory_documents_and_pagination(self):
        for html in ('<html>Not found</html>', fixture().replace('Memoria informativa', 'otro'),
                     fixture().replace('</div>', '<a href="?page=2">Siguiente</a></div>'),
                     fixture() + '<a rel="next" href="/page/2">2</a>',
                     fixture().replace('</div>', '<div class="page-links">2</div></div>'),
                     fixture().replace('/wp-content/uploads/2023/08/0.pdf', 'https://example.org/0.pdf')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_live_method_contract(self):
        manifest = load_manifest('baztan')
        self.assertIsInstance(load_portal_adapter(manifest), BaztanAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '31050')
        for key, flag in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[key][flag], False)
        response = Mock(url=SOURCE, text=fixture(), content=fixture().encode(), headers={'Content-Type': 'text/html'})
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.baztan.requests.get', return_value=response):
            adapter = BaztanAyuntamientoAdapter('baztan')
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['written'], 1)
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 4)
            response.raise_for_status.assert_called_once()
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
