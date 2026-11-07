import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_rapita import LaRapitaAyuntamientoAdapter, parse_projects

# Minimal representative source structure; intentionally independent of local evidence.
HTML = '''<h1>Seu electrònica de La Ràpita</h1>
<div class="llistatAnuncisUrbanisme"><div class="resultatsLlistat">1 publicació</div>
<div class="dElementPublicacioDefecte"><div class="titol">POUM</div>
<div>24/01/2012 14:33 - <a class="registreLink" href="/registrePublic/registrePublicacio/53">Registre de publicació</a></div>
<div class="top"><p>Pla d'Ordenació Urbana Municipal, publicades les normes al DOGC de 12 de maig de 2014</p>
<p><span>Aprovació inicial:</span> Ple 12.07.2012</p>
<p><span>Aprovació provisional:</span> Ple 26.09.2013</p>
<p><span>Aprovació definitiva:</span> CTUTE 04.02.2014</p></div>
<div class="documentsAdjunts"><a href="/documentPublic/download/490">Normativa urbanística</a>
<a href="/documentPublic/download/492">Plànols</a></div></div></div>'''


class LaRapitaTests(unittest.TestCase):
    def test_dates_and_grouped_provenance(self):
        rows = parse_projects(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['fecha_aprob'], '2014-02-04')
        self.assertEqual(row['fecha_publicacion'], '2014-05-12')
        self.assertEqual(row['fecha_registro_publicacion'], '2012-01-24')
        self.assertEqual(row['fecha_aprobacion_inicial'], '2012-07-12')
        self.assertEqual(row['fecha_aprobacion_provisional'], '2013-09-26')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['url'].startswith('https://seu.larapita.cat/documentPublic/') for d in row['documentos']))
        self.assertIsNone(row['lat'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])

    def test_empty_pagination_widget_is_not_another_page(self):
        html = HTML.replace('</div></div>', '<div class="paginateButtons"></div></div></div>')
        self.assertEqual(len(parse_projects(html)), 1)

    def test_missing_dates_are_not_inferred(self):
        row = parse_projects(HTML.replace('04.02.2014', '').replace('12 de maig de 2014', ''))[0]
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_refuses_truncated_or_paginated_inventory(self):
        for html in [HTML.replace('1 publicació', '2 publicacions'),
                     HTML.replace('</div></div>', '<a rel="next" href="?offset=1">Next</a></div></div>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_refuses_navigation_forms_and_missing_documents(self):
        for html in ['<h1>Seu electrònica de La Ràpita</h1><a>POUM</a>',
                     HTML.replace('POUM</div>', 'Sol·licitud de llicència</div>'),
                     HTML.replace('documentsAdjunts', 'unrelated')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_refuses_wrong_municipality_or_external_documents(self):
        for html in [HTML.replace('La Ràpita', 'Manlleu'),
                     HTML.replace('/documentPublic/download/490', 'https://example.com/fake.pdf')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_stable_identity_and_document_deduplication(self):
        row = parse_projects(HTML)[0]
        changed = parse_projects(HTML.replace('Normativa urbanística', 'Normativa actualitzada'))[0]
        self.assertEqual(row['id'], changed['id'])
        duplicate = HTML.replace('</div></div></div>', '<a href="/documentPublic/download/490">duplicate</a></div></div></div>')
        self.assertEqual(len(parse_projects(duplicate)[0]['documentos']), 2)

    def test_live_contract_with_mock_transport_and_disabled_licences(self):
        adapter = LaRapitaAyuntamientoAdapter('la-rapita')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch('municipio.adapters.la_rapita.requests.get') as get:
                response = get.return_value.__enter__.return_value
                response.status_code = 200
                response.headers = {'Content-Type': 'text/html; charset=utf-8'}
                response.iter_content.return_value = [HTML.encode()]
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
                self.assertEqual(result['rows'], 1)
                self.assertEqual(json.loads(out.read_text())['codigo_ine'], '43136')
                self.assertTrue(get.call_args.kwargs['verify'])
                self.assertFalse(get.call_args.kwargs['allow_redirects'])
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
