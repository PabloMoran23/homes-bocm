import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.eskoriatza import EskoriatzaAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def page(title, body):
    return f'<div id="content"><div class="c1"><h1>{title}</h1>{body}</div></div>'


ROOT = page('Normas Subsidiarias', '''
<p>El Consejo adoptó, en sesión de 23 de julio de 2002, varios acuerdos.</p>
<a href="http://eskoriatza.eus/wp-content/uploads/2013/07/texto.pdf">Texto Refundido de las Normas Subsidiarias de Planeamiento de Eskoriatza</a>
<a href="http://eskoriatza.eus/es/ayuntamiento/normativa/normas-subsidiarias/sorautz/">Mocificación puntual en Sorautz</a>
<a href="/es/ayuntamiento/normativa/normas-subsidiarias/sorautz/">Mocificación puntual en Sorautz</a>
<a href="/es/ayuntamiento/normativa/normas-subsidiarias/santa-ana/">Modificación puntual en Santa Ana</a>
''')
DETAIL = page('Sorautz', '''<h2>Memoria</h2>
<a href="http://eskoriatza.eus/wp-content/uploads/2013/11/memoria.pdf">Memoria</a>
<a href="http://eskoriatza.eus/wp-content/uploads/2013/11/memoria.pdf">Duplicado</a>
<p><strong>Planos definitivos</strong></p>
<a href="/wp-content/uploads/2013/11/plano.pdf">Plano 1</a>
<h2>Acuerdos</h2>
<a href="https://ssl4.gipuzkoa.net/castell/bog/2012/01/31/c1200904.pdf">Aprobación definitiva</a>''')


class ParserTests(unittest.TestCase):
    def test_inventory_deduplicates_and_keeps_agreement_semantics(self):
        row, children = Adapter.parse_inventory(ROOT)
        self.assertEqual(len(children), 2)
        self.assertEqual(row['fecha_acuerdo'], '2002-07-23')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['codigo_ine'], '20034')
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 1)

    def test_document_grouping_provenance_and_no_dates_from_paths(self):
        url = SOURCE + 'sorautz/'
        row = Adapter.parse_detail(DETAIL, url, 'Mocificación puntual en Sorautz')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['seccion'], 'Planos definitivos')
        self.assertEqual(row['documentos'][0]['source_url'], url)
        self.assertTrue(row['documentos'][0]['url'].startswith('https:'))
        self.assertTrue(row['documentos'][0]['url_original'].startswith('http:'))
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertNotIn('fase', row)
        changed = Adapter.parse_detail(DETAIL.replace('Plano 1', 'Plano nuevo'), url, 'Mocificación puntual en Sorautz')
        self.assertEqual(row['id'], changed['id'])

    def test_unlinked_document_names_are_not_fabricated_links(self):
        row = Adapter.parse_detail(page('Santa Ana', '<h2>Memoria</h2><li>Documento Modificación de Norma</li>'), SOURCE + 'santa-ana/', 'Modificación puntual en Santa Ana')
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentacion_status'], 'sin_enlaces_documentales')

    def test_pagination_and_missing_content_fail(self):
        for suffix in ['<a rel="next" href="?page=2">2</a>', '<div class="wp-pagenavi"><a href="?paged=2">2</a></div>', '<a href="?p=2">Siguiente</a>']:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(ROOT + suffix)
        for html in ['<html>Login</html>', page('Normas Subsidiarias', '<p>Vacío</p>')]:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_unknown_links_and_mismatched_details_fail(self):
        html = page('Sorautz', '<a href="/new-document.docx">Documento</a>')
        with self.assertRaises(ValueError):
            Adapter.parse_detail(html, SOURCE + 'sorautz/', 'Mocificación puntual en Sorautz')
        with self.assertRaises(ValueError):
            Adapter.parse_detail(DETAIL, SOURCE + 'santa-ana/', 'Modificación puntual en Santa Ana')

    def test_live_fetch_path_groups_children_and_failure_preserves_output(self):
        class Response:
            headers = {'Content-Type': 'text/html; charset=UTF-8'}
            def __init__(self, url, html):
                self.url, self.text = url, html
            def raise_for_status(self):
                pass
        pages = {SOURCE: ROOT, SOURCE + 'sorautz/': DETAIL,
                 SOURCE + 'santa-ana/': page('Santa Ana', '<h2>Memoria</h2>')}
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'proyectos.jsonl'
            adapter = Adapter('eskoriatza')
            with patch('municipio.adapters.eskoriatza.requests.Session.get', side_effect=lambda url, **kw: Response(url, pages[url])) as get:
                result = adapter.backfill_proyectos(out)
                self.assertEqual(result['rows'], 3)
                self.assertEqual(get.call_count, 3)
            previous = out.read_bytes()
            with patch('municipio.adapters.eskoriatza.requests.Session.get', side_effect=RuntimeError('network')):
                with self.assertRaises(RuntimeError):
                    adapter.update_proyectos(out, Path(temp) / 'state.json')
            self.assertEqual(out.read_bytes(), previous)
            self.assertEqual(adapter.backfill_licencias(Path(temp) / 'lic.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest('eskoriatza')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '20034')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
