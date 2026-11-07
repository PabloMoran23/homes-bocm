"""Offline parser/contract tests; run with python -m unittest municipio.test_palos_de_la_frontera."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.palos_de_la_frontera import (
    ROOT, PalosDeLaFronteraAyuntamientoAdapter, group_instruments, official_url,
    parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest

TITLE = 'INNOVACIÓN DE PLANEAMIENTO Nº3 DEL PGOUA DE PALOS DE LA FRONTERA'


def inventory(page=1, pages=1, municipality='PALOS DE LA FRONTERA', title=TITLE, number='100'):
    values = ['Órgano ambiental', title, 'HUELVA', '', municipality, '',
              'Resolución de archivo', '10/02/2021', 'EAPU/HU/001/21',
              f'<a href="/medioambiente/daepu/resolucions/{number};jsessionid=temporary">Ver</a>']
    return '<table><tr>' + ''.join('<td>' + v + '</td>' for v in values) + f'</tr><tr class="footer"><td>Página {page} de {pages}</td></tr></table>'


def detail(title=TITLE):
    fields = {'Municipio:': 'PALOS DE LA FRONTERA', 'Provincia:': 'HUELVA',
              'Número de Expediente:': 'EAPU/HU/001/21', 'Actuación:': title}
    html = ''.join(f'<div><label>{k}</label><div class="box">{v}</div></div>' for k, v in fields.items())
    return html + '''<table>
<tr><td>Resolución de archivo</td><td>10/02/2021</td><td><a href="downloadFile/a">Documento</a></td></tr>
<tr><td>Publicación en BOJA (PB)</td><td>24/05/2021</td><td><a href="downloadFile/b">Documento</a></td></tr>
</table>'''


class ParserTests(unittest.TestCase):
    def entry(self):
        return parse_inventory(inventory(), ROOT)[0][0]

    def test_inventory_identity_and_pagination(self):
        entries, page, total = parse_inventory(inventory(2, 3), ROOT)
        self.assertEqual((page, total), (2, 3))
        self.assertEqual(entries[0]['url'], ROOT + 'resolucions/100')
        self.assertEqual(entries[0]['fecha_resolucion'], '2021-02-10')

    def test_wrong_municipality_and_forms_rejected(self):
        for html in [inventory(municipality='LA FRONTERA'), inventory(title='Solicitud de licencia'), '<html>empty</html>']:
            with self.assertRaises(ValueError):
                parse_inventory(html, ROOT)

    def test_documents_keep_date_semantics_and_provenance(self):
        entry = self.entry()
        docs = parse_detail(detail(), entry['url'], entry)
        self.assertEqual(docs[0]['url'], ROOT + 'resolucions/downloadFile/a')
        self.assertEqual(docs[0]['fecha_resolucion'], '2021-02-10')
        self.assertNotIn('fecha_publicacion', docs[0])
        self.assertEqual(docs[1]['fecha_publicacion'], '2021-05-24')
        self.assertNotIn('fecha_resolucion', docs[1])
        self.assertEqual(docs[1]['source_url'], entry['url'])
        for bad in [detail('Other instrument'), detail().replace('PALOS DE LA FRONTERA', 'MOGUER'), detail().split('<table>')[0]]:
            with self.assertRaises(ValueError):
                parse_detail(bad, entry['url'], entry)

    def test_group_shared_numbered_instrument_keep_all_documents(self):
        first = self.entry()
        first['documentos'] = parse_detail(detail(), first['url'], first)
        second = {**first, 'expediente': 'IAE/HU/002/21', 'url': ROOT + 'resolucions/101',
                  'documentos': [{'url': ROOT + 'resolucions/downloadFile/c'}]}
        other = {**first, 'titulo': 'MODIFICACIÓN Nº 2 DEL PLAN GENERAL', 'expediente': 'OTHER', 'documentos': []}
        rows = group_instruments([first, second, other])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(len(rows[0]['resoluciones']), 2)
        for key in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase']:
            self.assertNotIn(key, rows[0])
        self.assertFalse(rows[0]['publication_ready'])

    def test_source_url_rejects_foreign_origin(self):
        with self.assertRaises(ValueError):
            official_url('https://example.com/medioambiente/daepu/1')

    def test_crawler_fetches_all_pages_and_fails_before_replacing_output(self):
        class Response:
            def __init__(self, url, text):
                self.url, self.text = url, text
            def raise_for_status(self):
                pass
        urls = []
        def get(session, url, **kwargs):
            urls.append(url)
            if '/find?' in url:
                page = 2 if 'page=2' in url else 1
                return Response(url, inventory(page, 2, number=str(100 + page)))
            return Response(url, detail())
        adapter = PalosDeLaFronteraAyuntamientoAdapter('palos-de-la-frontera')
        with tempfile.TemporaryDirectory() as d, patch('requests.Session.get', get):
            path = Path(d) / 'rows.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['environmental_cases'], 2)
            self.assertEqual(result['pages'], 2)
            self.assertTrue(any('page=2' in url for url in urls))
            before = path.read_text()
            with patch('requests.Session.get', lambda session, url, **kw: Response(url, inventory(1, 2))):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('palos-de-la-frontera')
        self.assertEqual(manifest.provincia, 'Huelva')
        self.assertFalse(manifest.licencias.enabled)
        adapter = PalosDeLaFronteraAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
