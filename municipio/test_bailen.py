"""Offline parser and crawler tests for the Bailén archive."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.bailen import BailenAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(title, body, nav=''):
    return f'<div class="nav">{nav}</div><div class="content"><h2>{title}</h2>{body}</div>'


class BailenTests(unittest.TestCase):
    def test_plan_groups_all_documents_and_no_inferred_dates(self):
        html = page('P.G.O.U.', '<h3>1. Memoria</h3><a href="pgou/memoria.pdf">Memoria</a>'
                    '<h3>2. Planos</h3><a href="planos/mapa.zip">Planos</a>'
                    '<a href="pgou/memoria.pdf">Duplicado</a>'
                    '<a href="https://other.example/modelo.pdf">Formulario</a>')
        rows, _ = parse_inventory(html, SOURCE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['codigo_ine'], '23010')
        self.assertFalse(any(k.startswith('fecha') for k in rows[0]))
        self.assertNotIn('lat', rows[0])
        self.assertFalse(rows[0]['publication_ready'])

    def test_revisions_keep_documents_and_dates_separate(self):
        html = page('Revisiones del P.G.O.U.',
                    '<h3>1. Revisión Parcial del PGOU en Suelo No Urbanizable</h3>'
                    '<p>Aprobación inicial: Sesión plenaria de fecha 26-10-2012.</p>'
                    '<p>B.O.P. de fecha 13-11-2012 y Diario Jaén de fecha 9-11-2012</p>'
                    '<a href="revision.pdf">Memoria</a><a href="revision.zip">Planos</a>'
                    '<h3>2. Revisión de otro ámbito</h3><a href="otro.pdf">Otra memoria</a><h3></h3>')
        rows, _ = parse_inventory(html, 'https://pgoubailen.es/revisiones.html')
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[0]['fecha_acuerdo'], '2012-10-26')
        self.assertIn('B.O.P. de fecha 13-11-2012', rows[0]['descripcion'])
        self.assertNotIn('fecha_publicacion', rows[0])
        self.assertNotIn('fecha_acuerdo', rows[1])

    def test_modifications_exclude_generic_index(self):
        html = page('Modificaciones del P.G.O.U.', '<ul><li><a href="https://juntadeandalucia.es/index">'
                    'Modificaciones 1995-2006</a></li><li><a href="x.pdf">Modificación puntual X.6.4.</a>'
                    '<a href="x.zip">Planos</a></li><li><a href="y.pdf">Modificación puntual Y</a></li></ul>')
        rows, _ = parse_inventory(html, 'https://pgoubailen.es/modificaciones.html')
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_missing_or_changed_inventory_fails(self):
        for html in ('<html>error</html>', page('P.G.O.U.', ''), page('Licitaciones', '<a href="x.pdf">Obra</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)

    def test_pagination_is_not_silently_ignored(self):
        html = page('P.G.O.U.', '<a href="m.pdf">Memoria</a><a rel="next" href="page2.html">Siguiente</a>')
        self.assertIn('https://pgoubailen.es/page2.html', parse_inventory(html, SOURCE)[1])
        self.assertIn(SOURCE + '?page=2', parse_inventory(html.replace('page2.html', '?page=2'), SOURCE)[1])
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('page2.html', 'https://other.example/page2.html'), SOURCE)

    def test_crawler_follows_pages_and_manifest_loads(self):
        class Response:
            def __init__(self, url, html):
                self.url, self.content = url, html.encode('iso-8859-1')
            def raise_for_status(self):
                pass
        pages = {
            SOURCE: page('P.G.O.U.', '<a href="m.pdf">Memoria</a>', '<a href="adaptacion_parcial.html">Adaptación</a>'),
            'https://pgoubailen.es/adaptacion_parcial.html': page('Adaptación Parcial a la L.O.U.A.', '<a href="a.pdf">Memoria</a>', '<a href="index.html">PGOU</a>'),
        }
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.bailen.requests.Session.get', side_effect=lambda url, **kw: Response(url, pages[url])) as fetch:
            adapter = load_portal_adapter(load_manifest('bailen'))
            self.assertIsInstance(adapter, BailenAyuntamientoAdapter)
            output = Path(tmp) / 'projects.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 2)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 2)


if __name__ == '__main__':
    unittest.main()
