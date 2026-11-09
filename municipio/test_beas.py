"""Pruebas de agrupación, semántica y fallos ante pérdida de cobertura."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.beas import (
    BeasAyuntamientoAdapter, DOCUMENT_ROOT, INVENTORY_URL, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def gallery(title, folder, files=('01-ACUERDO.PDF', '02-MEMORIA.pdf')):
    links = ''.join(f'<tr><td><a href="{DOCUMENT_ROOT}{folder}/{f}">{f}</a></td></tr>' for f in files)
    return f'<div class="sg-download-gallery"><h4>{title}</h4><table>{links}</table></div>'


class BeasTests(unittest.TestCase):
    def test_group_documents_and_preserve_provenance(self):
        html = gallery('00 NNSS 1987', '00-NNSS-1987') + gallery('01 MODIFICACION 01 1993', '01-MODIFICACION-01-1993')
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertTrue(all('/00-NNSS-1987/' in d['url'] for d in rows[0]['documentos']))
        self.assertTrue(all('/01-MODIFICACION-01-1993/' in d['url'] for d in rows[1]['documentos']))
        self.assertEqual(rows[0]['documentos'][0]['source_url'], INVENTORY_URL)
        self.assertEqual(rows[0]['codigo_ine'], '21011')
        for field in ('fecha', 'fecha_acuerdo', 'fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, rows[0])
        self.assertFalse(rows[0]['publication_ready'])

    def test_unrelated_forms_news_and_procurement_excluded(self):
        html = '<a href="obra.pdf">Adjudicación piscina</a>' + gallery('Formulario licencia', 'forms')
        with self.assertRaises(ValueError):
            parse_inventory(html)

    def test_empty_or_missing_inventory_rejected(self):
        for html in ('<html>Error</html>', gallery('00 NNSS 1987', 'empty', ())):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected(self):
        for pager in ('<ul class="pagination"><li>2</li></ul>', '<a href="?page=2" rel="next">2</a>', '<a href="?p=2">Siguiente</a>'):
            with self.subTest(pager=pager), self.assertRaises(ValueError):
                parse_inventory(gallery('00 NNSS 1987', 'nnss') + pager)

    def test_foreign_document_and_mixed_folder_rejected(self):
        valid = gallery('00 NNSS 1987', 'nnss')
        for html in (valid.replace(DOCUMENT_ROOT, 'https://example.org/'), valid.replace('nnss/02-', 'other/02-')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_id_stable_when_documents_reordered(self):
        a = parse_inventory(gallery('00 NNSS 1987', 'nnss'))[0]
        b = parse_inventory(gallery('00 NNSS 1987', 'nnss', ('02-MEMORIA.pdf', '01-ACUERDO.PDF')))[0]
        self.assertEqual(a['id'], b['id'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('beas')
        self.assertEqual(manifest.provincia, 'Huelva')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), BeasAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'licencias.jsonl'
            result = BeasAyuntamientoAdapter('beas').backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')

    @patch('municipio.adapters.beas.requests.get')
    def test_live_path_writes_parsed_response_and_tls_default(self, get):
        html = gallery('07 ADP LOUA 2012', 'adp')
        get.return_value = Mock(url=INVENTORY_URL, text=html, content=html.encode())
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'proyectos.jsonl'
            result = BeasAyuntamientoAdapter('beas').update_proyectos(p, Path(d) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(p.read_text())['titulo'], '07 ADP LOUA 2012')
            self.assertIs(get.call_args.kwargs['verify'], True)


if __name__ == '__main__':
    unittest.main()
