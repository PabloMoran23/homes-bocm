import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alaro import (
    AlaroAyuntamientoAdapter, SOURCE, parse_inventory, parse_documents,
)
from municipio.manifest import load_manifest


def article(body):
    return '<div id="block-consell-main-content"><article><div class="prose">' + body + '</div></article></div>'


INVENTORY = article('''
<p><strong>Planejament definitivament aprovat:</strong></p>
<ul><li>Normes Subsidiàries de Planejament del municipi d’Alaró (A.D. 17.10.2003):</li></ul>
<p><a href="https://www.ajalaro.net/ca/arxius-i-documents/documentacio-escrita">Documentació escrita</a></p>
<p><a href="/ca/arxius-i-documents/planols">Plànols</a></p>
<ul><li><a href="https://drive.google.com/drive/folders/example">Estudis de detall</a></li></ul>
<p>Planejament en revisió/tramitació:</p>
<ul><li><a href="/ca/cataleg-delements-i-espais-protegits">MP consistent en el Catàleg d’elements i espais protegits d’Alaró</a></li></ul>
''')
DOCS = article('''<section class="multimedia--documents">
<div><h3>BOIB núm. 156 de 11.11.2003 - NNSS</h3><span>18/03/2025</span>
<a download href="/files/boib.pdf">Descarregar</a></div>
<div><h3>Normes</h3><a download href="/files/normes.pdf">Descarregar</a></div>
</section>''')
CATALOGUE = article('''<p>Catàleg (Aprovació inicial 28.12.2023)</p>
<a href="https://drive.google.com/drive/folders/catalogue">Documentació Aprovació Inicial</a>''')


class AlaroTests(unittest.TestCase):
    def test_grouping_and_dates(self):
        rows = parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_aprob'], '2003-10-17')
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertIsNone(rows[0]['lat'])
        self.assertEqual(rows[0]['id'], parse_inventory(INVENTORY)[0]['id'])

    def test_reject_empty_navigation_and_forms(self):
        for html in ['<a href="/plan">Normes Subsidiàries</a>', article('<p>Llicència urbanística</p>'),
                     INVENTORY.replace('Normes Subsidiàries de Planejament', 'Sol·licitud de llicència')]:
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(INVENTORY + '<nav class="pager"><a href="?page=1">2</a></nav>')
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_documents(DOCS + '<a rel="next" href="?page=1">Next</a>', SOURCE)

    def test_document_inventory(self):
        docs = parse_documents(DOCS, SOURCE)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]['url'], 'https://ajalaro.net/files/boib.pdf')
        with self.assertRaises(ValueError):
            parse_documents(article('<p>Documents</p>'), SOURCE)

    def test_duplicate_rejected(self):
        duplicate = '<ul><li><a href="/x">MP consistent en el Catàleg d’elements i espais protegits d’Alaró</a></li></ul>'
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            parse_inventory(INVENTORY.replace('</div></article>', duplicate + '</div></article>'))

    def test_snapshot_enrichment_and_failure_preserves_output(self):
        adapter = AlaroAyuntamientoAdapter()
        def fetch(url):
            if url == SOURCE:
                return INVENTORY
            return CATALOGUE if 'cataleg' in url else DOCS
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=fetch):
                result = adapter.backfill_proyectos(output)
                rows = [json.loads(line) for line in output.read_text().splitlines()]
                self.assertEqual(result['live_records'], 2)
                self.assertEqual(rows[0]['fecha_publicacion'], '2003-11-11')
                self.assertEqual(rows[0]['fecha_aprob'], '2003-10-17')
                self.assertIsNone(rows[0]['fecha_acuerdo'])
                self.assertEqual(rows[1]['fase'], 'aprobación inicial')
                self.assertEqual(rows[1]['fecha_aprob'], '2023-12-28')
                self.assertEqual(len(rows[0]['documentos']), 4)
                before = output.read_bytes()
                adapter.update_proyectos(output, Path(tmp) / 'state.json')
                self.assertEqual(before, output.read_bytes())
            with patch.object(adapter, '_fetch', return_value='<p>Login</p>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(before, output.read_bytes())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('alaro')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp, patch('requests.get') as get:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(AlaroAyuntamientoAdapter().backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')
            get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
