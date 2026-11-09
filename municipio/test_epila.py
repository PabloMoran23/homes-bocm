import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.epila import (
    SOURCE, EpilaAyuntamientoAdapter, make_record, official_url, parse_page,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(*links):
    return '<table>' + ''.join('<tr><td class="class_name">' + a + '</td></tr>' for a in links) + '</table>'


def doc(key, title):
    return f'<a class="gIconLink" href="/preview-document/{key}" title="Original">{title}</a>'


def folder(key, title, count):
    return (f'<a class="gIconLink exp" href="#" onclick="wicketAjaxGet(\'?x={key}\')">'
            f'{title}<span> ( {count} )</span></a>')


class Response:
    def __init__(self, url, text='', headers=None):
        self.url, self.text, self.headers = url, text, headers or {}
        self.content = text.encode()

    def raise_for_status(self):
        pass


class EpilaTests(unittest.TestCase):
    def run_inventory(self, count=2):
        child = 'https://epila.sedelectronica.es/transparency/plan/'
        root = page(doc('nnss', 'BOP Z 188 1995.08.17 Normas subsidiarias de planeamiento de Épila'),
                    folder('plan', 'INFORMACION PUBLICA APROBACION PLAN PARCIAL AZUCARERA', count))
        responses = {
            SOURCE: Response(SOURCE, root),
            SOURCE + '?x=plan': Response(SOURCE + '?x=plan', headers={'Ajax-Location': child}),
            child: Response(child, page(doc('memoria', '1-MEMORIA'), doc('planos', '6-PLANOS'))),
        }
        adapter = EpilaAyuntamientoAdapter('epila')
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.epila.requests.Session') as session:
            session.return_value.get.side_effect = lambda url, **kwargs: responses[url]
            path = Path(directory) / 'records.jsonl'
            result = adapter.backfill_proyectos(path)
            records = [json.loads(line) for line in path.read_text().splitlines()]
        return result, records

    def test_grouping_and_dates(self):
        result, rows = self.run_inventory()
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['document_count'], 3)
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertEqual(rows[1]['documentos'][0]['titulo'], '1-MEMORIA')
        self.assertEqual(rows[1]['documentos'][1]['titulo'], '6-PLANOS')
        self.assertEqual(rows[0]['fecha_publicacion'], '1995-08-17')
        self.assertNotIn('fecha_publicacion', rows[1])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '50099')
            self.assertFalse(row['publication_ready'])
            for field in ('fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(field, row)
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in self.run_inventory()[1]])

    def test_count_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            self.run_inventory(count=3)

    def test_pagination_rejected(self):
        for pager in ('<a rel="next" href="?page=2">2</a>',
                      '<a href="#">Mostrar más</a>', '<div class="pagination">1 2</div>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_page(page(doc('x', 'Plan')) + pager)

    def test_empty_unknown_and_broken_folder_rejected(self):
        for html in ('<h1>Login</h1>', page('<a href="form.pdf">Solicitud licencia</a>'),
                     page('<a class="gIconLink exp">Plan (8)</a>')):
            with self.assertRaises(ValueError):
                parse_page(html)

    def test_document_provenance_and_no_synthetic_instrument(self):
        entry = parse_page(page(doc('one', 'Memoria')))[0]
        self.assertEqual(entry['descripcion'], 'Original')
        with self.assertRaises(ValueError):
            make_record('Plan', SOURCE, [])
        with self.assertRaises(ValueError):
            official_url(SOURCE, 'https://other.example/document')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('epila')
        self.assertEqual(manifest.nombre, 'Épila')
        self.assertEqual(manifest.provincia, 'Zaragoza')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, EpilaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
