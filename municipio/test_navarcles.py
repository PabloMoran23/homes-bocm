"""Offline parser/graph tests; small representative HTML, no live test dependency."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.navarcles import (
    BASE, SOURCE, INVENTORY, PARTICIPATION, NavarclesAyuntamientoAdapter,
    content, document_page, parse_record,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(title, text=''):
    return f'<main><div id="readspeakerPage"><h1>{title}</h1>{text}</div></main>'


def link(url, label='Document'):
    return f'<a href="{url}">{label}</a>'


ROOT = page('POUM', '<div class="ddbbtext"><p>Navarcles. El 28 d’abril de 2026, '
            'el Ple de la Corporació va aprovar per unanimitat l’Avanç del POUM.</p></div>'
            '<span class="updated">29.05.2026</span>' + link(INVENTORY) + link(PARTICIPATION))
DOC = BASE + '/media/repository/POUM/Documents/Avanc.pdf'


class NavarclesTests(unittest.TestCase):
    def test_dates_and_grouping(self):
        row = parse_record(ROOT, [{'url': DOC}], [SOURCE])
        self.assertEqual(row['fecha_acuerdo'], '2026-04-28')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['fase'], 'aprobación del avance')
        self.assertFalse(row['publication_ready'])

    def test_reject_unverified_approval(self):
        for html in (page('POUM', link(DOC)), ROOT.replace('va aprovar', 'va debatre'),
                     ROOT.replace('Navarcles', 'Other municipality'), '<h1>Login</h1>'):
            with self.assertRaises(ValueError):
                parse_record(html, [{'url': DOC}], [SOURCE])

    def test_pagination_fails(self):
        for extra in ('<a rel="next" href="/p2">2</a>', link('?pagina=2', '2'), link('/p2', 'Següent')):
            with self.assertRaises(ValueError):
                content(ROOT + extra)

    def test_documents_scope_and_deduplication(self):
        html = page('Avanç', link(DOC) * 2 + link('/forms/licence.pdf')
                    + link('https://example.org/media/repository/POUM/other.pdf')
                    + link(INVENTORY + '/avanc-poum'))
        html += '<section id="page-documents">' + link(DOC) + '</section>'
        docs, children = document_page(html, INVENTORY)
        self.assertEqual([d['url'] for d in docs], [DOC])
        self.assertEqual(docs[0]['url_fuente'], INVENTORY)
        self.assertEqual(children, {INVENTORY + '/avanc-poum'})

    def test_sidebar_attachments_are_outside_article(self):
        html = page('Avanç') + '<section id="page-documents">' + link(DOC) + '</section>'
        docs, _ = document_page(html, INVENTORY)
        self.assertEqual([d['url'] for d in docs], [DOC])

    def test_live_graph_contract_and_refresh(self):
        child = INVENTORY + '/avanc-poum'
        graph = {SOURCE: ROOT, INVENTORY: page('Documents', link(child) * 2),
                 child: page('Avanç', link(DOC) + link(INVENTORY)),
                 PARTICIPATION: page('Programa', link(DOC))}
        adapter = NavarclesAyuntamientoAdapter('navarcles')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=graph.__getitem__) as fetch:
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(fetch.call_count, 4)
            self.assertEqual(result['rows'], 1)
            row = json.loads(out.read_text())
            self.assertEqual(len(row['documentos']), 1)
            self.assertEqual(len(row['documentos'][0]['paginas_fuente']), 2)
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(row, json.loads(out.read_text()))

    def test_failed_tree_preserves_previous_output(self):
        graph = {SOURCE: ROOT, INVENTORY: page('Documents', link(INVENTORY + '/missing')),
                 INVENTORY + '/missing': page('No docs', link(INVENTORY + '/sibling'))}
        adapter = NavarclesAyuntamientoAdapter('navarcles')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=graph.__getitem__):
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('navarcles')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08140')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, NavarclesAyuntamientoAdapter)
        with self.assertRaises(NotImplementedError):
            adapter.backfill_licencias(Path('never-written.jsonl'))


if __name__ == '__main__':
    unittest.main()
