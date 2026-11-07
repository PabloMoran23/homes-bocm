import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.verin import (
    SOURCE, VerinAyuntamientoAdapter, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def card(url='https://urbanismo.verin.gal/apr45/apr45.html'):
    return f'''<a data-cvu-folla href="{url}"><h3 class="cvu__folla-tit">PERI APR-45</h3>
    <p class="cvu__desc">Documento para consulta, 2023</p></a>'''


def file_inventory():
    arrays = [
        ['C:/PLAN*0*123', 0, '1'],
        ['C:/PLAN/01.MX*0*123', 'memoria #á.pdf*20*123', 'anexo.pdf*30*123', 50, ''],
    ]
    return ('<script>var sourceRoot = "C:/PLAN";\nvar numberOfFiles = 2;\n'
            'var linkRoot = "";\nvar linkProtocol = "";\n' +
            '\n'.join('D.p(' + json.dumps(a) + ')' for a in arrays) +
            '\n</script><div class="app_header_stats">2 files in 2 folders</div>')


class VerinTests(unittest.TestCase):
    def test_inventory_deduplicates_and_preserves_semantics(self):
        rows = parse_inventory(card() + card())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['codigo_ine'], '32085')
        self.assertEqual(rows[0]['descripcion'], 'Documento para consulta, 2023')
        self.assertFalse(rows[0]['vigencia_verificada'])
        self.assertFalse(any(k.startswith('fecha') for k in rows[0]))
        self.assertNotIn('lat', rows[0])
        with self.assertRaises(ValueError):
            parse_inventory(card('https://example.org/plan'))

    def test_all_files_and_encoded_source_links(self):
        docs = parse_documents(file_inventory(), 'https://urbanismo.verin.gal/plan/plan.html')
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]['url'], 'https://urbanismo.verin.gal/plan/01.MX/memoria%20%23%C3%A1.pdf')
        self.assertEqual(docs[0]['bytes'], 20)
        self.assertFalse(any(k.startswith('fecha') for d in docs for k in d))

    def test_fail_closed_on_missing_data_and_pagination(self):
        for html in ['', file_inventory().replace('numberOfFiles = 2', 'numberOfFiles = 3'),
                     file_inventory().replace('2 folders', '3 folders'),
                     file_inventory().replace('D.p(', 'other(')]:
            with self.assertRaises(ValueError):
                parse_documents(html, SOURCE)
        for html in ['<p>No catalogue</p>', card() + '<a rel="next" href="?page=2">2</a>',
                     card() + '<span class="cvu__conta">2 documentos</span>',
                     card() + '<div class="pagination"><a href="?page=2">2</a></div>']:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_adapter_groups_documents_and_reports_exclusions(self):
        adapter = VerinAyuntamientoAdapter('verin')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[
                card() + card('https://urbanismo.verin.gal/pxom2012'), file_inventory()
            ]):
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(result['catalogue_records'], 2)
            self.assertEqual(len(result['excluded']), 1)
            self.assertEqual(len(json.loads(out.read_text())['documentos']), 2)
            before = out.read_text()
            with patch.object(adapter, '_fetch', side_effect=[card(), '<p>Broken</p>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), before)
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        m = load_manifest('verin')
        self.assertEqual(m.provincia, 'Ourense')
        self.assertEqual(m.portal.adapter, 'municipio.adapters.verin:VerinAyuntamientoAdapter')
        self.assertFalse(m.licencias.enabled)
        raw = load_yaml(m.path)
        self.assertEqual(raw['codigo_ine'], '32085')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
