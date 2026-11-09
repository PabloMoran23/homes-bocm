"""Offline parser/contract tests; run with python -m unittest municipio.test_markina_xemein."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.markina_xemein import (
    AREA, SOURCE, MarkinaXemeinAyuntamientoAdapter, collect_documents,
    extract_projects, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def html(body):
    return '<div id="main-content">' + body + '</div>'


def link(url, title):
    return f'<a href="{url}">{title}</a>'


def document(name, title=None):
    return link(AREA + 'docs/' + name + '.pdf', title or name)


class ParserTests(unittest.TestCase):
    def test_inventory_uses_image_labels_and_excludes_forms(self):
        page = html(f'<a href="{AREA}Paginas/pgou.aspx"><img alt="PGOU - Plan General"/></a>'
                    + link('/form.pdf', 'Solicitud licencia obras')
                    + link('/news.aspx', 'Subvención urbanismo'))
        self.assertEqual(list(parse_inventory(page)), ['pgou'])
        with self.assertRaises(ValueError):
            parse_inventory(html(link('/form.pdf', 'Solicitud licencia')))
        with self.assertRaisesRegex(ValueError, 'now paginated'):
            parse_inventory(page.replace('</div>', '<ul class="pagination"></ul></div>'))

    def test_pagination_complete_and_deduplicated(self):
        base = AREA + 'Paginas/pgou.aspx'
        first = html('<div class="ms-WPBody">Resultados 1 - 1 de 2'
                     + document('a') + '</div><ul class="pagination">'
                     + link(base + '?page=2', '>') + '</ul>')
        second = html('<div class="ms-WPBody">Resultados 2 - 2 de 2'
                      + document('b') + '</div><ul class="pagination">'
                      + link(base + '?page=1', '<') + '</ul>')
        pages = {base: first, base + '?page=2': second}
        calls = []
        def fetch(url):
            calls.append(url)
            return pages[url]
        docs = collect_documents(fetch, base)
        self.assertEqual(len(docs), 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(docs[1]['source_page'], base + '?page=2')
        # A server ignoring ?page=2 must fail even if HTTP 200.
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            collect_documents(lambda _: first, base)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            collect_documents(lambda _: first.split('<ul')[0] + '</div>', base)

    def test_grouping_phase_labels_are_not_approval_facts(self):
        pgou, mod, arret = [AREA + 'Paginas/' + x + '.aspx' for x in ('pgou', 'mod', 'arret')]
        initial, provisional, final = [AREA + 'Paginas/' + x + '.aspx' for x in ('initial', 'provisional', 'final')]
        pages = {
            SOURCE: html(link(pgou, 'PGOU - Plan General')
                         + link(mod, 'Modificación puntual del PGOU: Etxetic')
                         + link(arret, 'Área RX –V-a. 40 Arretxinaga')),
            pgou: html(document('memoria') + document('plano')),
            mod: html(link(initial, 'Aprobación Inicial') + link(provisional, 'Aprobación provisional')
                      + link(final, 'Aprobación definitiva')),
            initial: html(document('etx-inicial')),
            provisional: html(document('etx-provisional')),
            final: html('<h3>Aprobación Definitiva</h3>'),
            arret: html(''.join(document(str(i), title) for i, title in enumerate([
                'Estudio detalle', 'Planos', 'Programa de Actuación Urbanizadora_Planos',
                'Programa de Actuación Urbanizadora_Texto', 'Proyecto de reparcelación',
                'Proyecto de Urbanización', 'Convenio de concertación']))),
        }
        rows = extract_projects(pages.__getitem__)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({r['id'] for r in rows}), 6)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 2, 2, 1, 1])
        self.assertEqual(rows[1]['secciones_documentales'][-1]['documentos'], 0)
        for row in rows:
            self.assertIsNone(row['fase'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['geometry'])
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in extract_projects(pages.__getitem__)])

    def test_no_partial_overwrite_and_manifest_contract(self):
        manifest = load_manifest('markina-xemein')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MarkinaXemeinAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            with patch.object(adapter, '_fetch', return_value=html('unrelated content')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
