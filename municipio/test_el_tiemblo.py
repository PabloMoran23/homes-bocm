"""Offline parser and traversal regression tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.el_tiemblo import (
    ElTiembloAyuntamientoAdapter, MUNICIPAL, ROOT, SOURCE, canonical,
)
from municipio.manifest import load_manifest

HEAD = '<table class="cuadroAplicacion"><tr>' + ''.join(
    '<th>' + h + '</th>' for h in
    ['Libro', 'Instrumento', 'Fecha de publicación', 'Fecha de acuerdo', 'Título']) + '</tr>'


def item(title, doc='123', book='PU', publication='11/10/2018', agreement='31/05/2017'):
    links = (f'<a href="/PlanPublica/ldoc_files.do;jsessionid=transient?cDocId={doc}">files</a>'
             if doc else '<img alt="No hay documentos">')
    return '<tr>' + ''.join('<td>' + x + '</td>' for x in
        [book, 'NS', publication, agreement, title, links]) + '</tr>'


NEXT = (ROOT + 'searchVPubDocMuniPlau.do?pager.offset=1&municipio=241&provincia=05&bInfoPublica=N')


def page(rows, start=1, end=1, total=1, following=None, identity=True):
    return (('Código INE: 05241' if identity else '') + HEAD + rows + '</table>'
            + f'Mostrando resultados {start}-{end} de {total}'
            + (f'''<a onclick="doResults('results',unescape('{following.replace('&', '%26')}'));return false;">Siguiente »</a>'''
               if following else ''))


FILES = '''<h1>Listado de ficheros</h1><table class="cuadroAplicacion">
<tr><td>normativa.pdf</td><td><a href="/PlanPublica/openFichero.do;jsessionid=abc?cFicheroId=7">Ver</a></td></tr>
<tr><td>planos.pdf</td><td><a href="/PlanPublica/openFichero.do?cFicheroId=8">Ver</a></td></tr></table>'''


class Response:
    def __init__(self, text):
        self.text, self.content = text, text.encode()

    def raise_for_status(self):
        pass


class ElTiembloTests(unittest.TestCase):
    def test_dates_missing_identity_and_pagination(self):
        html = page(item('Modificación puntual'), total=2, following=NEXT)
        rows, span, following = ElTiembloAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(span, (1, 1, 2))
        self.assertEqual(following, NEXT)
        self.assertEqual(rows[0]['fecha_publicacion'], '2018-10-11')
        self.assertEqual(rows[0]['fecha_acuerdo'], '2017-05-31')
        self.assertEqual(rows[0]['archivo_id'], '123')
        self.assertNotIn('jsessionid', rows[0]['url_ficheros'])
        missing = page(item('MODIFICACIÓN PUNTUAL( PTO.24/01)', doc='', publication=''))
        row = ElTiembloAyuntamientoAdapter.parse_inventory(missing)[0][0]
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['archivo_id'])
        self.assertIsNone(row['url_ficheros'])

    def test_fail_closed_on_truncation_and_source_drift(self):
        bad_pages = [page(item('Plan'), total=2),
                     page(item('Plan'), end=2, total=2),
                     page(item('Plan'), total=2, following=NEXT.replace('241', '242')),
                     '<h1>Maintenance</h1>']
        for html in bad_pages:
            with self.subTest(html=html), self.assertRaises(ValueError):
                ElTiembloAyuntamientoAdapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            canonical('https://example.com/PlanPublica/ldoc_files.do?cDocId=1')

    def test_group_files_and_reject_unhandled_file_pagination(self):
        docs = ElTiembloAyuntamientoAdapter.parse_files(FILES)
        self.assertEqual([d['titulo'] for d in docs], ['normativa.pdf', 'planos.pdf'])
        self.assertNotIn('jsessionid', docs[0]['url'])
        for html in [FILES + '<a onclick="pager.offset=15">2</a>', '<h1>Listado de ficheros</h1>']:
            with self.assertRaises(ValueError):
                ElTiembloAyuntamientoAdapter.parse_files(html)

    def test_complete_live_method_traverses_and_preserves_output_on_failure(self):
        # Two pages, one excluded GU row, two source instruments. Attachments
        # become children, missing dates do not borrow the agreement date.
        responses = {
            MUNICIPAL: f'<a href="{SOURCE}">Ver normativa</a>',
            SOURCE: page(item('NORMAS SUBSIDIARIAS'), total=3, following=NEXT),
            NEXT: page(item('Proyecto gestión', '234', 'GU') +
                       item('MODIFICACIÓN PUNTUAL PTO.24/01', '', publication=''),
                       start=2, end=3, total=3, identity=False),
            ROOT + 'ldoc_files.do?cDocId=123': FILES,
        }
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.el_tiemblo.requests.Session.get',
                side_effect=lambda url, **kwargs: Response(responses[url])), patch(
                'municipio.adapters.el_tiemblo.time.sleep'):
            adapter = ElTiembloAyuntamientoAdapter('el-tiemblo')
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual((result['inventory_pages'], result['inventory_rows'], result['rows']), (2, 3, 2))
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[0]['codigo_ine'], '05241')
            self.assertIsNone(rows[1]['fecha_publicacion'])
            self.assertFalse(rows[1]['documentacion_disponible'])
            self.assertIsNone(rows[0]['geometry'])
            self.assertNotIn('fecha_aprob', rows[0])
            old = out.read_text()
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(old, out.read_text())
            responses[NEXT] = page(item('Plan'), start=1, end=1, total=3, following=NEXT)
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(old, out.read_text())
            disabled = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(disabled)['status'], 'disabled')
            self.assertEqual(disabled.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('el-tiemblo')
        self.assertEqual(manifest.provincia, 'Ávila')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.el_tiemblo:ElTiembloAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
