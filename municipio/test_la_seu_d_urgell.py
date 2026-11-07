import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_seu_d_urgell import (
    LaSeuDUrgellAyuntamientoAdapter, ROOT, STARTS, explicit_date, parse_page,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(body, title='PLA ESPECIAL DEL CEMENTIRI'):
    return f'<h1 class="documentFirstHeading">{title}</h1><div id="content-core">{body}</div>'


def detail(extra=''):
    return page('<div id="parent-fieldname-text"><p><a href="/fitxers/memoria.pdf">Memòria</a></p>'
                '<a href="/fitxers/dogc.pdf">Publicació DOGC (03/10/2012)</a>'
                '<a href="/fitxers/acord.pdf">Acord de la Comissió (28/06/2012)</a>' + extra + '</div>')


class ParserTests(unittest.TestCase):
    def test_group_documents_and_preserve_date_scope(self):
        text = detail('<a href="/fitxers/memoria.pdf"></a>')
        text = text.replace('<div id="parent-fieldname-text">', '<time datetime="2026-11-07">07/11/2026</time><div id="parent-fieldname-text">')
        _, _, row = parse_page(text, STARTS[0] + '/instrument')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['fecha_publicacion'], '2012-10-03')
        self.assertEqual(row['documentos'][2]['fecha_acuerdo'], '2012-06-28')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['lat'])

    def test_mobility_dates_are_distinct(self):
        text = detail('<p>El Pla de Mobilitat Urbana Sostenible de la Seu va ser aprovat definitivament pel Ple Municipal del dia 11 de juny de 2012 i publicat al BOP el dia 21 de juny de 2012.</p>')
        row = parse_page(text, STARTS[2])[2]
        self.assertEqual(row['fecha_aprob'], '2012-06-11')
        self.assertEqual(row['fecha_publicacion'], '2012-06-21')

    def test_reject_unusable_and_unexpected_sources(self):
        for text in ['<h1>Login</h1>', page('<p>Sol·licitud de llicència</p>'),
                     page('<div id="parent-fieldname-text"><a href="/formulari">Formulari</a></div>'),
                     page('<div class="tileItem"><a class="stretched-link" href="https://other.invalid">News</a></div>')]:
            with self.assertRaises(ValueError):
                parse_page(text, STARTS[0])
        self.assertEqual(parse_page(page('<p>Actualment no hi ha elements dins d’aquesta carpeta.</p>'), STARTS[0])[2], None)

    def test_inventory_and_pagination_not_records(self):
        child = STARTS[0] + '/plan'
        html = page(f'<div class="tileItem"><a class="stretched-link" href="{child}">Plan</a></div>'
                    '<div class="batchNext"><a href="?b_start:int=20">Següent</a></div>')
        children, following, row = parse_page(html, STARTS[0])
        self.assertEqual(children, [child])
        self.assertEqual(following, [STARTS[0] + '?b_start:int=20'])
        self.assertIsNone(row)

    def test_dates_missing_ambiguous_and_invalid(self):
        for text in ['PGOU 2002', '31/02/2022', '16/11/201 1', '01/01/2020 i 02/02/2021']:
            self.assertIsNone(explicit_date(text))
        self.assertEqual(explicit_date('7 de febrer de 2007'), '2007-02-07')

    def test_snapshot_follows_next_and_failure_preserves_output(self):
        class Response:
            url = STARTS[0]
            def __init__(self, url, text): self.url, self.text = url, text
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield self.text.encode()
        next_url = STARTS[0] + '?b_start:int=20'
        child = STARTS[0] + '/plan'
        sources = {
            STARTS[0]: page('<div class="tileItem"><a class="stretched-link" href="' + child + '">Plan</a></div><a rel="next" href="?b_start:int=20">Next</a>'),
            next_url: page('<div class="tileItem"><a class="stretched-link" href="' + child + '-2">Plan 2</a></div>'),
            child: detail(), child + '-2': detail(),
        }
        adapter = LaSeuDUrgellAyuntamientoAdapter('la-seu-d-urgell')
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.la_seu_d_urgell.STARTS', [STARTS[0]]), patch('requests.Session.get', side_effect=lambda url, **kw: Response(url, sources[url])):
            out = Path(d) / 'proyectos.jsonl'
            report = adapter.backfill_proyectos(out)
            self.assertEqual(report['rows'], 2)
            self.assertIn(next_url, report['source_urls'])
            self.assertEqual(len([json.loads(x) for x in out.read_text().splitlines()]), 2)
            previous = out.read_bytes()
            sources[next_url] = '<h1>Login</h1>'
            with self.assertRaises(ValueError): adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('la-seu-d-urgell')
        self.assertIsInstance(load_portal_adapter(manifest), LaSeuDUrgellAyuntamientoAdapter)
        self.assertEqual(manifest.provincia, 'Lleida')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
