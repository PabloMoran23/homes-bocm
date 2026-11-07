"""Offline parser/adapter tests; fixtures model municipal HTML structure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.sada import (
    BASE, INVENTORY_URL, PACKAGES, SadaAyuntamientoAdapter,
    group_packages, parse_inventory, parse_package,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture(path, extra=''):
    title = {'/plan-xeral-de-ordenacion-municipal': 'Plan xeral de ordenación municipal',
             '/plan-especial-de-veigue': 'Plan Especial de Veigue',
             '/peri-a-lagoa': 'PERI A Lagoa', '/peri-a-canota': 'PERI A Cañota'}[path]
    return (f'<h1>{title}</h1><div class="pagina">'
            f'<a href="{PACKAGES[path]}memoria.pdf">Memoria</a>{extra}</div>'
            '<aside><a href="/archivos/pev/ruido.pdf">Unrelated sidebar</a></aside>')


class SadaTests(unittest.TestCase):
    def test_discovery_deduplicates_and_requires_all_packages(self):
        html = ''.join(f'<a href="{path}">Plan</a>' * 2 for path in PACKAGES)
        self.assertEqual(len(parse_inventory(html)), 4)
        with self.assertRaises(ValueError):
            parse_inventory('<a href="/impresos-urbanismo">Licencias</a>')
        with self.assertRaises(ValueError):
            parse_inventory(html + '<a rel="next" href="?page=2">Next</a>')

    def test_dates_and_partial_approval(self):
        path = '/plan-xeral-de-ordenacion-municipal'
        extra = ('<h2>PXOM Aprobación definitiva (11/10/2017)</h2>'
                 f'<a href="{PACKAGES[path]}dog.pdf">29/11/2017 - Publicación no D.O.G. da orde</a>')
        row = parse_package(fixture(path, extra), BASE + path)
        self.assertEqual(row['fecha_aprob'], '2017-10-11')
        self.assertEqual(row['fecha_publicacion'], '2017-11-29')
        self.assertIn('parcial', row['alcance_aprobacion'])
        self.assertNotIn('fecha_acuerdo', row)
        self.assertEqual(len(row['documentos']), 2)

    def test_crosslinked_document_belongs_to_canota(self):
        path = '/peri-a-lagoa'
        cross = f'<a href="{PACKAGES["/peri-a-canota"]}memoria.pdf">Cañota AD 202408</a>'
        rows = group_packages([parse_package(fixture(p, cross if p == path else ''), BASE + p)
                               for p in PACKAGES])
        by_url = {r['url']: r for r in rows}
        self.assertEqual(len(by_url[BASE + path]['documentos']), 1)
        doc = by_url[BASE + '/peri-a-canota']['documentos'][0]
        self.assertEqual(set(doc['source_urls']), {BASE + path, BASE + '/peri-a-canota'})
        for row in rows:
            if row['url'] != BASE + '/plan-xeral-de-ordenacion-municipal':
                self.assertNotIn('fecha_aprob', row)
            self.assertNotIn('lat', row)
            self.assertNotIn('fase', row)

    def test_all_documents_and_fail_closed(self):
        path = '/peri-a-lagoa'
        docs = ''.join(f'<a href="{PACKAGES[path]}plano{i}.pdf">Plano {i}</a>' for i in range(120))
        row = parse_package(fixture(path, docs), BASE + path)
        self.assertEqual(len(row['documentos']), 121)
        for html in ['<h1>PERI</h1><div class="pagina">Impresos de licencia</div>',
                     fixture(path, '<a rel="next" href="?page=2">2</a>'),
                     fixture(path, '<a href="https://example.org/memoria.pdf">Memoria</a>'),
                     fixture(path, '<a href="/archivos/unknown.pdf">Plan nuevo</a>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_package(html, BASE + path)

    def test_manifest_and_adapter_write(self):
        manifest = load_manifest('sada')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), SadaAyuntamientoAdapter)
        inventory = ''.join(f'<a href="{p}">Plan</a>' for p in PACKAGES)

        def get(url, **kwargs):
            response = Mock(url=url)
            response.text = inventory if url == INVENTORY_URL else fixture(url.removeprefix(BASE))
            return response

        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.sada.requests.get', side_effect=get):
            adapter = SadaAyuntamientoAdapter('sada')
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 4)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len({r['id'] for r in rows}), 4)
            initial = output.read_text()
            adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_text(), initial)
            with self.assertRaises(NotImplementedError):
                adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')


if __name__ == '__main__':
    unittest.main()
