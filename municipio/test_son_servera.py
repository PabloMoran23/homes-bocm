import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.son_servera import (
    SOURCE, SonServeraAyuntamientoAdapter, discover, documents, revision_links,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(title, text):
    return f'<div id="interior_cuerpo"><h2>{title}</h2><div class="interior_texto">{text}</div></div>'


def table(number, entries, total=None):
    rows = ''.join(
        f'<tr><td><a class="linkTb01" href="ficha?contenido={i}">{title}</a></td>'
        f'<td><a href="RecursosWeb/DOCUMENTOS/1/{i}.pdf"><img></a></td></tr>'
        for i, title in entries)
    return (f'<table class="listado"><tr><td><h3>Modificación {number} NNSS</h3></td></tr>{rows}</table>'
            f'<div class="paginacion">{len(entries) if total is None else total} contenidos</div>')


class SonServeraTests(unittest.TestCase):
    def test_discovery_excludes_forms_procurement_and_unrelated_news(self):
        menu = page('Urbanismo y vivienda', '') + (
            '<a href="nnss">Normas Subsidiarias</a>'
            '<a href="mod1">Modificación núm. 1 de NNSS</a>'
            '<a href="form">Solicitud licencia obra mayor</a>'
            '<a href="contract">Anuncio de licitación</a>'
            '<a href="news">Fiestas</a>')
        self.assertEqual(len(discover(menu)), 2)
        with self.assertRaises(ValueError):
            discover('<h2>Login</h2>')

    def test_cross_listed_instrument_uses_section_not_page(self):
        html = page('Modificación núm. 6 de NNSS', table(7, [('7', 'Memoria modificación 7')]))
        pairs, _, approval = documents(html, SOURCE)
        self.assertEqual(pairs[0][0], 'modificacion-7')
        self.assertEqual(pairs[0][1]['titulo'], 'Memoria modificación 7')
        self.assertIsNone(approval)

    def test_pagination_and_missing_document_fail(self):
        for html in (
            page('Modificación núm. 1 de NNSS', table(1, [('1', 'Memoria')], 2)),
            page('Modificación núm. 1 de NNSS', table(1, [('1', 'Memoria')]) +
                 '<div class="paginacion"><a href="page2">2</a></div>'),
            page('Modificación núm. 1 de NNSS', table(1, [('1', 'Memoria')]).replace('RecursosWeb/DOCUMENTOS/', 'other/')),
        ):
            with self.assertRaises(ValueError):
                documents(html, SOURCE)
        with self.assertRaises(ValueError):
            revision_links(page('Normas Subsidiarias', '<div class="paginacion">2 contenidos</div>'), SOURCE)

    def test_distinct_dates_and_no_invented_modification_status(self):
        html = page('Revisión Normas Subsidiarias del planeamiento del municipio de Son Servera',
                    '<p>Aprobación definitiva con fecha 28 de marzo de 2014</p>'
                    '<div class="masinfo"><a href="RecursosWeb/DOCUMENTOS/1/plan.pdf">Normas</a></div>')
        _, _, approval = documents(html, SOURCE)
        self.assertEqual(approval, '2014-03-28')
        _, _, approval = documents(html.replace('28 de marzo de 2014', 'fecha desconocida'), SOURCE)
        self.assertIsNone(approval)
        pairs, desc, approval = documents(page('Modificación núm. 1 de NNSS',
            '<div>Suspensión del procedimiento por ejecución de sentencia.</div>' +
            table(1, [('1', 'Aprobación definitiva 1 NNSS')])), SOURCE)
        self.assertIn('Suspensión', desc)
        self.assertIsNone(approval)

    def test_full_snapshot_groups_duplicates_and_update(self):
        menu = page('Urbanismo y vivienda', '') + (
            '<a href="inventory">Normas Subsidiarias</a>'
            '<a href="mod6">Modificación núm. 6 de NNSS</a>'
            '<a href="mod7">Modificación núm. 7 de NNSS</a>')
        inventory = page('Normas Subsidiarias', '<div id="listado"><div id="descriptivo"><ul>'
                         '<li><a href="plan">Revisión</a></li></ul></div></div>'
                         '<div class="paginacion">1 contenidos</div>')
        plan = page('Normas Subsidiarias Planos', '<div class="masinfo">'
                    '<a href="RecursosWeb/DOCUMENTOS/1/map.pdf">Mapa</a></div>')
        mod6 = page('Modificación núm. 6 de NNSS', table(6, [('6', 'Memoria')]).replace(
            '<div class="paginacion">1 contenidos</div>', '') + table(7, [('7', 'Memoria 7')], 2))
        mod7 = page('Modificación núm. 7 de NNSS', table(7, [('7', 'Memoria 7')]))
        def fetch(url):
            return menu if url == SOURCE else {'inventory': inventory, 'plan': plan,
                'mod6': mod6, 'mod7': mod7}[url.rsplit('/', 1)[1]]
        adapter = SonServeraAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fetch):
            path = Path(tmp) / 'proyectos.jsonl'
            adapter.backfill_proyectos(path)
            original = path.read_text()
            rows = [json.loads(s) for s in original.splitlines()]
            self.assertEqual(len(rows), 3)
            seven = next(r for r in rows if r['id'].endswith('modificacion-7'))
            self.assertEqual(len(seven['documentos']), 1)
            self.assertEqual(len(seven['documentos'][0]['source_urls']), 2)
            for r in rows:
                self.assertIsNone(r['fecha_publicacion'])
                self.assertIsNone(r['fecha_acuerdo'])
                self.assertIsNone(r['lat'])
                self.assertIsNone(r['fase'])
            adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_text(), original)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('son-servera')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), SonServeraAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            result = SonServeraAyuntamientoAdapter().backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
