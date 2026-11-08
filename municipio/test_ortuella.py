import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ortuella import (
    AREA, BASE, INVENTORY, OrtuellaAyuntamientoAdapter, parse_inventory, parse_page,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def item(n, title, filename):
    return {'Id': n, 'Title': title, 'FileRef': AREA + 'Paginas/' + filename,
            'Modified': '2025-09-30T08:35:55Z'}


def page(text, links):
    return '<div id="centerColumn"><h3>' + text + '</h3>' + ''.join(
        f'<a href="{url}">{title}</a>' for title, url in links) + '</div>'


class OrtuellaTests(unittest.TestCase):
    def test_document_provenance_and_scope(self):
        url = BASE + AREA + 'Paginas/PGOU.aspx'
        html = '<nav><a href="/unrelated.pdf">Outside</a></nav>' + page('PGOU', [
            ('Memoria', '../aprobacion_inicial_textos/memoria con ñ.pdf'),
            ('Memoria', '../aprobacion_inicial_textos/memoria con ñ.pdf'),
            ('Planos', 'planos.aspx'), ('External', 'https://example.com/file.pdf')])
        text, docs, children = parse_page(html, url)
        self.assertEqual(len(docs), 1)
        self.assertIn('memoria%20con%20%C3%B1.pdf', docs[0]['url'])
        self.assertEqual(docs[0]['source_page'], url)
        self.assertEqual(children, {BASE + AREA + 'Paginas/planos.aspx'})

    def test_changed_content_and_uncovered_pagination_fail(self):
        for html in ('<h1>Login</h1>', page('Plan', [('Siguiente', '?page=2')])):
            with self.assertRaises(ValueError):
                parse_page(html, BASE)
        with self.assertRaises(ValueError):
            parse_inventory({'error': 'Access denied'})

    def test_municipal_layout_variants(self):
        for wrapper in ('<div id="centerColumn">{}</div>',
                        '<div id="ProcedureContent">{}</div>',
                        '<div id="MainContent"><div class="CenterZone">{}</div></div>'):
            html = wrapper.format('<h3>Memoria</h3><a href="/plan.pdf">Plan</a>')
            self.assertEqual(len(parse_page(html, BASE)[1]), 1)

    def test_pagination_grouping_and_dates(self):
        pgou = item(5, 'PGOU', 'PGOU.aspx')
        cat = item(6, 'Catálogo de patrimonio', 'cat.aspx')
        landscape = item(7, 'Plan de acción del paisaje de Ortuella', 'paisaje.aspx')
        child = item(22, 'Planos', 'planos.aspx')
        form = item(3, 'Otorgamiento', 'form.aspx')
        next_url = INVENTORY + '&$skiptoken=5'
        responses = {
            INVENTORY: {'value': [pgou, form], 'odata.nextLink': next_url},
            next_url: {'value': [cat, landscape, child]},
            BASE + pgou['FileRef']: page('Documento aprobación inicial', [
                ('Memoria', '../aprobacion_inicial_textos/m.pdf'), ('Planos', 'planos.aspx')]),
            BASE + child['FileRef']: page('Planos', [('Plano', '../planos/plano.pdf'), ('Volver', 'PGOU.aspx')]),
            BASE + cat['FileRef']: page('Catálogo', [('Memoria', '../catalogo/m.pdf')]),
            BASE + landscape['FileRef']: page('Paisaje', [('Memoria', '../paisaje/m.pdf')]),
        }
        adapter = OrtuellaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as d, patch.object(adapter, '_fetch', side_effect=lambda u, **kw: responses[u]) as fetch:
            out = Path(d) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(out)['rows'], 3)
            rows = [json.loads(s) for s in out.read_text().splitlines()]
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[0]['fase'], 'documentación de aprobación inicial')
            self.assertTrue(all(r['fecha_aprob'] is None and r['fecha_publicacion'] is None for r in rows))
            self.assertTrue(all(r['geometry'] is None for r in rows))
            self.assertFalse(any(c.args[0].endswith('form.aspx') for c in fetch.call_args_list))
            before = out.read_bytes()
            responses[next_url] = {'value': [], 'odata.nextLink': next_url}
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('ortuella')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('48083', 'Bizkaia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'licencias.jsonl'
            result = load_portal_adapter(manifest).backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
