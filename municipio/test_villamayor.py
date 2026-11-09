"""Offline parser and complete-snapshot checks for the Villamayor adapter."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villamayor import (
    BASE, SOURCE, VillamayorAyuntamientoAdapter, canonical, page_url,
    parse_files, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def row(doc='11', book='PU', instrument='ED', publication='25/01/2024', agreement='28/12/2023', files=True):
    bulletin = f'<a onclick="doGoBoletin(\'{doc}\', \'37354-PU-x\')">{publication}</a>' if publication else ''
    links = (f'<a href="/PlanPublica/ldoc_files.do;jsessionid=abc?cDocId={doc}">files</a>'
             f'<a href="/PlanPublica/openDocuIndice.do?cDocId={doc}">index</a>') if files else ''
    return (f'<tr><td>{book}</td><td>{instrument}</td><td>{bulletin}</td><td>{agreement}</td>'
            f'<td>ESTUDIO DE DETALLE LOS PÁRAMOS</td><td>{links}</td></tr>')


def page(rows, start=1, total=None):
    end = start + len(rows) - 1
    return ('<table class="cuadroAplicacion">' + ''.join(rows) + '</table>'
            f'<p>Mostrando resultados {start}-{end} de {total or end}</p>')


FILES = '''<h1>Villamayor (Salamanca )</h1><h1>ESTUDIO DE DETALLE</h1>
<table class="cuadroAplicacion">
<tr><td>memoria.pdf</td><td><a href="openFichero.do;jsessionid=abc?cFicheroId=41">PDF</a></td></tr>
<tr><td>planos.pdf</td><td><a href="openFichero.do?cFicheroId=42">PDF</a></td></tr></table>'''


class ParserTests(unittest.TestCase):
    def test_dates_identity_and_document_provenance(self):
        rows, bounds = parse_inventory(page([row()]), page_url(0))
        self.assertEqual(bounds, (1, 1, 1))
        r = rows[0]
        self.assertEqual(r['codigo_ine'], '37354')
        self.assertEqual(r['fecha_publicacion'], '2024-01-25')
        self.assertEqual(r['fecha_acuerdo'], '2023-12-28')
        self.assertNotIn('fecha_aprob', r)
        self.assertNotIn('fase', r)
        self.assertIsNone(r['geometry'])
        self.assertNotIn('jsessionid', r['files_url'])
        self.assertEqual(len(parse_files(FILES, r['files_url'])), 2)
        self.assertEqual(parse_files(FILES, r['files_url'])[0]['procedencia'], r['files_url'])

    def test_missing_dates_and_no_files_are_not_invented(self):
        r = parse_inventory(page([row(publication='', files=True)]), SOURCE)[0][0]
        self.assertIsNone(r['fecha_publicacion'])
        self.assertNotIn('boletin_url', r)
        r = parse_inventory(page([row(files=False)]), SOURCE)[0][0]
        self.assertNotIn('files_url', r)
        self.assertEqual(r['documentacion_status'], 'sin_ficheros_en_archivo')
        self.assertIn('openBoletinDoc.do', r['url'])

    def test_reject_changed_or_truncated_pages(self):
        for html in ['<html>Unavailable</html>', page([row(), row()]),
                     page([row()]).replace('1-1', '1-2'),
                     page([row()]).replace('25/01/2024', '31/02/2024'),
                     page([row()]).replace('cDocId=11', 'cDocId=12')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)

    def test_files_cannot_be_empty_wrong_municipality_or_paginated(self):
        for html in [FILES.replace('Villamayor', 'Villarmayor'), '<h1>Villamayor (Salamanca)</h1>',
                     FILES + '<a>Siguiente</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_files(html, SOURCE)
        with self.assertRaises(ValueError):
            canonical('https://example.com/PlanPublica/ldoc_files.do?cDocId=11')

    def test_complete_pagination_filtering_and_grouped_files(self):
        pages = {SOURCE: 'VILLAMAYOR Código INE: 37354',
                 page_url(0): page([row(), row('12', book='EU', instrument='JC')], total=3),
                 page_url(2): page([row('13', book='GU', instrument='PEX', files=False)], start=3, total=3),
                 BASE + 'ldoc_files.do?cDocId=11': FILES}
        self.run_snapshot(pages, expected_count=2)

    def run_snapshot(self, pages, expected_count=None, failure=False):
        calls = []
        def get(session, url, **kwargs):
            calls.append(url)
            class Response:
                text = pages[url]
                def raise_for_status(self):
                    pass
            response = Response()
            response.url = url
            return response
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get', get), patch('time.sleep'):
            target = Path(tmp) / 'projects.jsonl'
            target.write_text('previous snapshot')
            adapter = VillamayorAyuntamientoAdapter('villamayor')
            if failure:
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(target)
                self.assertEqual(target.read_text(), 'previous snapshot')
            else:
                result = adapter.backfill_proyectos(target)
                rows = [json.loads(line) for line in target.read_text().splitlines()]
                self.assertEqual(len(rows), expected_count)
                self.assertEqual(result['inventory_rows'], 3)
                self.assertEqual(result['excluded_rows'], 1)
                self.assertEqual(len(rows[0]['documentos']), 3)  # bulletin, memory, plans
                self.assertEqual(result['source_urls'], calls)
                self.assertTrue(any('pager.offset=2' in url for url in calls))

    def test_repeated_page_and_changed_total_preserve_previous_snapshot(self):
        pages = {SOURCE: 'VILLAMAYOR Código INE: 37354', page_url(0): page([row()], total=2),
                 page_url(1): page([row()], start=2, total=2)}
        self.run_snapshot(pages, failure=True)
        pages[page_url(1)] = page([row('12')], start=2, total=3)
        self.run_snapshot(pages, failure=True)
        pages[SOURCE] = 'VILLARMAYOR Código INE: 37365'
        self.run_snapshot(pages, failure=True)

    def test_manifest_loader_and_disabled_licences(self):
        manifest = load_manifest('villamayor')
        adapter = load_portal_adapter(manifest)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '37354')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
