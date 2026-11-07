"""Offline parser, pagination and instrument-boundary tests (no live dependency)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from municipio.adapters.torredonjimeno import (
    SOURCE, TorredonjimenoAyuntamientoAdapter, action_url, apply_ajax,
    make_record, official_url, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml

DOC = 'https://tosiria.sedelectronica.es/preview-document/'
CHILD = 'https://tosiria.sedelectronica.es/transparency/11111111-1111-1111-1111-111111111111/'


def doc(number, title):
    return f'<tr><td><a class="gIconLink" href="{DOC}{number:08d}-1111-1111-1111-111111111111">{title}</a></td></tr>'


def folder(title, count, token):
    return f'''<tr><td><a class="gIconLink exp" href="#" onclick="wicketAjaxGet('?x={token}')">{title}<span> ( {count} )</span></a></td></tr>'''


def table(rows):
    return '<table><tbody id="rows">' + rows + '</tbody></table>'


MORE = '''<div class="more_results" id="more"><button onclick="wicketAjaxGet('?x=next')">Mostrar más</button></div>'''


def ajax(*components):
    return '<ajax-response>' + ''.join(
        f'<component id="{key}"><![CDATA[{html}]]></component>' for key, html in components
    ) + '</ajax-response>'


class Response:
    def __init__(self, url, text='', headers=None):
        self.url, self.text, self.headers, self.status_code = url, text, headers or {}, 200

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses, self.headers, self.calls = responses, {}, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        self.calls.append(url)
        response = self.responses[url]
        return response.pop(0) if isinstance(response, list) else response


class TorredonjimenoTests(unittest.TestCase):
    def test_manifest_identity_and_safety(self):
        manifest = load_manifest('torredonjimeno')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('23087', 'Torredonjimeno', 'Jaén'))
        for section, key in [('schedule', 'enabled'), ('licencias', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[section][key], False)
        self.assertEqual(manifest.portal.base_url, SOURCE)

    def test_parse_only_inventory_links_preserve_provenance(self):
        html = '<a href="/bad">Licencia de obra</a>' + table(
            doc(1, 'MEMORIA AVANCE DE PLANEAMIENTO &amp; planos') +
            folder('PLAN DE ORDENACIÓN', 44, 'open'))
        documents, folders = parse_inventory(html, SOURCE)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]['inventory_url'], SOURCE)
        self.assertEqual(documents[0]['titulo'], 'MEMORIA AVANCE DE PLANEAMIENTO & planos')
        self.assertEqual(folders[0]['count'], 44)
        self.assertEqual(folders[0]['titulo'], 'PLAN DE ORDENACIÓN')

    def test_invalid_links_and_navigation(self):
        for url in ['https://example.org/preview-document/123', 'http://tosiria.sedelectronica.es/']:
            with self.assertRaises(ValueError):
                official_url(url)
        with self.assertRaises(ValueError):
            parse_inventory(table('<a class="gIconLink" href="/formulario">Licencia</a>'), SOURCE)
        with self.assertRaises(ValueError):
            action_url(BeautifulSoup('<a/>', 'html.parser').a, SOURCE)

    def test_ajax_appends_documents_and_removes_pagination(self):
        soup = BeautifulSoup(table(doc(1, 'Memoria')) + MORE, 'html.parser')
        result = apply_ajax(soup, ajax(('new-row', doc(2, 'Plano')), ('more', '<div id="more"></div>')))
        documents, _ = parse_inventory(str(result), SOURCE)
        self.assertEqual(len(documents), 2)
        self.assertFalse(result.select('.more_results button'))
        with self.assertRaises(ValueError):
            apply_ajax(result, '<ajax-response/>')

    def responses(self, child_count=2, pagination=None):
        root = table(doc(1, 'MEMORIA AVANCE DE PLANEAMIENTO ASENTAMIENTOS') +
                     doc(2, 'Asentamientos 1. PLANO') + folder('PLAN DE ORDENACIÓN URBANA', child_count, 'open'))
        child = table(doc(3, 'ÍNDICE GENERAL')) + MORE
        next_page = pagination or ajax(('new', doc(4, 'ACUERDO DE JGL DE APROBACIÓN INICIAL')),
                                      ('more', '<div id="more"></div>'))
        return {SOURCE: Response(SOURCE, root),
                SOURCE + '?x=open': Response(SOURCE + '?x=open', headers={'Ajax-Location': CHILD}),
                CHILD: Response(CHILD, child),
                CHILD + '?x=next': Response(CHILD + '?x=next', next_page)}

    def test_live_path_groups_instruments_and_completes_pagination(self):
        session = FakeSession(self.responses())
        adapter = TorredonjimenoAyuntamientoAdapter('torredonjimeno')
        with tempfile.TemporaryDirectory() as tmp, patch(
            'municipio.adapters.torredonjimeno.requests.Session', return_value=session
        ):
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual(result['documents'], 4)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(rows[1]['url'], CHILD)
        self.assertEqual(rows[1]['documentos'][1]['titulo'], 'ACUERDO DE JGL DE APROBACIÓN INICIAL')
        self.assertIn(CHILD + '?x=next', session.calls)
        for row in rows:
            for key in ['fecha', 'fecha_acuerdo', 'fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'fase']:
                self.assertNotIn(key, row)

    def test_reused_wicket_callback_advances_until_hidden(self):
        responses = self.responses()
        responses[CHILD + '?x=next'] = [
            Response(CHILD + '?x=next', ajax(('new', doc(4, 'Plano')), ('more', MORE))),
            Response(CHILD + '?x=next', ajax(('more', '<div id="more" style="display:none"></div>'))),
        ]
        session = FakeSession(responses)
        with tempfile.TemporaryDirectory() as tmp, patch(
            'municipio.adapters.torredonjimeno.requests.Session', return_value=session
        ):
            result = TorredonjimenoAyuntamientoAdapter('torredonjimeno').backfill_proyectos(Path(tmp) / 'out.jsonl')
        self.assertEqual(result['documents'], 4)
        self.assertEqual(session.calls.count(CHILD + '?x=next'), 2)

    def test_count_mismatch_and_stuck_pagination_never_write_partial(self):
        cases = [self.responses(child_count=3), self.responses(pagination=ajax(('more', MORE)))]
        for responses in cases:
            with self.subTest(), tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.torredonjimeno.requests.Session', return_value=FakeSession(responses)
            ):
                out = Path(tmp) / 'proyectos.jsonl'
                out.write_text('previous complete snapshot')
                with self.assertRaises(ValueError):
                    TorredonjimenoAyuntamientoAdapter('torredonjimeno').backfill_proyectos(out)
                self.assertEqual(out.read_text(), 'previous complete snapshot')

    def test_missing_inventory_rejected(self):
        with patch('municipio.adapters.torredonjimeno.requests.Session', return_value=FakeSession(
            {SOURCE: Response(SOURCE, '<html>Maintenance</html>')}
        )):
            with self.assertRaises(ValueError):
                TorredonjimenoAyuntamientoAdapter('torredonjimeno').backfill_proyectos(Path('/tmp/unused-torredonjimeno.jsonl'))

    def test_document_identity_and_disabled_licences(self):
        docs = [{'titulo': 'Memoria', 'url': DOC + 'example'}]
        self.assertEqual(make_record('A', CHILD, docs)['id'], make_record('B', CHILD, docs)['id'])
        with self.assertRaises(ValueError):
            make_record('A', CHILD, [])
        with self.assertRaises(NotImplementedError):
            TorredonjimenoAyuntamientoAdapter('torredonjimeno').backfill_licencias(Path('/tmp/unused.jsonl'))


if __name__ == '__main__':
    unittest.main()
